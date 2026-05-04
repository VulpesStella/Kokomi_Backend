from datetime import datetime, timezone

from settings import METRIC_RATING_THRESHOLDS


def get_current_timestamp() -> int:
    """获取当前 UTC 时间的 int 类型时间戳（秒）"""
    return int(datetime.now(timezone.utc).timestamp())

def get_current_iso_time() -> str:
    """获取当前 UTC 时间的 ISO 格式字符串"""
    return datetime.now(timezone.utc).isoformat(timespec='seconds')

def get_rating_level(
    value: float,
    metric_name: str
) -> int:
    # 获取对应指标的阈值列表
    thresholds = METRIC_RATING_THRESHOLDS.get(metric_name)
    if not thresholds:
        return 1

    # 遍历阈值，找到第一个大于 value 的阈值位置
    for i, threshold in enumerate(thresholds):
        if value < threshold:
            return i + 1  # 返回等级 (1-7)
    
    # 如果 value 大于等于所有阈值，返回最高等级 8
    return 8

def calc_ship_rating(ship_data: list, server_data: list):
    # 计算PR
    # Step 1 - ratios:
    r_wins = ship_data[0] / server_data[0]
    r_dmg = ship_data[1] / server_data[1]
    r_frags = ship_data[2] / server_data[2]
    # Step 2 - normalization:
    n_wins = max(0, (r_wins - 0.7) / (1 - 0.7))
    n_dmg = max(0, (r_dmg - 0.4) / (1 - 0.4))
    n_frags = max(0, (r_frags - 0.1) / (1 - 0.1))
    # Step 3 - PR value:
    personal_rating = round(700 * n_dmg + 300 * n_frags + 150 * n_wins, 2)
    damage_rating = get_rating_level(r_dmg, 'damage')
    frags_rating = get_rating_level(r_frags, 'frags')
    return personal_rating, damage_rating, frags_rating

def calc_recent_diff(old_cache: dict, latest_data: dict):
    """
    计算每艘船的近期增量数据（最新 - 本地缓存）
    """
    diff_data = {}
    for ship_id, new_values in latest_data.items():
        old_values = old_cache.get(ship_id, [0]*len(new_values))
        ship_diff = [new_val - old_val for new_val, old_val in zip(new_values, old_values)]
        ship_diff[-2] = ship_diff[-2] * 100
        ship_diff[-1] = ship_diff[-1] * 1000
        if any(d < 0 for d in ship_diff):
            continue
        if ship_diff[0] == 0:
            continue
        diff_data[ship_id] = ship_diff
    return diff_data