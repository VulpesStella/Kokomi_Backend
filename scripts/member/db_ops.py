import traceback
from pymysql import Connection

from logger import logger
from rebalance import (
    calc_imbalance_score,
    rebalance_interval,
    find_rebalance_intervals,
)
from utils import (
    get_current_timestamp,
    get_seconds_until_end_of_day
)
from settings import (
    BATCH_SIZE,
    REBALANCE_ENABLED,
    MIN_IMBALANCE_SCORE
)

def get_update_ids(conn: Connection) -> list:
    """分批查询需要更新的 ID 并通过 Redis 分布式锁去重

    使用 id 范围分页，每批 10000 行，调用相应判断函数筛选 due 的 ID，
    批量获取 Redis 锁后返回成功获取锁的 ID

    Args:
        conn: 数据库连接

    Returns:
        成功获取锁的 ID 列表
    """
    update_list = []

    total_count = 0
    planned_count = 0
    today_remained_count = 0

    refresh_stats = [0] * 5
    buckets = [[] for _ in range(24)]
    all_migrations = []

    current_timestamp = get_current_timestamp()
    seconds_until_end_of_day = get_seconds_until_end_of_day()

    try:
        with conn.cursor() as cursor:
            # 获取最大 id
            cursor.execute(f"SELECT MAX(id) FROM T_clan_users;")
            max_id = cursor.fetchone()[0] or 0

            # 按 id 区间循环
            for start_id in range(1, max_id + 1, BATCH_SIZE):
                end_id = start_id + BATCH_SIZE - 1

                sql = f"""
                    SELECT 
                        clan_id, 
                        is_enabled,
                        UNIX_TIMESTAMP(next_refresh_at), 
                        UNIX_TIMESTAMP(updated_at) 
                    FROM T_clan_users
                    WHERE id BETWEEN %s AND %s;
                """
                cursor.execute(sql, [start_id, end_id])
                rows = cursor.fetchall()

                if not rows:
                    continue

                for row in rows:
                    if not row[1]:
                        # 不可用工会不更新
                        continue

                    planned_count += 1
                    
                    # 不可用用户不更新
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
                        update_list.append(row[0])
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

    except Exception:
        logger.error(traceback.format_exc())
        return []

    counts = [len(b) for b in buckets]
    score = calc_imbalance_score(counts)
    logger.debug('Refresh plan (%s): %s', score, counts)
    if REBALANCE_ENABLED and score >= MIN_IMBALANCE_SCORE:
        min_peak_abs = max(100, total_count // 10000 * 100)
        min_interval_total = min_peak_abs
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
            cursor.execute("""
                UPDATE T_table_meta 
                SET 
                    metric_value = %s 
                WHERE metric_key = %s;
            """, [planned_count, 'planned_clans'])

            # 2. 更新 refresh_stats
            status_names = ['overdue', 'within_24h', 'within_week', 'within_month', 'within_quarter']
            for status, count in zip(status_names, refresh_stats):
                sql = """
                    UPDATE T_refresh_stats
                    SET 
                        clan_count = %s,
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
                        planned_clans = %s,
                        updated_at = NOW()
                    WHERE planned_hour = %s;
                """
                cursor.execute(sql, [count, planned_hour])
            
            if all_migrations:
                sql = """
                    UPDATE T_clan_users
                    SET 
                        next_refresh_at = next_refresh_at - INTERVAL %s HOUR
                    WHERE clan_id = %s
                """
                params = [(hours, uid) for uid, hours in all_migrations]
                cursor.executemany(sql, params)
                logger.info("Applied %d clan migrations to database", len(all_migrations))
        conn.commit()
    except Exception:
        conn.rollback()
        logger.error(traceback.format_exc())

    logger.info('Planned clan updates within today: %s', today_remained_count)

    return update_list
