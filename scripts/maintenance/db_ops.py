import json
import traceback
from redis import Redis
from pymysql import Connection
from pymysql.cursors import Cursor
from collections import defaultdict
from typing import Optional

from logger import logger
from api import fetch_latest_version
from utils import get_current_iso_time
from settings import (
    BATCH_SIZE,
    STAGING_DELETE_DELAY_ENABLED,
    USER_INIT_TABLE_LIST,
    CLAN_INIT_TABLE_LIST
)


def _get_game_version(cursor: Cursor) -> Optional[str]:
    """获取当前最新游戏版本号

    Args:
        cursor: 数据库游标

    Returns:
        最新版本 short_name，无记录时返回 None
    """
    sql = """
        SELECT 
            short_name 
        FROM T_game_version 
        WHERE is_latest = TRUE 
        LIMIT 1;
    """
    cursor.execute(sql)
    version_row = cursor.fetchone()
    return version_row[0] if version_row else None

def _get_stats_refresh_time(cursor: Cursor) -> Optional[int]:
    """获取 ship_stats 源表的上次数据刷新时间戳

    Args:
        cursor: 数据库游标

    Returns:
        Unix 时间戳（秒），无记录时返回 None
    """
    sql = """
        SELECT 
            UNIX_TIMESTAMP(tracking_value) 
        FROM T_tracking_meta 
        WHERE tracking_key = 'ship_stats' 
          AND tracking_type = 'update_time';
    """
    cursor.execute(sql)
    current_tracking_value = cursor.fetchone()
    return current_tracking_value[0] if current_tracking_value else None

def _read_ship_ids(cursor: Cursor) -> list[int]:
    """读取所有已记录的船只 ID 列表

    Args:
        cursor: 数据库游标

    Returns:
        ship_id 列表
    """
    sql = """
        SELECT 
            ship_id 
        FROM T_ship_base;
    """
    cursor.execute(sql)
    return [row[0] for row in cursor.fetchall()]

def _need_update(cursor: Cursor, tracking_key: str, tracking_type: str) -> bool:
    """检查是否需要执行更新任务

    查询 T_tracking_meta 表中指定键的上次更新时间，
    若超过 3600 秒或为空则更新 tracking_value 并返回 True

    Args:
        cursor: 数据库游标
        tracking_key: 追踪键
        tracking_type: 追踪类型

    Returns:
        是否需要执行更新
    """
    sql = """
        SELECT 
            CASE 
                WHEN tracking_value IS NULL THEN TRUE
                WHEN UNIX_TIMESTAMP(NOW()) - UNIX_TIMESTAMP(tracking_value) > 3600 THEN TRUE
                ELSE FALSE
            END AS need_update
        FROM T_tracking_meta 
        WHERE tracking_key = %s 
            AND tracking_type = %s;
    """
    cursor.execute(sql, [tracking_key, tracking_type])
    result = cursor.fetchone()
    if not result[0]:
        return False
    
    sql = """
        UPDATE T_tracking_meta 
        SET 
            tracking_value = NOW() 
        WHERE tracking_key = %s 
            AND tracking_type = %s;
    """
    cursor.execute(sql, [tracking_key, tracking_type])

    return True

def _verify_database(cursor: Cursor, index: str, table_names: list) -> int:
    """校验 user 或 clan 基础表与关联子表的数据完整性

    检查 T_{index}_base 中 table_count 小于应有数量的记录，
    为缺失的子表补充初始数据行并修正 table_count

    Args:
        cursor: 数据库游标
        index: 表类型标识，'user' 或 'clan'
        table_names: 应存在的子表名称列表

    Returns:
        本次修复的行数
    """
    fixed_count = 0

    # 根据类型确定主键字段名
    if index == 'user':
        id_str = 'account_id'
    else:
        id_str = 'clan_id'

    # 找出 table_count 不满足应有数量的记录
    sql = f"""
        SELECT 
            {id_str}
        FROM T_{index}_base 
        WHERE table_count < %s;
    """
    cursor.execute(sql, [len(table_names)])
    broken_ids = [row[0] for row in cursor.fetchall()]

    # 遍历每条脏数据，检查并补充缺失的子表行
    for entity_id in broken_ids:
        for table_name in table_names:
            sql = f"""
                SELECT 
                    {id_str} 
                FROM {table_name}
                WHERE {id_str} = %s;
            """
            cursor.execute(sql, [entity_id])
            result = cursor.fetchone()
            # 子表缺失记录，插入初始数据并更新计数
            if result is None:
                sql = f"""
                    INSERT INTO {table_name} (
                        {id_str}
                    ) VALUES (
                        %s
                    );
                """
                cursor.execute(sql, [entity_id])
                sql = f"""
                    UPDATE T_{index}_base 
                    SET 
                        table_count = table_count + 1 
                    WHERE {id_str} = %s;
                """
                cursor.execute(sql, [entity_id])
                fixed_count += 1
    
    return fixed_count

