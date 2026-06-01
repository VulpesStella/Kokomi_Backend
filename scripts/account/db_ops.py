import json
from pymysql.cursors import Cursor
from collections import defaultdict
from typing import Optional

from logger import logger
from utils import get_current_iso_time
from settings import STAGING_DELETE_DELAY_ENABLED


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

def _read_game_version(cursor: Cursor) -> Optional[str]:
    """读取当前最新的游戏版本
    
    Args:
        cursor: 数据库游标
    """
    sql = """
        SELECT 
            short_name 
        FROM T_game_version 
        WHERE is_latest = TRUE
        LIMIT 1;
    """
    cursor.execute(sql)
    result = cursor.fetchone()
    if not result:
        return None
    else:
        return result[0]

def _verify_ship_archive(cursor: Cursor, version: str, ship_ids: list) -> None:
    """确保近期数据存档表包含最新版本下所有船只的记录

    读取全量 ship_id 和最新版本号，检查归档表中是否已有该版本的数据条目，
    若不存在则插入一条空数据记录

    Args:
        cursor: 数据库游标
        version: 游戏版本
        ship_ids: 船只ID列表
    """
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

    logger.debug(f'Table ARCH_ship_stats_by_recent inserted: {len(missing_ids)}')

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

def get_max_id(cursor: Cursor) -> int:
    """读取 T_user_stats 表中自增 ID 最大值确定数据读取的终点"""
    sql = "SELECT MAX(id) FROM T_user_stats;"
    cursor.execute(sql)

    data = cursor.fetchone()
    if data is None:
        return 0
    
    return data[0]

def get_version(cursor: Cursor) -> tuple:
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
    return cursor.fetchone()

def refresh_version(cursor: Cursor, local: str | None, latest: dict):
    # 版本未变，更新 full_name 和 updated_at
    if local and local == latest['short']:
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

    logger.info(
        f"Game Version: "
        f"{local if local else 'NULL'} -> {latest['short']}"
    )

def read_table_batch(cursor: Cursor, start_id: int, end_id: int) -> tuple:
    """从 T_user_stats 表中读取一个批次的数据"""
    sql = f"""
        SELECT 
            account_id, 
            is_enabled,
            UNIX_TIMESTAMP(next_refresh_at), 
            UNIX_TIMESTAMP(updated_at) 
        FROM T_user_stats
        WHERE id BETWEEN %s AND %s;
    """
    cursor.execute(sql, [start_id, end_id])
    rows = cursor.fetchall()

    return rows

def aggregate_recent_data(cursor: Cursor) -> None:
    # 读取所有的船只 ID
    all_ship_ids = _read_ship_ids(cursor)
    if len(all_ship_ids) == 0:
        return
    
    # 读取最新的游戏版本
    game_version = _read_game_version(cursor)
    if not game_version:
        return

    # 把新version的插入存档表
    _verify_ship_archive(cursor, game_version, all_ship_ids)
    
    # 将中转表中待处理的近期舰船数据聚合写入归档表
    processed = _aggregate_ship_recent(cursor, all_ship_ids)

    # 清理过期暂存数据
    deleted = _cleanup_ship_recent(cursor)

    logger.info(
        'Recent data aggregated - Processed: %s | Deleted: %s',
        processed, deleted
    )

