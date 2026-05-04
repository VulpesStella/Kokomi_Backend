import json
import traceback
from collections import defaultdict
from redis import Redis
from pymysql import Connection
from pymysql.cursors import Cursor

from logger import logger
from api import fetch_latest_version
from utils import get_current_iso_time
from settings import (
    USER_INIT_TABLE_LIST,
    CLAN_INIT_TABLE_LIST
)


def _verify_database(cursor: Cursor, index: str, table_names: list) -> int:
    """校验 user 或 clan 基础表与关联子表的数据完整性。

    - 检查 T_{index}_base 中 table_count 小于应有数量的记录
    - 为缺失的子表补充初始数据行，并修正 table_count

    Args:
        cursor: 数据库游标。
        index: 表类型标识，'user' 或 'clan'。
        table_names: 应存在的子表名称列表。

    Returns:
        int: 本次修复的行数。
    """
    fixed_count = 0

    # 根据类型确定主键字段名
    if index == 'user':
        id_str = 'account_id'
    else:
        id_str = 'clan_id'

    sql = f"""
        SELECT 
            COUNT(*) 
        FROM T_{index}_base;
    """
    cursor.execute(sql)
    data = cursor.fetchone()
    rows = data[0] if data[0] else 0
    logger.info(f'T_{index}_base total rows: {rows}')

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

def _verify_ship_archive(cursor: Cursor, all_ship_ids: list) -> None:
    """确保近期数据存档表数据完整

    - 读取全量 ship_id 和最新版本号，检查归档表中是否已有该数据条目
    - 若不存在则插入一条空数据记录

    Args:
        cursor: 数据库游标
        all_ship_ids: 所有舰船 ID 列表
    """
    if len(all_ship_ids) == 0:
        return 
    
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
        return
    version = result[0]

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
    missing_ids = [sid for sid in all_ship_ids if sid not in archived_ids]
    if not missing_ids:
        return
    
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
    logger.info(f'Insert row counts: {len(missing_ids)}')

def _archive_if_needed(
    cursor: Cursor, 
    today: str, 
    game_version: str, 
    tracking_key: str,
    source_table: str, 
    archive_table: str, 
    columns: list[str]
):
    """检查是否需要归档，如需要则按 ship_id 分别执行 INSERT 或 UPDATE

    步骤：
    1. 检查源表整体是否有变化（通过上次归档时间比较）
    2. 读取源表全量数据
    3. 读取归档表中当天+当前版本已有的 ship_id
    4. 已存在 → UPDATE，不存在 → INSERT
    5. 更新跟踪时间
    """

    # 1. 快速检查：是否需要归档
    sql = """
        SELECT 
            UNIX_TIMESTAMP(tracking_value),
            DATE(updated_at)
        FROM T_tracking_meta 
        WHERE tracking_key = %s 
          AND tracking_type = 'archive_time';
    """
    cursor.execute(sql, [tracking_key])
    row = cursor.fetchone()
    last_tracking_value = row[0] if row else None
    last_archive_date = str(row[1]) if row else None

    # 获取当前源表的数据版本标识
    sql = """
        SELECT 
            UNIX_TIMESTAMP(tracking_value) 
        FROM T_tracking_meta 
        WHERE tracking_key = 'ship_stats' 
          AND tracking_type = 'update_time';
    """
    cursor.execute(sql)
    current_tracking_value = cursor.fetchone()
    current_tracking_value = current_tracking_value[0] if current_tracking_value else None

    if current_tracking_value is None:
        return
    # 判断是否需要归档：
    # 1. tracking_value 不一致（源表数据有变化）
    # 2. 上次归档日期不是今天（保证每天都有记录）
    need_archive = False
    if last_tracking_value is None:
        need_archive = True
        logger.debug(f'{source_table} changed: NULL -> {current_tracking_value}')
    elif current_tracking_value != last_tracking_value:
        need_archive = True
        logger.debug(f'{source_table} changed: {last_tracking_value} -> {current_tracking_value}')
    elif last_archive_date != today:
        need_archive = True
        logger.debug(f'{source_table} changed: {last_archive_date} -> {today}')

    if not need_archive:
        return


    # 2. 读取源表全量数据
    col_names = ', '.join(columns)
    cursor.execute(f"SELECT ship_id, {col_names} FROM {source_table}")
    source_rows = cursor.fetchall()

    # 3. 读取归档表当天+当前版本已有的 ship_id
    sql = f"""
        SELECT ship_id 
        FROM {archive_table}
        WHERE stat_date = %s 
          AND game_version = %s;
    """
    cursor.execute(sql, (today, game_version))
    existing_ids = {row[0] for row in cursor.fetchall()}

    # 4. 收集 INSERT 和 UPDATE 列表
    insert_list = []
    update_list = []

    for source_row in source_rows:
        if source_row[0] in existing_ids:
            update_list.append(source_row)
        else:
            insert_list.append(source_row)

    # 5. 执行 INSERT
    if insert_list:
        placeholders = ', '.join(['%s'] * len(columns))
        insert_sql = f"""
            INSERT INTO {archive_table} 
            (ship_id, stat_date, game_version, {col_names})
            VALUES (%s, %s, %s, {placeholders})
        """
        for row in insert_list:
            cursor.execute(insert_sql, (row[0], today, game_version, *row[1:]))

    # 6. 执行 UPDATE
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

    # 7. 更新跟踪时间
    sql = """
        UPDATE T_tracking_meta 
        SET 
            tracking_value = FROM_UNIXTIME(%s),
            updated_at = CURRENT_TIMESTAMP 
        WHERE tracking_key = %s 
          AND tracking_type = 'archive_time';
    """
    cursor.execute(sql, [current_tracking_value, tracking_key])

    logger.info(f'Table archived: {archive_table}')

