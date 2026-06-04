
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
    MAX_REFRESH_BATCH,
    REBALANCE_ENABLED,
    MIN_IMBALANCE_SCORE
)

class RefreshPlanStats:
    """负责用户刷新计划的统计与均衡计算"""

    def __init__(self):
        self.current_timestamp = get_current_timestamp()
        self.seconds_until_end_of_day = get_seconds_until_end_of_day()

        # 累加统计
        self.planned_count = 0
        self.today_remained_count = 0
        self.total_count = 0           # 进入 hourly 桶的总数

        # 刷新状态统计：[overdue, within_24h, within_week, within_month, within_quarter]
        self.refresh_stats = [0] * 5

        # 工会 activity_level 分布
        self.activity_distribution = [0] * 4

        # 按小时分桶（0~23），逾期也放入第 0 小时
        self.buckets = [[] for _ in range(24)]

        # 重均衡产生的迁移列表，元素为 (clan_id, hours)
        self.all_migrations = []

        # 成功获取锁的更新 ID 列表
        self.update_list = []

    def add_batch(self, rows: list[tuple]) -> list:
        """处理一批原始行，返回本批中逾期且需要尝试加锁的 ID 列表

        rows 中每条记录格式为:
            (clan_id, is_enabled, activity_level, next_refresh_at_unix, updated_at_unix)
        """
        due_ids = []

        for clan_id, is_enabled, activity_level, next_refresh_at, updated_at in rows:
            self.activity_distribution[activity_level] += 1
            if not is_enabled:
                continue

            self.planned_count += 1

            # 计算剩余秒数
            if updated_at is None:
                remaining_seconds = -1
            elif next_refresh_at and next_refresh_at > self.current_timestamp:
                remaining_seconds = next_refresh_at - self.current_timestamp
            else:
                remaining_seconds = -1

            # 统计到今天结束前还剩余的计划更新数
            if remaining_seconds < self.seconds_until_end_of_day:
                self.today_remained_count += 1

            # overdue
            if remaining_seconds == -1:
                due_ids.append(clan_id)
                self.refresh_stats[0] += 1
                self.total_count += 1
                self.buckets[0].append(clan_id)
                continue

            # refresh_stats 分类
            # within_24h / within_week / within_month / within_quarter
            if remaining_seconds <= 86400:
                self.refresh_stats[1] += 1
            elif remaining_seconds <= 604800:
                self.refresh_stats[2] += 1
            elif remaining_seconds <= 2592000:
                self.refresh_stats[3] += 1
            elif remaining_seconds <= 7776000:
                self.refresh_stats[4] += 1

            # hourly bucket
            if remaining_seconds < 86400:
                hour_index = remaining_seconds // 3600
                if hour_index < 24:
                    self.total_count += 1
                    self.buckets[hour_index].append(clan_id)

        self.update_list.extend(due_ids)

    def rebalance_plan(self):
        """基于当前 buckets 执行用户刷新计划的重均衡，结果存入 self.all_migrations，并更新桶的内容"""
        counts = [len(b) for b in self.buckets]
        score = calc_imbalance_score(counts)

        if not (REBALANCE_ENABLED and score >= MIN_IMBALANCE_SCORE):
            logger.debug("No interval needs rebalancing")
            return

        min_peak_abs = max(100, self.total_count // 10000 * 100)
        min_interval_total = 2 * min_peak_abs

        intervals = find_rebalance_intervals(
            counts,
            min_peak_abs=min_peak_abs,
            min_interval_total=min_interval_total
        )

        if not intervals:
            logger.debug("No interval needs rebalancing")
            return

        logger.info("Found %d intervals to rebalance: %s", len(intervals), intervals)

        for left, right in intervals:
            bucket_slice = self.buckets[left:right + 1]
            migrations = rebalance_interval(bucket_slice)
            self.all_migrations.extend(migrations)

            # 更新 counts 供后续区间判断
            for h in range(left, right + 1):
                counts[h] = len(self.buckets[h])

        score = calc_imbalance_score(counts)
        logger.debug('Rebalanced plan (%s): %s', score, counts)

    def get_db_update_data(self) -> dict:
        """返回用于写入数据库的统计数据字典，包含：
            - planned_count
            - refresh_stats
            - hourly_counts
            - all_migrations
            - activity_distribution
        """
        hourly_counts = [len(b) for b in self.buckets]
        activity_distribution = [[cnt, i] for i, cnt in enumerate(self.activity_distribution)]
        return {
            'planned_count': self.planned_count,
            'refresh_stats': self.refresh_stats,
            'hourly_counts': hourly_counts,
            'all_migrations': self.all_migrations,
            'activity_distribution': activity_distribution
        }

    def get_update_ids(self) -> list:
        """返回最终需要执行更新的用户 ID 列表"""
        return self.update_list[:MAX_REFRESH_BATCH]