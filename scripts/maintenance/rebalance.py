import math
from pymysql.cursors import Cursor

from logger import logger
from settings import MIN_IMBALANCE_SCORE

def apply_migrations(cursor: Cursor, migrations: list, index: str) -> int:
    """
    批量更新用户的 next_refresh_at，将其提前指定的小时数。

    Args:
        cursor: 数据库游标
        migrations: [(user_id, advance_hours), ...]
        index: 'user' 或 'clan'

    Returns:
        更新的行数
    """
    if not migrations:
        return 0

    if index == 'user':
        table = 'T_user_stats'
        id_col = 'account_id'
    else:
        table = 'T_clan_users'
        id_col = 'clan_id'

    sql = f"""
        UPDATE {table}
        SET next_refresh_at = next_refresh_at - INTERVAL %s HOUR
        WHERE {id_col} = %s
    """
    params = [(hours, uid) for uid, hours in migrations]

    affected = 0
    batch_size = 1000
    for i in range(0, len(params), batch_size):
        batch = params[i:i+batch_size]
        cursor.executemany(sql, batch)
        affected += cursor.rowcount
    return affected

def update_hourly_stats(cursor: Cursor, counts: list, index: str) -> None:
    """
    将均衡后的每小时计划数写回 T_refresh_hourly_stats 表。
    
    Args:
        cursor: 数据库游标
        counts: 长度为 24 的列表，每小时计划数（索引0=当前小时）
        index: 'user' 或 'clan'
    """
    if len(counts) != 24:
        return

    if index == 'user':
        field = 'planned_users'
    else:
        field = 'planned_clans'

    sql = f"""
        UPDATE T_refresh_hourly_stats
        SET {field} = %s,
            updated_at = NOW()
        WHERE planned_hour = %s
    """
    for hour_index, count in enumerate(counts):
        planned_hour = hour_index + 1
        cursor.execute(sql, (count, planned_hour))
    logger.info("Updated T_refresh_hourly_stats for %s", index)

def calc_imbalance_score(counts: list) -> float:
    """
    计算分布不合理系数。

    定义为所有违反单调不增的相邻逆增量总和 / 区间总计划数 × 100。
    返回值越接近 100 表示分布越不合理（越不满足单调不增）。
    """
    n = len(counts)
    if n < 2:
        return 0.0
    total_excess = sum(max(0, counts[i + 1] - counts[i]) for i in range(n - 1))
    total = sum(counts)
    if total == 0:
        return 0.0
    return round((total_excess / total) * 100, 2)

def find_rebalance_intervals(
    counts: list,
    min_peak_abs: int = 100,
    min_interval_total: int = 200
) -> list:
    """
    扫描 24 小时分布，返回需要削峰的区间。

    一个合理的分布应为单调不增（越早时段更新越多）。
    从后向前扫描，识别出右侧高、左侧低的“尖峰”区间，
    并根据绝对数量和波动程度过滤。

    Args:
        counts: 长度为 24 的列表
        min_peak_abs: 尖峰最低绝对值，低于此不处理
        min_interval_total: 区间最少计划总数，低于此不处理

    Returns:
        list[tuple[int, int]]: 闭区间索引列表
    """
    if len(counts) != 24:
        return []

    intervals = []
    hour = 23

    while hour > 0:
        # 跳过绝对数量过小
        if counts[hour] < min_peak_abs:
            hour -= 1
            continue

        # 未违反单调不增
        if counts[hour - 1] >= counts[hour]:
            hour -= 1
            continue

        # 向左寻找区间左边界：直到遇到第一个大于当前峰值的桶
        left = hour - 1
        while left > 0:
            if counts[left - 1] < counts[hour]:
                left -= 1
            else:
                break

        interval_counts = counts[left:hour + 1]
        total_in_interval = sum(interval_counts)

        # 过滤总量过小
        if total_in_interval < min_interval_total:
            hour = left - 1
            continue

        # 过滤轻微波动
        score = calc_imbalance_score(interval_counts)
        logger.info("Interval [%d-%d] Score(%.2f): %s", left, hour, score, interval_counts)

        if score >= MIN_IMBALANCE_SCORE:
            intervals.append((left, hour))

        hour = left - 1

    logger.info("Found %d intervals to rebalance: %s", len(intervals), intervals)
    return intervals

def rebalance_interval(
    buckets_slice: list
) -> list:
    """
    对区间内的用户桶进行负载均衡（只能提前，就近填谷）。

    从最左侧桶开始，若低于目标平均值，则从右侧最近的富余桶借用用户。
    返回所有需要提前的用户迁移记录。

    Args:
        buckets_slice: 区间内按小时顺序排列的桶，每个桶是用户 ID 列表

    Returns:
        List[Tuple[int, int]]: 每个元素为 (user_id, advance_hours)
    """
    n = len(buckets_slice)
    if n <= 1:
        return []

    # 每桶当前人数
    counts = [len(b) for b in buckets_slice]
    total = sum(counts)
    avg = total / n
    target = math.floor(avg)
    if target == 0 and total > 0:
        target = 1  # 至少填至 1，避免永远填不满

    migrations = []

    for i in range(n):
        deficit = target - counts[i]
        if deficit <= 0:
            continue

        j = i + 1
        while deficit > 0 and j < n:
            surplus = counts[j] - target
            if surplus > 0:
                move = min(deficit, surplus)
                # 从桶 j 取出 move 个用户，放入桶 i
                for _ in range(move):
                    if not buckets_slice[j]:
                        break
                    user_id = buckets_slice[j].pop()
                    buckets_slice[i].append(user_id)
                    migrations.append((user_id, j - i))
                counts[i] += move
                counts[j] -= move
                deficit -= move
            j += 1

    # 注意：因取整可能导致极少用户未被分配，留在原桶不影响整体合理性
    return migrations