def _read_ship_ids(conn: Connection):
    ship_ids = []
    try:
        cursor: Cursor = conn.cursor()

        sql = """
            SELECT 
                ship_id 
            FROM T_ship_base;
        """
        cursor.execute(sql)
        ship_ids = [row[0] for row in cursor.fetchall()]
    
        logger.info(f'T_ship_base total rows: {len(ship_ids)}')
    except Exception:
        conn.rollback()
        logger.error((f"{traceback.format_exc()}"))
    finally:
        cursor.close()
    return ship_ids

def _need_update(conn: Connection, tracking_key: str, tracking_type: str) -> bool:
    try:
        cursor: Cursor = conn.cursor()

        sql = f"""
            SELECT 
                CASE 
                    WHEN tracking_value IS NULL THEN TRUE
                    WHEN UNIX_TIMESTAMP(CURRENT_TIMESTAMP) - UNIX_TIMESTAMP(tracking_value) > 60 THEN TRUE
                    ELSE FALSE
                END AS need_update
            FROM T_tracking_meta 
            WHERE tracking_key = '{tracking_key}' 
              AND tracking_type = '{tracking_type}';
        """
        cursor.execute(sql)
        result = cursor.fetchone()
        if not result[0]:
            return False
        sql = f"""
            UPDATE T_tracking_meta 
            SET 
                tracking_value = CURRENT_TIMESTAMP 
            WHERE tracking_key = '{tracking_key}' 
              AND tracking_type = '{tracking_type}';
        """
        cursor.execute(sql)
    except Exception:
        conn.rollback()
        logger.error((f"{traceback.format_exc()}"))
    finally:
        cursor.close()
    return True

