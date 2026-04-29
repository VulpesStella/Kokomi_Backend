import json
import traceback
from tqdm import tqdm
from pymysql import Connection
from pymysql.cursors import Cursor
from datetime import datetime, timezone
from typing import Any, Iterator, List, Dict, Tuple

from logger import logger
from settings import (
    USE_TQDM,
    DATE_FMT,
    DATA_DIR,
    BATCH_SIZE,
    SHIP_METRIC_MAP
)


HISTOGRAM_BUCKETS = 200  # 固定桶数量
# 字段索引常量（与 ship_cache 值数组顺序严格对应）
IDX_BATTLES       = 0
IDX_WINS          = 1
IDX_DAMAGE        = 2
IDX_FRAGS         = 3
IDX_EXP           = 4
IDX_SURVIVED_RATE = 5
IDX_SCOUT_DMG     = 6
IDX_POTENTIAL_DMG = 7
# 参与分布计算的指标列表
DIST_METRICS = [
    "win_rate",
    "avg_damage",
    "avg_frags",
    "avg_exp",
    "survived_rate",
    "avg_scouting_dmg",
    "avg_potential_dmg",
]

def _log_warning(message: str) -> None:
    """根据 USE_TQDM 配置输出警告信息"""
    if USE_TQDM:
        tqdm.write(f'{get_formatted_date()} [WARNING] {message}')
    else:
        logger.warning(message)

def _log_error(message: str) -> None:
    """根据 USE_TQDM 配置输出错误信息"""
    if USE_TQDM:
        tqdm.write(f'{get_formatted_date()} [ERROR]\n{message}')
    else:
        logger.error(message)

def get_current_iso_time() -> str:
    """获取当前 UTC 时间的 ISO 格式字符串"""
    return datetime.now(timezone.utc).isoformat(timespec='seconds')

def get_formatted_date() -> str:
    """获取当前日期格式化字符串，用于日志输出"""
    return datetime.now().strftime(DATE_FMT)

def read_version() -> str:
    """从本地 JSON 文件读取当前游戏版本短号

    Returns:
        版本字符串，如 '15.3'
    """
    file_path = DATA_DIR / "json/game_version.json"
    with open(file_path, "r", encoding="utf-8") as f:
        version_data = json.load(f)
        return version_data['short']

def analyze_db_files() -> str:
    """递归扫描 db 目录下的所有 .db 文件，统计数量与总大小，
    并将结果写入 JSON

    Returns:
        格式化的统计摘要字符串。
    """
    db_files_dir = DATA_DIR / 'db'
    db_files = list(db_files_dir.rglob("*.db"))
    file_count = len(db_files)
    total_size = 0

    for f in db_files:
        try:
            total_size += f.stat().st_size
        except Exception:
            continue

    avg_size = total_size / file_count if file_count else 0

    result = {
        "update_time": int(datetime.now().timestamp()),
        "file_count": file_count,
        "total_size_bytes": total_size,
        "avg_size_bytes": int(avg_size)
    }

    output_file = DATA_DIR / "json/db_stats.json"
    with output_file.open("w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    return (f"Files: {file_count}  "
            f"Size: {round(total_size / 1024 / 1024, 2)} MB  "
            f"Avg: {round(avg_size / 1024 / 1024, 2)} MB")