def _verify_ship_archive(cursor: Cursor) -> int:
    """确保近期数据存档表包含最新版本下所有船只的记录

    读取全量 ship_id 和最新版本号，检查归档表中是否已有该版本的数据条目，
    若不存在则插入一条空数据记录

    Args:
        cursor: 数据库游标

    Returns:
        本次修复的行数
    """
    # 获取当前最新版本号
    sql = """
        SELECT 
            short_name 
        FROM T_game_version 
        WHERE is_latest = TRUE;
    """
    cursor.execute(sql)
    result = cursor.fetchone()
    if not result:
        return 0
    version = result[0]

    # 获取当前表中所有船只 ID
    sql = """
        SELECT 
            ship_id 
        FROM T_ship_base;
    """
    cursor.execute(sql)
    ship_ids = [row[0] for row in cursor.fetchall()]
    if len(ship_ids) == 0:
        return 0

    # 查询已归档的 ship_id + version 组合
    sql = """
        SELECT 
            ship_id 
        FROM ARCH_ship_stats_by_recent 
        WHERE game_version = %s;
    """
    cursor.execute(sql, [version])
    archived_ids = {row[0] for row in cursor.fetchall()}
    
    # 找出未归档的 ship_id
    missing_ids = [sid for sid in ship_ids if sid not in archived_ids]
    if not missing_ids:
        return 0
    
    # 补全归档表
    for ship_id in missing_ids:
        sql = """
            INSERT INTO ARCH_ship_stats_by_recent (
                ship_id, game_version
            )
            VALUES (
                %s, %s
            );
        """
        cursor.execute(sql, [ship_id, version])

    return len(missing_ids)

def _archive_base_table(cursor: Cursor, index: str, today: str) -> None:
    """归档 user 或 clan 基础表的行数到对应的 ARCH 表

    将当天 T_{index}_base 的行数与归档表中的历史记录比较，
    无记录则插入，有变化则更新

    Args:
        cursor: 数据库游标
        index: 表类型标识，'user' 或 'clan'
        today: 当天日期字符串 YYYY-MM-DD
    """
    # 查询当前数据行数
    sql = f"SELECT COUNT(*) FROM T_{index}_base;"
    cursor.execute(sql)
    base_count = cursor.fetchone()[0]

    # 查询今天是否已有用户统计记录
    sql = f"""
        SELECT 
            row_count 
        FROM ARCH_{index}_base 
        WHERE stat_date = %s;
    """
    cursor.execute(sql, [today])
    base_result = cursor.fetchone()

    # 处理用户统计
    if base_result is None:
        # 没有记录，插入新记录
        sql = f"""
            INSERT INTO ARCH_{index}_base (
                stat_date, row_count
            ) VALUES (
                %s, %s
            );
        """
        cursor.execute(sql, [today, base_count])
    elif base_result[0] != base_count:
        # 有记录但数据有变化，更新
        sql = f"""
            UPDATE ARCH_{index}_base 
            SET 
                row_count = %s 
            WHERE stat_date = %s;
        """
        cursor.execute(sql, [base_count, today])

    logger.info(f'Table archived: T_{index}_base')