def _aggregate_ship_recent(conn: Connection, all_ship_ids: list) -> None:
    """将中转表中 pending 状态的近期数据聚合写入归档表

    对每条 staging 记录：
      - 将 payload 内已知 ship_id 与未知 ship_id 分开
      - 未知部分作为新 error 行单独插入
      - 已知部分保留在原行，状态置 done，并参与按版本累加
      - 用直接 UPDATE 写入归档表（已确保目标行存在）
    """
    processed_count = 0
    cursor = None

    try:
        cursor: Cursor = conn.cursor()

        # 读取待处理数据
        select_sql = """
            SELECT uuid, game_version, account_id, payload
            FROM STAGING_ship_recent_data
            WHERE status = 'pending'
            LIMIT 1000
        """
        cursor.execute(select_sql)
        rows = cursor.fetchall()
        if not rows:
            return

        # 按版本分组累加（只累加已知 ship_id）
        #    结构: {game_version: {ship_id: [8 vals]}}
        version_ship_agg = defaultdict(lambda: defaultdict(lambda: [0] * 8))

        # 逐行处理，收集需要更新的 staging 状态和新增的 error 行
        update_status_params = []       # (new_status, new_payload, uuid)
        insert_error_params = []        # (uuid, game_version, account_id, error_payload)

        for uuid_val, game_version, account_id, payload_str in rows:
            try:
                payload = json.loads(payload_str)
            except (json.JSONDecodeError, TypeError):
                # 整条 payload 无法解析，原行直接标记 error
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

            # 如果没有任何已知 ship_id
            if not known:
                update_status_params.append(('error', payload_str, uuid_val))
                continue

            # 已知部分参与累加
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

            # 原行更新：状态 done，payload 只保留已知部分
            known_payload = json.dumps(known)
            update_status_params.append(('done', known_payload, uuid_val))

            # 如果有未知部分，插入新的 error 行
            if unknown:
                unknown_payload = json.dumps(unknown)
                insert_error_params.append(
                    (uuid_val, game_version, account_id, unknown_payload)
                )

        # 4. 直接 UPDATE 归档表（已知 ship_id + version 已存在）
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
            WHERE ship_id = %s AND game_version = %s
        """
        for game_ver, ship_dict in version_ship_agg.items():
            for ship_id, vals in ship_dict.items():
                cursor.execute(upsert_sql, (
                    vals[0], vals[1], vals[2], vals[3], vals[4], vals[5], vals[6], vals[7],
                    ship_id, game_ver
                ))

        # 5. 更新原有 staging 行的状态和 payload
        update_staging_sql = """
            UPDATE STAGING_ship_recent_data
            SET status = %s, payload = %s
            WHERE uuid = %s
        """
        for new_status, new_payload, uuid_val in update_status_params:
            cursor.execute(update_staging_sql, (new_status, new_payload, uuid_val))

        # 6. 插入异常行
        insert_error_sql = """
            INSERT INTO STAGING_ship_recent_data (uuid, game_version, account_id, payload, status)
            VALUES (%s, %s, %s, %s, 'error')
        """
        for uuid_val, game_ver, acc_id, err_payload in insert_error_params:
            cursor.execute(insert_error_sql, (uuid_val, game_ver, acc_id, err_payload))

        conn.commit()
        processed_count = len(rows)

    except Exception:
        conn.rollback()
        logger.error(traceback.format_exc())
    finally:
        if cursor:
            cursor.close()

    if processed_count > 0:
        logger.info(f'Processed recent data rows: {processed_count}')

def _cleanup_ship_recent(conn: Connection) -> int:
    """删除中转表中已处理完成且超过保留时间的旧数据。

    将 status 为 'done' 且 processed_at 超过指定时间的记录删除

    Args:
        conn: 数据库连接对象。

    Returns:
        int: 删除的行数。
    """
    deleted_count = 0
    
    try:
        cursor: Cursor = conn.cursor()
        
        # sql = """
        #     DELETE FROM STAGING_ship_recent_data 
        #     WHERE status = 'done';
        # """
        sql = """
            DELETE FROM STAGING_ship_recent_data 
            WHERE status = 'done' 
              AND processed_at < NOW() - INTERVAL 600 SECOND;
        """
        cursor.execute(sql)
        deleted_count = cursor.rowcount
        
        conn.commit()
    except Exception:
        conn.rollback()
        logger.error(f"{traceback.format_exc()}")
    finally:
        cursor.close()
    
    if deleted_count > 0:
        logger.info(f'Deleted `done` rows: {deleted_count}')