# def refresh_leaderboard(
#     mysql_connection: Connection, 
#     redis_client: Redis,
#     ship_ids: list
# ):
#     redis_client.set(f'leaderboard:maintenance', 1, ex=3600)
#     time.sleep(3)   # 等待一小段时间
#     len_ship_ids = len(ship_ids)
#     if USE_TQDM:
#         iterator = tqdm(
#             ship_ids, 
#             total=len_ship_ids, 
#             desc=f"{datetime.now().strftime(DATE_FMT)} [INFO] Refreshing MySQL"
#         )
#     else:
#         iterator = enumerate(ship_ids, 1)
#     for item in iterator:
#         mysql_connection.begin()
#         cursor: Cursor = mysql_connection.cursor()
#         try:
#             if USE_TQDM:
#                 update_id = item
#                 index = iterator.n
#             else:
#                 index, update_id = item
#             sql = """
#                 UPDATE T_ship_pvp_leaderboard l
#                 JOIN T_ship_stats_by_battles s 
#                     ON l.ship_id = s.ship_id
#                 SET
#                     l.rating = F_calculate_ship_pr(
#                         l.win_rate, l.avg_damage, l.avg_frags,
#                         s.win_rate, s.avg_damage, s.avg_frags
#                     ),
#                     l.avg_damage_level = F_get_metric_level(1, l.avg_damage, s.avg_damage),
#                     l.avg_frags_level = F_get_metric_level(2, l.avg_frags, s.avg_frags),
#                     l.updated_at = NOW()
#                 WHERE l.ship_id = %s;
#             """
#             cursor.execute(sql, [update_id])
#             row_count = cursor.rowcount
#             if USE_TQDM:
#                 iterator.set_postfix_str(f"{update_id} | UPDATE {row_count} Rows")
#             else:
#                 logger.info(f'[{index}/{len_ship_ids}] {update_id} | UPDATE {row_count} Rows')
#             mysql_connection.commit()
#         except Exception as e:
#             mysql_connection.rollback()
#             logger.error((f"{traceback.format_exc()}"))
#             redis_client.delete(f'leaderboard:maintenance')
#             return type(e).__name__
#         finally:
#             cursor.close()
#     if USE_TQDM:
#         iterator = tqdm(
#             ship_ids, 
#             total=len_ship_ids, 
#             desc=f"{datetime.now().strftime(DATE_FMT)} [INFO] Refreshing Redis"
#         )
#     else:
#         iterator = enumerate(ship_ids, 1)
#     for item in iterator:
#         cursor: Cursor = mysql_connection.cursor()
#         try:
#             if USE_TQDM:
#                 update_id = item
#                 index = iterator.n
#             else:
#                 index, update_id = item
#             sql = """
#                 SELECT 
#                     account_id, 
#                     rating
#                 FROM T_ship_pvp_leaderboard
#                 WHERE ship_id = %s;
#             """
#             cursor.execute(sql, [update_id])
#             rows = cursor.fetchall()
#             if rows:
#                 key = f"leaderboard:ship:{update_id}"
#                 pipe = redis_client.pipeline()
#                 pipe.delete(key)
#                 for acc, rating in rows:
#                     if rating >= 0:
#                         pipe.zadd(key, {str(acc): float(rating)})
#                 pipe.execute()
#                 row_count = len(rows)
#             else:
#                 row_count = 0
#             if USE_TQDM:
#                 iterator.set_postfix_str(f"{update_id} | REFRESH {row_count} Keys")
#             else:
#                 logger.info(f'[{index}/{len_ship_ids}] {update_id} | REFRESH {row_count} Keys')
#             mysql_connection.commit()
#         except Exception as e:
#             mysql_connection.rollback()
#             logger.error((f"{traceback.format_exc()}"))
#             redis_client.delete(f'leaderboard:maintenance')
#             return type(e).__name__
#         finally:
#             cursor.close()
#     redis_client.delete(f'leaderboard:maintenance')
#     redis_client.set(f'leaderboard:refresh_time', int(time.time()))
#     return 'Success'

class SimpleHistogram:
    """固定桶直方图，支持流式插入和分位数查询

    将连续的数值范围均匀划分为 bucket_count 个桶
    每个桶记录落在该区间的样本数量
    查询分位数时按桶累积计数定位，返回桶中心值
    """

    def __init__(self, bucket_count: int = HISTOGRAM_BUCKETS, min_val: float = 0.0, max_val: float = 100.0):
        """
        Args:
            bucket_count: 桶的数量
            min_val: 数值范围下限（低于此值归入首个桶）。
            max_val: 数值范围上限（高于此值归入末尾桶）。
        """
        self.bucket_count = bucket_count
        self.min_val = min_val
        self.max_val = max_val
        self.bucket_width = (max_val - min_val) / bucket_count
        self.buckets = [0] * bucket_count
        self.total_count = 0

    def update(self, value: float) -> None:
        """插入一个样本值（O(1)）。"""
        self.total_count += 1
        idx = int((value - self.min_val) / self.bucket_width)
        if idx < 0:
            self.buckets[0] += 1
        elif idx >= self.bucket_count:
            self.buckets[-1] += 1
        else:
            self.buckets[idx] += 1

    def percentile(self, p: float) -> float:
        """
        查询第 p 百分位的近似值（O(桶数)）。

        Args:
            p: 分位点，1-100 之间的数值。

        Returns:
            近似分位数值（桶中心值）。
        """
        if self.total_count == 0:
            return 0.0

        target = int(self.total_count * p / 100)
        accumulated = 0
        for i, count in enumerate(self.buckets):
            accumulated += count
            if accumulated >= target:
                return round(self.min_val + (i + 0.5) * self.bucket_width, 2)
        return self.max_val
    