def _archive_ship_stats(
    cursor: Cursor, 
    today: str, 
    refresh_time: str,
    game_version: str, 
    tracking_key: str,
    source_table: str, 
    archive_table: str, 
    columns: list[str]
):
    """按需将源表数据归档到对应的 ARCH 表

    判断逻辑：
        1. 读取上次归档的 tracking_value 和归档日期
        2. 源表 tracking_value 变化 或 上次归档不是今天 → 触发归档
        3. 读取源表全量数据，与归档表已有记录对比
        4. 新 ship_id 执行 INSERT，已有 ship_id 执行 UPDATE
        5. 更新归档跟踪时间

    Args:
        cursor: 数据库游标
        today: 当天日期字符串 YYYY-MM-DD
        refresh_time: 源表当前的数据刷新时间戳
        game_version: 当前游戏版本号
        tracking_key: 追踪键，用于读取和更新 T_tracking_meta
        source_table: 源表名
        archive_table: 归档表名
        columns: 需要归档的列名列表
    """
    # 读取上次归档时间
    sql = """
        SELECT 
            UNIX_TIMESTAMP(tracking_value),
            DATE(updated_at)
        FROM T_tracking_meta 
        WHERE tracking_key = %s 
          AND tracking_type = %s;
    """
    cursor.execute(sql, [tracking_key, 'archive_time'])
    row = cursor.fetchone()
    last_tracking_value = row[0] if row else None
    last_archive_date = str(row[1]) if row else None

    # 判断是否需要归档：
    # 1. tracking_value 不一致（源表数据有变化）
    # 2. 上次归档日期不是今天（保证每天都有记录）
    need_archive = False
    if last_tracking_value is None:
        need_archive = True
        logger.debug(f'{source_table} changed: NULL -> {refresh_time}')
    elif refresh_time != last_tracking_value:
        need_archive = True
        logger.debug(f'{source_table} changed: {last_tracking_value} -> {refresh_time}')
    elif last_archive_date != today:
        need_archive = True
        logger.debug(f'{source_table} changed: {last_archive_date} -> {today}')

    if not need_archive:
        return

    # 读取源表全量数据
    col_names = ', '.join(columns)
    cursor.execute(f"SELECT ship_id, {col_names} FROM {source_table}")
    source_rows = cursor.fetchall()

    # 读取归档表当天+当前版本已有的 ship_id
    sql = f"""
        SELECT ship_id 
        FROM {archive_table}
        WHERE stat_date = %s 
          AND game_version = %s;
    """
    cursor.execute(sql, (today, game_version))
    existing_ids = {row[0] for row in cursor.fetchall()}

    # 收集 INSERT 和 UPDATE 列表
    insert_list = []
    update_list = []

    for source_row in source_rows:
        if source_row[0] in existing_ids:
            update_list.append(source_row)
        else:
            insert_list.append(source_row)

    # 执行 INSERT
    if insert_list:
        placeholders = ', '.join(['%s'] * len(columns))
        insert_sql = f"""
            INSERT INTO {archive_table} 
            (ship_id, stat_date, game_version, {col_names})
            VALUES (%s, %s, %s, {placeholders})
        """
        for row in insert_list:
            cursor.execute(insert_sql, (row[0], today, game_version, *row[1:]))

    # 执行 UPDATE
    if update_list:
        set_clause = ', '.join([f'{col} = %s' for col in columns])
        update_sql = f"""
            UPDATE {archive_table} 
            SET {set_clause}
            WHERE ship_id = %s AND stat_date = %s AND game_version = %s
        """
        for row in update_list:
            cursor.execute(update_sql, (*row[1:], row[0], today, game_version))
    if insert_list or update_list:
        logger.debug(f'Total: {len(insert_list)} inserted, {len(update_list)} updated')

    # 更新跟踪时间
    sql = """
        UPDATE T_tracking_meta 
        SET 
            tracking_value = FROM_UNIXTIME(%s),
            updated_at = CURRENT_TIMESTAMP 
        WHERE tracking_key = %s 
          AND tracking_type = 'archive_time';
    """
    cursor.execute(sql, [refresh_time, tracking_key])

    logger.info(f'Table archived: {archive_table}')