def refresh_version(conn: Connection, redis_client: Redis) -> None:
    """每小时检查并更新数据库中的游戏版本记录

    Args:
        conn: MySQL 数据库连接
        redis_client: Redis 客户端
    """
    try:
        cursor: Cursor = conn.cursor()
        sql = """
            SELECT 
                short_name, 
                full_name,
                UNIX_TIMESTAMP(updated_at), 
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
        if local_version and not local_version[3]:
            logger.debug('Skip to refresh version data step')
            return
        
        latest = fetch_latest_version(redis_client)
        if isinstance(latest, str):
            logger.info(f'Failed to obtain latest version: {latest}')
            return
        
        if not local_version or local_version[0] != latest['short']:
            # 版本有变化或首次插入
            sql = """
                SELECT 
                    id 
                FROM T_game_version 
                WHERE short_name = %s;
            """
            cursor.execute(sql,[latest['short']])
            existing = cursor.fetchone()
            if existing:
                # 已存在该版本记录：将所有记录的 is_latest 置为 False，再将该记录更新为最新
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
                        updated_at = CURRENT_TIMESTAMP 
                    WHERE short_name = %s;
                """
                cursor.execute(sql, [latest['full'], latest['short']])
                action_message = (
                    f"Game Version: "
                    f"{local_version[0] if local_version else 'None'} -> {latest['short']}"
                )
            else:
                # 不存在：将所有记录的 is_latest 置为 False，插入新版本记录
                sql = """
                    UPDATE T_game_version 
                    SET 
                        is_latest = FALSE 
                    WHERE is_latest = TRUE;
                """
                cursor.execute(sql)
                sql = """
                    INSERT INTO T_game_version (is_latest, short_name, full_name) VALUES (TRUE, %s, %s);
                """
                cursor.execute(sql, [latest['short'], latest['full']])
                action_message = (
                    f"Game Version: "
                    f"{local_version[0] if local_version else 'None'} -> {latest['short']}"
                )
        else:
            # 版本未变，只更新 updated_at 时间戳
            sql = """
                UPDATE T_game_version 
                SET 
                    updated_at = CURRENT_TIMESTAMP 
                WHERE is_latest = TRUE;
            """
            cursor.execute(sql)
            action_message = f"Game Version: {latest['short']} -> Latest"
        
        conn.commit()
        logger.info(action_message)
    except Exception:
        conn.rollback()
        logger.error(traceback.format_exc())
    finally:
        if 'cursor' in locals():
            cursor.close()

def maintenance_database(conn: Connection) -> None:
    """修复用户和公会基础表中缺失的关联数据行

    遍历 user_base / clan_base 中 table_count 与实际应拥有表数量不一致的记录
    为缺失的表补充一行初始数据，并更新 table_count

    Args:
        conn: 数据库连接对象

    Returns:
        总共修复的行数
    """
    # 检测是否需要更新
    update_sign = _need_update(conn, 'maintenance', 'update_time')
    if not update_sign:
        logger.debug('Skip to maintenance database step')
        return
    
    fixed_count = 0
    all_ship_ids = _read_ship_ids(conn)
    try:
        cursor: Cursor = conn.cursor()
        
        # 效验user表的完整型
        fixed_count += _verify_database(cursor, 'user', USER_INIT_TABLE_LIST)

        # 效验clan表的完整型
        fixed_count += _verify_database(cursor, 'clan', CLAN_INIT_TABLE_LIST)

        # 补全近期数据归档表
        _verify_ship_archive(cursor, all_ship_ids)

        conn.commit()
    except Exception:
        conn.rollback()
        logger.error((f"{traceback.format_exc()}"))
    finally:
        cursor.close()

    if fixed_count != 0:
        logger.info(f'Fixed row counts: {fixed_count}')

    try:
        cursor: Cursor = conn.cursor()

        # 将中转表中待处理的近期舰船数据聚合写入归档表
        _aggregate_ship_recent(conn, all_ship_ids)
        _cleanup_ship_recent(conn)

        conn.commit()
    except Exception:
        conn.rollback()
        logger.error((f"{traceback.format_exc()}"))
    finally:
        cursor.close()