def _create_metric_histograms() -> Dict[str, SimpleHistogram]:
    """为每个分布指标创建一个直方图对象。

    范围根据各指标的游戏数据特征设定：
    - win_rate / survived_rate: 0-100%
    - avg_damage: 0-300,000
    - avg_frags: 0-5
    - avg_exp: 0-5,000
    - avg_scouting_dmg: 0-200,000
    - avg_potential_dmg: 0-3,000,000
    """
    return {
        "win_rate":          SimpleHistogram(HISTOGRAM_BUCKETS, 0, 100),
        "avg_damage":        SimpleHistogram(HISTOGRAM_BUCKETS, 0, 300000),
        "avg_frags":         SimpleHistogram(HISTOGRAM_BUCKETS, 0, 5),
        "avg_exp":           SimpleHistogram(HISTOGRAM_BUCKETS, 0, 5000),
        "survived_rate":     SimpleHistogram(HISTOGRAM_BUCKETS, 0, 100),
        "avg_scouting_dmg":  SimpleHistogram(HISTOGRAM_BUCKETS, 0, 200000),
        "avg_potential_dmg": SimpleHistogram(HISTOGRAM_BUCKETS, 0, 3000000),
    }

def _get_percentiles(
    hist: SimpleHistogram,
    percentiles: Tuple[int, ...] = (5, 10, 25, 50, 75, 90, 95)
) -> Dict[str, float]:
    """从 SimpleHistogram 中提取指定分位数值。

    Args:
        hist: SimpleHistogram 实例。
        percentiles: 需要提取的分位点列表（1-100 之间）。

    Returns:
        {'p5': xx.x, 'p10': xx.x, ...}
    """
    return {f"p{p}": hist.percentile(p) for p in percentiles}

