import json
import traceback
from redis import Redis
from pymysql import Connection
from pymysql.cursors import Cursor
from collections import defaultdict
from typing import Optional

from logger import logger
from api import fetch_latest_version
from rebalance import (
    calc_imbalance_score,
    rebalance_interval,
    find_rebalance_intervals,
)
from utils import (
    get_current_iso_time, 
    get_current_timestamp,
    get_seconds_until_end_of_day
)
from settings import (
    BATCH_SIZE,
    REBALANCE_ENABLED,
    MIN_IMBALANCE_SCORE,
    STAGING_DELETE_DELAY_ENABLED
)

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
    if local_version and local_version[0] == latest['short']:
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
        f"{local_version[0] if local_version else 'NULL'} -> {latest['short']}"
    )

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

def archive_base_table(cursor: Cursor) -> int:
    """归档 user、clan、ship 基础表的行数到 ARCH 表

    Args:
        cursor: 数据库游标
    """
    base_count_list = [0,0,0,0]
    # 查询当前数据行数
    i = 1
    for index in ['user', 'clan', 'ship']:
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

    logger.info(
        'Base table archived - User: %s | Clan: %s | Ship: %s',
        base_count_list[1], base_count_list[2], base_count_list[3]
    )

def get_update_ids(
    conn: Connection, 
    redis_client: Redis
) -> list:
    """分批查询需要更新的 ID 并通过 Redis 分布式锁去重

    使用 id 范围分页，每批 10000 行，调用相应判断函数筛选 due 的 ID，
    批量获取 Redis 锁后返回成功获取锁的 ID

    Args:
        conn: 数据库连接
        redis_client: Redis 客户端

    Returns:
        成功获取锁的 ID 列表
    """

    update_list = []

    total_count = 0
    planned_count = 0
    today_remained_count = 0

    total_due = 0
    locked = 0

    refresh_stats = [0] * 5
    buckets = [[] for _ in range(24)]
    all_migrations = []

    current_timestamp = get_current_timestamp()
    seconds_until_end_of_day = get_seconds_until_end_of_day()

    try:
        with conn.cursor() as cursor:
            # 获取最大 id
            cursor.execute(f"SELECT MAX(id) FROM T_user_stats;")
            max_id = cursor.fetchone()[0] or 0

            # 按 id 区间循环
            for start_id in range(1, max_id + 1, BATCH_SIZE):
                end_id = start_id + BATCH_SIZE - 1

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

                if not rows:
                    continue

                due_ids = []

                for row in rows:
                    if not row[1]:
                        # 不可用用户不更新
                        continue

                    planned_count += 1

                    # 计算下次更新时间到现在时间的差值，-1表示需要更新
                    if row[3] is None:
                        remaining_seconds = -1
                    elif row[2] and row[2] > current_timestamp:
                        remaining_seconds = row[2] - current_timestamp
                    else:
                        remaining_seconds = -1

                    if remaining_seconds < seconds_until_end_of_day:
                        today_remained_count += 1

                    # overdue：需要立即刷新
                    if remaining_seconds == -1:
                        due_ids.append(row[0])
                        refresh_stats[0] += 1
                        total_count += 1
                        # overdue 也算进 hourly_stats 的第 0 小时
                        buckets[0].append(row[0])
                        continue

                    # 统计 refresh_stats：within_24h / within_week / within_month / within_quarter
                    if remaining_seconds <= 86400:
                        refresh_stats[1] += 1  # within_24h
                    elif remaining_seconds <= 604800:
                        refresh_stats[2] += 1  # within_week
                    elif remaining_seconds <= 2592000:
                        refresh_stats[3] += 1  # within_month
                    elif remaining_seconds <= 7776000:
                        refresh_stats[4] += 1  # within_quarter

                    # 统计 refresh_hourly_stats：按小时分桶
                    if remaining_seconds < 86400:
                        hour_index = remaining_seconds // 3600
                        if hour_index < 24:
                            total_count += 1
                            buckets[hour_index].append(row[0])

                total_due += len(due_ids)

                if due_ids:
                    # 通过redis去重
                    pipe = redis_client.pipeline()
                    keys = [f"refresh_lock:user:{uid}" for uid in due_ids]
                    for key in keys:
                        pipe.set(key, 1, nx=True, ex=4*3600)
                    results = pipe.execute()
                    batch_locked = [due_ids[i] for i, r in enumerate(results) if r]
                    update_list.extend(batch_locked)
                    locked += len(batch_locked)

    except Exception:
        logger.error(traceback.format_exc())
        return []

    skipped = total_due - locked
    logger.info(
        'User update schedule - Total: %s | Locked: %s | Skipped: %s',
        total_due, locked, skipped
    )

    counts = [len(b) for b in buckets]
    score = calc_imbalance_score(counts)
    logger.debug('Refresh plan (%s): %s', score, counts)
    if REBALANCE_ENABLED and score >= MIN_IMBALANCE_SCORE:
        min_peak_abs = max(100, total_count // 10000 * 100)
        min_interval_total = 2 * min_peak_abs
        intervals = find_rebalance_intervals(
            counts,
            min_peak_abs=min_peak_abs,
            min_interval_total=min_interval_total
        )
        if intervals:
            logger.info("Found %d intervals to rebalance: %s", len(intervals), intervals)
            for left, right in intervals:
                bucket_slice = buckets[left:right+1]  # 子列表引用，修改会作用到原桶
                migrations = rebalance_interval(bucket_slice)
                all_migrations.extend(migrations)

                # 更新全局 counts 供后续区间使用
                for h in range(left, right+1):
                    counts[h] = len(buckets[h])
            score = calc_imbalance_score(counts)
            logger.debug('Rebalanced plan (%s): %s', score, counts)
        else:
            logger.debug("No interval needs rebalancing")
    else:
        logger.debug("No interval needs rebalancing")
    
    try:
        with conn.cursor() as cursor:
            # 1. 更新 planned_count
            sql = """
                UPDATE T_table_meta 
                SET 
                    metric_value = %s 
                WHERE metric_key = %s;
            """
            cursor.execute(sql, [planned_count, 'planned_users'])

            # 2. 更新 refresh_stats
            status_names = ['overdue', 'within_24h', 'within_week', 'within_month', 'within_quarter']
            for status, count in zip(status_names, refresh_stats):
                sql = """
                    UPDATE T_refresh_stats
                    SET 
                        user_count = %s,
                        updated_at = NOW()
                    WHERE status = %s;
                """
                cursor.execute(sql, [count, status])

            # 3. 更新 refresh_hourly_stats（planned_hour 对应 1~24）
            for hour_index, count in enumerate(counts):
                planned_hour = hour_index + 1
                sql = """
                    UPDATE T_refresh_hourly_stats
                    SET 
                        planned_users = %s,
                        updated_at = NOW()
                    WHERE planned_hour = %s;
                """
                cursor.execute(sql, [count, planned_hour])
            
            if all_migrations:
                sql = """
                    UPDATE T_user_stats
                    SET 
                        next_refresh_at = next_refresh_at - INTERVAL %s HOUR
                    WHERE account_id = %s
                """
                params = [(hours, uid) for uid, hours in all_migrations]
                cursor.executemany(sql, params)
                logger.info("Applied %d user migrations to database", len(all_migrations))
        conn.commit()
    except Exception:
        conn.rollback()
        logger.error(traceback.format_exc())

    logger.info('Planned user updates within today: %s', today_remained_count)

    return update_list