def get_update_ids(mysql_connection: Connection, redis_client: Redis, index: str):
    """查询需要更新的 ID，并通过 Redis 分布式锁去重

    Args:
        conn: 数据库连接
        redis_client: Redis 客户端
        index: 查询类型，user or clan

    Returns:
        成功获取锁的用户 ID 列表
    """
    update_list = []
    cursor: Cursor = mysql_connection.cursor()
    try:
        if index == 'user':
            id_str = 'account_id'
        else:
            id_str = 'clan_id'
        sql = f"""
            SELECT 
                {id_str} 
            FROM V_{index}_update_schedule
            WHERE is_due = 1;
        """
        cursor.execute(sql)
        rows = cursor.fetchall()
        if not rows:
            return []

        all_ids = [row[0] for row in rows]
        pipe = redis_client.pipeline()
        keys = [f"refresh_lock:{index}:{aid}" for aid in all_ids]
        for key in keys:
            pipe.set(key, 1, nx=True, ex=3600)
        # 批量执行
        results = pipe.execute()
        # 根据结果过滤未重复的id
        update_list = [
            all_ids[i] for i, r in enumerate(results) if r
        ]
    except Exception:
        logger.error((f"{traceback.format_exc()}"))
    finally:
        cursor.close()
    
    return update_list

def archive_statistics(conn: Connection) -> None:
    """归档用户和工会的统计数据到相应的归档表。
    
    Args:
        conn: 数据库连接
    """
    try:
        cursor: Cursor = conn.cursor()
        today = get_current_iso_time()[:10]
        
        # 归档基础表中的用户和工会数量
        for base_table in ['user_base', 'clan_base']:
            # 查询当前数据行数
            sql = f"SELECT COUNT(*) FROM T_{base_table};"
            cursor.execute(sql)
            user_count = cursor.fetchone()[0]
        
            # 查询今天是否已有用户统计记录
            sql = f"SELECT row_count FROM ARCH_{base_table} WHERE stat_date = %s;"
            cursor.execute(sql, [today])
            user_result = cursor.fetchone()
        
            # 处理用户统计
            if user_result is None:
                # 没有记录，插入新记录
                sql = f"INSERT INTO ARCH_{base_table} (stat_date, row_count) VALUES (%s, %s);"
                cursor.execute(sql, [today, user_count])
            elif user_result[0] != user_count:
                # 有记录但数据有变化，更新
                sql = f"UPDATE ARCH_{base_table} SET row_count = %s WHERE stat_date = %s;"
                cursor.execute(sql, [user_count, today])

            logger.info(f'Table archived: T_{base_table}')
        
        # 获取当前游戏版本号
        sql = """
            SELECT short_name 
            FROM T_game_version 
            WHERE is_latest = TRUE 
            LIMIT 1;
        """
        cursor.execute(sql)
        version_row = cursor.fetchone()
        if not version_row:
            logger.warning('No active game version found, skip archive')
            return
        game_version = version_row[0]

        # 归档 T_ship_stats_by_users
        _archive_if_needed(
            cursor=cursor,
            today=today,
            game_version=game_version,
            tracking_key='ship_users',
            source_table='T_ship_stats_by_users',
            archive_table='ARCH_ship_stats_by_users',
            columns=['users', 'battles', 'win_rate', 'avg_damage', 'avg_frags', 
                     'avg_exp', 'survived_rate', 'avg_scouting_damage', 'avg_potential_damage']
        )

        # 归档 T_ship_stats_by_battles
        _archive_if_needed(
            cursor=cursor,
            today=today,
            game_version=game_version,
            tracking_key='ship_battles',
            source_table='T_ship_stats_by_battles',
            archive_table='ARCH_ship_stats_by_battles',
            columns=['battles', 'win_rate', 'avg_damage', 'avg_frags', 
                     'avg_exp', 'survived_rate', 'avg_scouting_damage', 'avg_potential_damage']
        )

        conn.commit()
    except Exception:
        conn.rollback()
        logger.error(traceback.format_exc())
    finally:
        if 'cursor' in locals():
            cursor.close()