def aggregate_pvp_stats(
    cursor,
    max_id: int,
    ship_ids: List[int]
) -> Tuple[
    Dict[int, List[float]],
    Dict[int, Dict[str, Any]],
    Dict[int, Dict[str, Any]],
]:
    """
    分批读取 T_user_pvp.ship_cache，对每个启用的船只计算三种统计。

    三种统计：
      1. 场次平均 — 所有用户的原始值累加，最后除以总场次。
      2. 用户平均 — 筛选场次>=10的用户，先算各用户平均值，再求用户间均值。
      3. 用户分布 — 同上筛选，用固定桶直方图收集各用户平均值，提取 P5/P10/.../P95。

    Returns:
        battles_accum     - {ship_id: [累加原始值 x8]}
        users_accum       - {ship_id: {count, sum_battles, sum_win_rate, ...}}
        distribution_data - {ship_id: {metric_name: {p5:xx, ..., sample_count:N}, ...}}
    """
    # ---------- 初始化容器 ----------
    battles_accum: Dict[int, List[float]] = {
        sid: [0.0] * 8 for sid in ship_ids
    }
    users_accum: Dict[int, Dict[str, Any]] = {
        sid: {
            "count": 0,
            "sum_battles": 0,
            "sum_win_rate": 0.0,
            "sum_avg_damage": 0.0,
            "sum_avg_frags": 0.0,
            "sum_avg_exp": 0.0,
            "sum_survived_rate": 0.0,
            "sum_avg_scouting_dmg": 0.0,
            "sum_avg_potential_dmg": 0.0,
        }
        for sid in ship_ids
    }
    dist_collectors: Dict[int, Dict[str, SimpleHistogram]] = {
        sid: _create_metric_histograms() for sid in ship_ids
    }

    # ---------- 进度条 ----------
    if USE_TQDM:
        from tqdm import tqdm
        pbar = tqdm(total=max_id, desc="Processing PVP cache", unit="rows")
    else:
        pbar = None

    try:
        # ---------- 分批读取 ----------
        for offset in range(0, max_id, BATCH_SIZE):
            cursor.execute(
                "SELECT ship_cache FROM T_user_pvp WHERE id BETWEEN %s AND %s;",
                (offset + 1, offset + BATCH_SIZE),
            )
            rows = cursor.fetchall()

            if pbar:
                pbar.update(len(rows))

            for (ship_cache_json,) in rows:
                # 跳过空数据
                if not ship_cache_json:
                    continue
                try:
                    cache: Dict[str, list] = json.loads(ship_cache_json)
                except Exception:
                    logger.warning("JSON parse error near offset %d", offset)
                    continue

                for sid_str, stats in cache.items():
                    # 数据合法性校验
                    if not isinstance(stats, list) or len(stats) < 8:
                        continue
                    sid = int(sid_str)
                    if sid not in ship_ids:
                        continue

                    battles = stats[IDX_BATTLES]

                    # ===== 1. 场次累加（所有用户） =====
                    base = battles_accum[sid]
                    for i in range(8):
                        base[i] += stats[i]

                    # ===== 2 & 3. 仅统计场次 >= 10 的用户 =====
                    if battles < 10:
                        continue

                    # 计算该用户的平均指标
                    win_rate = stats[IDX_WINS] / battles * 100
                    avg_damage = stats[IDX_DAMAGE] / battles
                    avg_frags = stats[IDX_FRAGS] / battles
                    avg_exp = stats[IDX_EXP] / battles
                    survived_rate = stats[IDX_SURVIVED_RATE] / battles
                    avg_scouting_dmg = stats[IDX_SCOUT_DMG] / battles
                    avg_potential_dmg = stats[IDX_POTENTIAL_DMG] / battles

                    # 累加用户平均值
                    u = users_accum[sid]
                    u["count"] += 1
                    u["sum_battles"] += battles
                    u["sum_win_rate"] += win_rate
                    u["sum_avg_damage"] += avg_damage
                    u["sum_avg_frags"] += avg_frags
                    u["sum_avg_exp"] += avg_exp
                    u["sum_survived_rate"] += survived_rate
                    u["sum_avg_scouting_dmg"] += avg_scouting_dmg
                    u["sum_avg_potential_dmg"] += avg_potential_dmg

                    # 喂入分布收集器（直方图）
                    d = dist_collectors[sid]
                    d["win_rate"].update(win_rate)
                    d["avg_damage"].update(avg_damage)
                    d["avg_frags"].update(avg_frags)
                    d["avg_exp"].update(avg_exp)
                    d["survived_rate"].update(survived_rate)
                    d["avg_scouting_dmg"].update(avg_scouting_dmg)
                    d["avg_potential_dmg"].update(avg_potential_dmg)

    finally:
        if pbar:
            pbar.close()

    # ---------- 后处理：提取分布分位数 ----------
    distribution_data: Dict[int, Dict[str, Any]] = {}
    for sid, metrics in dist_collectors.items():
        distribution_data[sid] = {}
        for metric_name, hist in metrics.items():
            entry = _get_percentiles(hist)
            entry["sample_count"] = users_accum[sid]["count"]
            distribution_data[sid][metric_name] = entry

    return battles_accum, users_accum, distribution_data

def update_battles_stats_table(
    cursor,
    battles_accum: Dict[int, List[float]],
) -> None:
    """将场次平均统计数据写入 T_ship_stats_by_battles。

    battles 字段 = 所有用户的总场次累加值。
    其余指标 = 总累计值 / 总场次。
    """
    update_sql = """
        UPDATE T_ship_stats_by_battles
        SET
            battles               = %s,
            win_rate              = %s,
            avg_damage            = %s,
            avg_frags             = %s,
            avg_exp               = %s,
            survived_rate         = %s,
            avg_scouting_damage   = %s,
            avg_potential_damage  = %s,
            updated_at            = CURRENT_TIMESTAMP
        WHERE
            ship_id = %s
    """
    params = []

    for ship_id, acc in battles_accum.items():
        battles = acc[IDX_BATTLES]
        if battles == 0:
            continue

        params.append((
            int(battles),
            round(acc[IDX_WINS] / battles * 100, 2),
            round(acc[IDX_DAMAGE] / battles, 2),
            round(acc[IDX_FRAGS] / battles, 2),
            round(acc[IDX_EXP] / battles, 2),
            round(acc[IDX_SURVIVED_RATE] / battles, 2),
            int(acc[IDX_SCOUT_DMG] / battles),
            int(acc[IDX_POTENTIAL_DMG] / battles),
            ship_id,
        ))

    if params:
        cursor.executemany(update_sql, params)
        logger.info(f"Updated {cursor.rowcount} rows in T_ship_stats_by_battles")