def _aggregate_ship_recent(cursor: Cursor, all_ship_ids: list) -> int:
    """将暂存表中 pending 状态的近期数据聚合写入归档表

    处理流程：
        1. 每次读取最多 1000 条 pending 记录
        2. 解析 payload，按 ship_id 是否已知分为 known/unknown
        3. 已知部分按版本累加并 UPDATE 归档表
        4. 原行状态更新为 done（仅保留已知部分）
        5. 未知部分作为新的 error 行插入暂存表

    Args:
        cursor: 数据库游标
        all_ship_ids: 全量已知 ship_id 列表

    Returns:
        本次处理的行数
    """
    select_sql = """
        SELECT 
            uuid, 
            game_version, 
            account_id, 
            payload
        FROM STAGING_ship_recent_data
        WHERE status = 'pending'
        LIMIT 1000;
    """
    cursor.execute(select_sql)
    rows = cursor.fetchall()
    if not rows:
        return 0

    # 按版本分组累加，结构: {game_version: {ship_id: [8 vals]}}
    version_ship_agg = defaultdict(lambda: defaultdict(lambda: [0] * 8))

    update_status_params = []       # (new_status, new_payload, uuid)
    insert_error_params = []        # (uuid, game_version, account_id, error_payload)

    for uuid_val, game_version, account_id, payload_str in rows:
        try:
            payload = json.loads(payload_str)
        except (json.JSONDecodeError, TypeError):
            update_status_params.append(('error', payload_str, uuid_val))
            continue

        known = {}
        unknown = {}

        for ship_id_str, stats in payload.items():
            ship_id = int(ship_id_str) if ship_id_str.isdigit() else None
            if ship_id is None or ship_id not in all_ship_ids:
                unknown[ship_id_str] = stats
            else:
                known[ship_id_str] = stats

        if not known:
            update_status_params.append(('error', payload_str, uuid_val))
            continue

        for ship_id_str, stats in known.items():
            ship_id = int(ship_id_str)
            safe = (list(stats) + [0] * 8)[:8]
            agg = version_ship_agg[game_version][ship_id]
            agg[0] += safe[0]
            agg[1] += safe[1]
            agg[2] += safe[2]
            agg[3] += safe[3]
            agg[4] += safe[4]
            agg[5] += safe[5]
            agg[6] += safe[6]
            agg[7] += safe[7]

        known_payload = json.dumps(known)
        update_status_params.append(('done', known_payload, uuid_val))

        if unknown:
            unknown_payload = json.dumps(unknown)
            insert_error_params.append(
                (uuid_val, game_version, account_id, unknown_payload)
            )

    # UPDATE 归档表
    upsert_sql = """
        UPDATE ARCH_ship_stats_by_recent
        SET
            battles = battles + %s,
            wins = wins + %s,
            damage = damage + %s,
            frags = frags + %s,
            exp = exp + %s,
            survived = survived + %s,
            scouting_damage = scouting_damage + %s,
            potential_damage = potential_damage + %s
        WHERE ship_id = %s 
          AND game_version = %s;
    """
    for game_ver, ship_dict in version_ship_agg.items():
        for ship_id, vals in ship_dict.items():
            cursor.execute(upsert_sql, (
                vals[0], vals[1], vals[2], vals[3], vals[4], vals[5], vals[6], vals[7],
                ship_id, game_ver
            ))

    # 更新原 staging 行状态
    update_staging_sql = """
        UPDATE STAGING_ship_recent_data
        SET 
            status = %s, 
            payload = %s, 
            processed_at = NOW() 
        WHERE uuid = %s;
    """
    for new_status, new_payload, uuid_val in update_status_params:
        cursor.execute(update_staging_sql, (new_status, new_payload, uuid_val))

    # 插入未知 ship_id 的错误行
    insert_error_sql = """
        INSERT INTO STAGING_ship_recent_data (
            uuid, game_version, account_id, payload, status
        ) VALUES (
            %s, %s, %s, %s, 'error'
        );
    """
    for uuid_val, game_ver, acc_id, err_payload in insert_error_params:
        cursor.execute(insert_error_sql, (uuid_val, game_ver, acc_id, err_payload))

    return len(rows)

def _cleanup_ship_recent(cursor: Cursor) -> int:
    """删除暂存表中已处理完成且超过保留时间的旧数据

    根据 STAGING_DELETE_DELAY_ENABLED 决定是延迟删除还是立即删除
    status='done' 的记录

    Args:
        cursor: 数据库游标

    Returns:
        删除的行数
    """
    if STAGING_DELETE_DELAY_ENABLED:
        sql = """
            DELETE FROM STAGING_ship_recent_data 
            WHERE status = 'done' 
              AND processed_at < NOW() - INTERVAL 600 SECOND;
        """
    else:
        sql = """
            DELETE FROM STAGING_ship_recent_data 
            WHERE status = 'done';
        """
    cursor.execute(sql)

    return cursor.rowcount

