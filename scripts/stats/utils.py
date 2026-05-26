from datetime import datetime, timezone

from settings import DATE_FMT


def get_formatted_date() -> str:
    """获取当前日期格式化字符串，用于日志输出"""
    return datetime.now().strftime(DATE_FMT)

def get_current_timestamp() -> int:
    """获取当前 UTC 时间的 int 类型时间戳（秒）"""
    return int(datetime.now(timezone.utc).timestamp())

def get_current_iso_time() -> str:
    """获取当前 UTC 时间的 ISO 格式字符串"""
    return datetime.now(timezone.utc).isoformat(timespec='seconds')

def calc_ship_rating(player_stats: list, benchmark_stats: list) -> float:
    """计算单艘船的个人 Rating

    Args:
        player_stats: 玩家该船的统计值，格式为 [win_rate, avg_damage, avg_frags]
        benchmark_stats: 服务器该船的平均统计值，格式为 [win_rate, avg_damage, avg_frags]

    Returns:
        计算得到的个人 Rating，若 benchmark_stats 为空则返回 -1
    """
    if not benchmark_stats:
        return -1
    # 计算相对比率
    r_wins = player_stats[0] / benchmark_stats[0]
    r_dmg = player_stats[1] / benchmark_stats[1]
    r_frags = player_stats[2] / benchmark_stats[2]

    # 归一化处理
    n_wins = max(0, (r_wins - 0.7) / 0.3)
    n_dmg = max(0, (r_dmg - 0.4) / 0.6)
    n_frags = max(0, (r_frags - 0.1) / 0.9)

    # 计算最终 PR
    personal_rating = round(700 * n_dmg + 300 * n_frags + 150 * n_wins, 2)

    return personal_rating