def update_users_stats_table(
    cursor,
    users_accum: Dict[int, Dict[str, Any]],
) -> None:
    """将用户平均统计数据写入 T_ship_stats_by_users。

    battles 字段 = 合格用户（场次>=10）的总场次之和。
    其余指标 = 各合格用户平均值之和 / 合格用户数。
    """
    update_sql = """
        UPDATE T_ship_stats_by_users
        SET
            users                 = %s,
            battles               = %s,
            win_rate              = %s,
            avg_damage            = %s,
            avg_frags             = %s,
            avg_exp               = %s,
            survived_rate         = %s,
            avg_scouting_damage   = %s,
            avg_potential_damage  = %s,
            updated_at            = CURRENT_TIMESTAMP
        WHERE
            ship_id = %s
    """
    params = []

    for ship_id, u in users_accum.items():
        cnt = u["count"]
        if cnt == 0:
            continue

        params.append((
            cnt,
            int(u["sum_battles"]),
            round(u["sum_win_rate"] / cnt, 2),
            round(u["sum_avg_damage"] / cnt, 2),
            round(u["sum_avg_frags"] / cnt, 2),
            round(u["sum_avg_exp"] / cnt, 2),
            round(u["sum_survived_rate"] / cnt, 2),
            int(u["sum_avg_scouting_dmg"] / cnt),
            int(u["sum_avg_potential_dmg"] / cnt),
            ship_id,
        ))

    if params:
        cursor.executemany(update_sql, params)
        logger.info(f"Updated {cursor.rowcount} rows in T_ship_stats_by_users")

def update_distribution_table(
    cursor,
    distribution_data: Dict[int, Dict[str, Any]],
) -> None:
    """将用户分布百分位数据写入 T_ship_stats_distribution。

    表中所有 (ship_id, metric_id) 已通过初始化脚本预先创建，
    此处仅执行 UPDATE 操作。
    """
    update_sql = """
        UPDATE T_ship_stats_distribution
        SET
            sample_count = %s,
            p5           = %s,
            p10          = %s,
            p25          = %s,
            p50          = %s,
            p75          = %s,
            p90          = %s,
            p95          = %s
        WHERE ship_id   = %s
          AND metric_id = %s
    """
    params = []

    for ship_id, metrics in distribution_data.items():
        for metric_name, values in metrics.items():
            metric_id = SHIP_METRIC_MAP.get(metric_name)
            if metric_id is None:
                logger.warning(f"Unknown metric_name: {metric_name}, skip")
                continue
            params.append((
                values["sample_count"],
                values["p5"],
                values["p10"],
                values["p25"],
                values["p50"],
                values["p75"],
                values["p90"],
                values["p95"],
                ship_id,
                metric_id,
            ))

    if params:
        cursor.executemany(update_sql, params)
        logger.info(f"Updated {cursor.rowcount} rows in T_ship_stats_distribution")

def process_region_stats(mysql_connection, game_version):
    """处理 PVP 统计的完整流程。

    步骤：
      1. 获取启用的船只列表和 T_user_pvp 最大 ID。
      2. 聚合计算：场次平均、用户平均、用户分布。
      3. 写入三张统计表。

    注意：事务提交/回滚由调用方控制。
    """
    cursor = mysql_connection.cursor()

    # 1. 获取启用的船只列表 & 表最大 ID
    cursor.execute("SELECT ship_id FROM T_ship_base WHERE is_enabled = 1")
    ship_ids = [row[0] for row in cursor.fetchall()]

    cursor.execute("SELECT MAX(id) FROM T_user_pvp")
    row = cursor.fetchone()
    max_id = row[0] if row and row[0] else 0
    logger.info(f"Max ID in T_user_pvp: {max_id}, Enabled ships: {len(ship_ids)}")

    if max_id == 0:
        return

    # 2. 聚合计算
    battles_accum, users_accum, distribution_data = aggregate_pvp_stats(
        cursor, max_id, ship_ids
    )

    # 3. 更新三张统计表
    update_battles_stats_table(cursor, battles_accum)
    update_users_stats_table(cursor, users_accum)
    update_distribution_table(cursor, distribution_data)