def refresh_version(cursor: Cursor, redis_client: Redis) -> None:
    """每小时检查并更新数据库中的游戏版本记录

    从远程 API 获取最新版本信息，与本地最新版本比较：
        - 版本未变：更新 full_name 和 updated_at
        - 版本变更：插入新版本记录并切换 is_latest 标记
        - 确保永远只有一个版本 is_latest = TRUE

    Args:
        cursor: 数据库游标
        redis_client: Redis 客户端
    """
    sql = """
        SELECT 
            short_name, 
            CASE 
                WHEN UNIX_TIMESTAMP(updated_at) IS NULL THEN TRUE
                WHEN UNIX_TIMESTAMP(CURRENT_TIMESTAMP) - UNIX_TIMESTAMP(updated_at) > 3600 THEN TRUE
                ELSE FALSE
            END AS is_due 
        FROM T_game_version 
        WHERE is_latest = TRUE 
        LIMIT 1;
    """
    cursor.execute(sql)
    local_version = cursor.fetchone()
    if local_version and not local_version[1]:
        # 有数据且当前不需要更新
        logger.debug('Skip to refresh version data step')
        return
    
    latest = fetch_latest_version(redis_client)
    if not latest:
        logger.warning(f'Failed to obtain latest version')
        return
    
    # 版本未变，更新 full_name 和 updated_at
    if local_version or local_version[0] == latest['short']:
        # 确保永远只有一个version是latest
        sql = """
            UPDATE T_game_version 
            SET 
                is_latest = FALSE 
            WHERE is_latest = TRUE;
        """
        cursor.execute(sql)
        sql = """
            UPDATE T_game_version 
            SET 
                is_latest = TRUE,
                full_name = %s, 
                updated_at = NOW() 
            WHERE short_name = %s;
        """
        cursor.execute(sql, [latest['full'], latest['short']])
        logger.info(f"Game Version: {latest['short']} -> Latest")
        return
    
    # 检查最新version是否存在于table中
    sql = """
        SELECT 
            id 
        FROM T_game_version 
        WHERE short_name = %s;
    """
    cursor.execute(sql,[latest['short']])
    existing = cursor.fetchone()
    if not existing:
        # 插入该版本的数据
        sql = """
            INSERT INTO T_game_version (
                is_latest, short_name, full_name
            ) VALUES (
                FALSE, %s, %s
            );
        """
        cursor.execute(sql, [latest['short'], latest['full']])
    
    # 确保永远只有一个version是latest
    sql = """
        UPDATE T_game_version 
        SET 
            is_latest = FALSE 
        WHERE is_latest = TRUE;
    """
    cursor.execute(sql)
    # 将该记录更新为最新
    sql = """
        UPDATE T_game_version 
        SET 
            is_latest = TRUE, 
            full_name = %s, 
            updated_at = NOW() 
        WHERE short_name = %s;
    """
    cursor.execute(sql, [latest['full'], latest['short']])

    # 把新version的插入存档表
    insert_count = _verify_ship_archive(cursor)
    logger.info(f'Insert row counts: {insert_count}')

    logger.info(
        f"Game Version: "
        f"{local_version[0] if local_version else 'NULL'} -> {latest['short']}"
    )

def maintenance_database(cursor: Cursor) -> None:
    """修复用户和公会基础表中缺失的关联数据行

    遍历 T_user_base / T_clan_base 中 table_count 不满足应有数量的记录，
    为缺失的子表补充一行初始数据并更新 table_count，
    同时检查并补全近期数据归档表

    Args:
        cursor: 数据库游标
    """
    # 检测是否需要更新
    update_sign = _need_update(cursor, 'maintenance', 'update_time')
    if not update_sign:
        logger.debug('Skip to maintenance database step')
        return
    
    fixed_count = 0
    # 效验user表的完整型
    fixed_count += _verify_database(cursor, 'user', USER_INIT_TABLE_LIST)

    # 效验clan表的完整型
    fixed_count += _verify_database(cursor, 'clan', CLAN_INIT_TABLE_LIST)

    # 检查并补全近期数据归档表
    fixed_count += _verify_ship_archive(cursor)

    if fixed_count != 0:
        logger.info(f'Fixed row counts: {fixed_count}')
    else:
        logger.debug('No abnormal data was detected')

def aggregate_recent_data(cursor: Cursor) -> None:
    # 读取所有的船只 ID
    all_ship_ids = _read_ship_ids(cursor)
    if len(all_ship_ids) == 0:
        return
    
    # 将中转表中待处理的近期舰船数据聚合写入归档表
    processed = _aggregate_ship_recent(cursor, all_ship_ids)

    # 清理过期暂存数据
    deleted = _cleanup_ship_recent(cursor)

    logger.info(
        'Recent data aggregated - Processed: %s | Deleted: %s',
        processed, deleted
    )