def archive_base_table(cursor: Cursor) -> None:
    """归档 user、clan、ship 基础表的行数到 ARCH 表

    Args:
        cursor: 数据库游标
    """
    # 检查更新时间，每 10 分钟更新一次
    sql = """
        SELECT 
            CASE 
                WHEN tracking_value IS NULL THEN TRUE
                WHEN UNIX_TIMESTAMP(NOW()) - UNIX_TIMESTAMP(tracking_value) > 600 THEN TRUE
                ELSE FALSE
            END AS need_update
        FROM T_tracking_meta 
        WHERE tracking_key = %s 
            AND tracking_type = %s;
    """
    cursor.execute(sql, ['base_table', 'archive_time'])
    result = cursor.fetchone()
    if not result[0]:
        return

    base_count_list = [0,0,0,0]
    id_col_dict = {
        'user': 'account_id',
        'clan': 'clan_id',
        'ship': 'ship_id'
    }
    # 查询当前数据行数
    i = 1
    for index in ['user', 'clan', 'ship']:
        id_col = id_col_dict.get(index)

        sql = f"SELECT COUNT(*) FROM T_{index}_base;"
        cursor.execute(sql)
        base_count = cursor.fetchone()[0]

        sql = """
            UPDATE T_table_meta 
            SET 
                metric_value = %s 
            WHERE metric_key = %s;
        """
        cursor.execute(sql, [base_count, f'base_{index}s'])

        sql_range = f"""
            SELECT 
                COALESCE(MIN({id_col}), 0), 
                COALESCE(MAX({id_col}), 0) 
            FROM T_{index}_base;
        """
        cursor.execute(sql_range)
        min_id, max_id = cursor.fetchone()

        sql = """
            UPDATE T_base_id 
            SET 
                min_id = %s, 
                max_id = %s 
            WHERE meta = %s;
        """
        cursor.execute(sql, [min_id, max_id, index])

        base_count_list[0] += base_count
        base_count_list[i] += base_count

        i += 1

    today = get_current_iso_time()[:10]
    sql = """
        SELECT 1 
        FROM ARCH_base_count 
        WHERE stat_date = %s;
    """
    cursor.execute(sql, [today])
    data = cursor.fetchone()
    if data is None:
        sql = """
            INSERT INTO ARCH_base_count (
                stat_date, total_count, user_count, clan_count, ship_count
            ) VALUES (
                %s,%s,%s,%s,%s
            )
        """
        cursor.execute(sql, [today]+base_count_list)
    else:
        sql = """
            UPDATE ARCH_base_count 
            SET 
                total_count = %s, 
                user_count = %s, 
                clan_count = %s, 
                ship_count = %s 
            WHERE stat_date = %s;
        """
        cursor.execute(sql, base_count_list + [today])

    sql = """
        UPDATE T_tracking_meta 
        SET 
            tracking_value = NOW() 
        WHERE tracking_key = %s 
            AND tracking_type = %s;
    """
    cursor.execute(sql, ['base_table', 'archive_time'])

    logger.info(
        'Base table archived - User: %s | Clan: %s | Ship: %s',
        base_count_list[1], base_count_list[2], base_count_list[3]
    )

def write_stats_to_db(cursor, stats_data: dict) -> None:
    """ 将 RefreshPlanStats 的统计数据写入数据库"""
    # 更新统计总数：planned_users
    cursor.execute(
        "UPDATE T_table_meta SET metric_value = %s WHERE metric_key = %s",
        [stats_data['planned_count'], 'planned_users']
    )

    # 更新各刷新状态的人数
    status_names = ['overdue', 'within_24h', 'within_week', 'within_month', 'within_quarter']
    for status, count in zip(status_names, stats_data['refresh_stats']):
        cursor.execute(
            "UPDATE T_refresh_stats SET user_count = %s, updated_at = NOW() WHERE status = %s",
            [count, status]
        )

    # 更新每小时的计划人数（planned_hour 1~24）
    for hour_index, count in enumerate(stats_data['hourly_counts']):
        planned_hour = hour_index + 1
        cursor.execute(
            "UPDATE T_refresh_hourly_stats SET planned_users = %s, updated_at = NOW() WHERE planned_hour = %s",
            [count, planned_hour]
        )

    # 应用重均衡产生的用户迁移（调整 next_refresh_at）
    migrations = stats_data.get('all_migrations', [])
    if migrations:
        cursor.executemany(
            "UPDATE T_user_stats SET next_refresh_at = next_refresh_at - INTERVAL %s HOUR WHERE account_id = %s",
            [(hours, uid) for uid, hours in migrations]
        )