def get_update_ids(conn: Connection, redis_client: Redis, index: str) -> list:
    """分批查询需要更新的 ID 并通过 Redis 分布式锁去重

    使用 id 范围分页（TABLE 自增主键连续且不删除），每批 10000 行，
    调用相应判断函数筛选 due 的 ID，批量获取 Redis 锁后返回成功获取锁的 ID

    Args:
        conn: 数据库连接
        redis_client: Redis 客户端
        index: 查询类型，'user' 或 'clan'

    Returns:
        成功获取锁的 ID 列表
    """
    update_list = []
    total_due = 0
    locked = 0

    try:
        with conn.cursor() as cursor:
            # 根据类型确定表名、id 字段和判断函数
            if index == 'user':
                table_name = 'T_user_stats'
                select_sql = """
                    SELECT 
                        u.account_id,
                        F_is_user_update_due(
                            u.is_enabled,
                            u.updated_at,
                            u.activity_level,
                            IFNULL(c.user_level, 0)
                        ) AS is_due
                    FROM T_user_stats u
                    LEFT JOIN T_user_config c 
                      ON u.account_id = c.account_id
                    WHERE u.id BETWEEN %s AND %s;
                """
            else:  # clan
                table_name = 'T_clan_users'
                select_sql = """
                    SELECT 
                        c.clan_id,
                        F_is_clan_update_due(
                            c.is_enabled,
                            c.updated_at
                        ) AS is_due
                    FROM T_clan_users c
                    WHERE c.id BETWEEN %s AND %s;
                """

            # 获取最大 id
            cursor.execute(f"SELECT MAX(id) FROM {table_name};")
            max_id = cursor.fetchone()[0] or 0

            # 按 id 区间循环
            for start_id in range(1, max_id + 1, BATCH_SIZE):
                end_id = start_id + BATCH_SIZE - 1
                cursor.execute(select_sql, [start_id, end_id])
                rows = cursor.fetchall()
                if not rows:
                    continue

                # 提取 due 的 ID
                due_ids = [row[0] for row in rows if row[1]]
                total_due += len(due_ids)

                if due_ids:
                    pipe = redis_client.pipeline()
                    keys = [f"refresh_lock:{index}:{uid}" for uid in due_ids]
                    for key in keys:
                        pipe.set(key, 1, nx=True, ex=3600)
                    results = pipe.execute()
                    batch_locked = [due_ids[i] for i, r in enumerate(results) if r]
                    update_list.extend(batch_locked)
                    locked += len(batch_locked)

                start_id = end_id + 1

    except Exception:
        logger.error(f"{traceback.format_exc()}")
        return []

    skipped = total_due - locked
    logger.debug(
        '%s update schedule - Total: %s | Locked: %s | Skipped: %s',
        index.capitalize(), total_due, locked, skipped
    )

    return update_list

def archive_statistics(cursor: Cursor) -> None:
    """归档用户/公会数量和船只统计数据到对应的 ARCH 表

    归档内容包括：
        - T_user_base / T_clan_base 的行数
        - T_ship_stats_by_users → ARCH_ship_stats_by_users
        - T_ship_stats_by_battles → ARCH_ship_stats_by_battles

    Args:
        cursor: 数据库游标
    """
    today = get_current_iso_time()[:10]
    
    # 归档基础表中的用户和工会数量
    for index in ['user', 'clan']:
        _archive_base_table(cursor, index, today)
    
    # 获取当前游戏版本号
    game_version = _get_game_version(cursor)
    if game_version is None:
        logger.warning('No active game version found, skip archive')
        return

    # 获取当前源表的数据版本标识
    current_tracking_value = _get_stats_refresh_time(cursor)
    if current_tracking_value is None:
        return

    # 归档 T_ship_stats_by_users
    _archive_ship_stats(
        cursor=cursor,
        today=today,
        refresh_time=current_tracking_value,
        game_version=game_version,
        tracking_key='ship_users',
        source_table='T_ship_stats_by_users',
        archive_table='ARCH_ship_stats_by_users',
        columns=['users', 'battles', 'win_rate', 'avg_damage', 'avg_frags', 
                'avg_exp', 'survived_rate', 'avg_scouting_damage', 'avg_potential_damage']
    )

    # 归档 T_ship_stats_by_battles
    _archive_ship_stats(
        cursor=cursor,
        today=today,
        refresh_time=current_tracking_value,
        game_version=game_version,
        tracking_key='ship_battles',
        source_table='T_ship_stats_by_battles',
        archive_table='ARCH_ship_stats_by_battles',
        columns=['battles', 'win_rate', 'avg_damage', 'avg_frags', 
                'avg_exp', 'survived_rate', 'avg_scouting_damage', 'avg_potential_damage']
    )