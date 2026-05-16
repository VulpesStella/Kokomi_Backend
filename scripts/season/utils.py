"""
工具函数模块

提供时间戳转换、赛季配置读取和公会战活动窗口判断等工具函数。
"""

import json
from datetime import datetime, timezone, time

from settings import (
    REGION,
    DATA_DIR,
    DATE_FMT,
    CLAN_BATTLE_WINDOWS
)


def get_formatted_date() -> str:
    """获取当前日期格式化字符串，用于日志输出"""
    return datetime.now().strftime(DATE_FMT)

def get_current_timestamp() -> int:
    """获取当前 UTC 时间的 int 类型时间戳（秒）"""
    return int(datetime.now(timezone.utc).timestamp())

def get_current_iso_time() -> str:
    """获取当前 UTC 时间的 ISO 格式字符串"""
    return datetime.now(timezone.utc).isoformat(timespec='seconds')

def formtime_to_timestamp(formtime: str) -> int:
    """将 ISO 格式时间字符串转换为 Unix 时间戳"""
    return int(datetime.fromisoformat(formtime).timestamp())

def read_season_data() -> dict:
    """从本地 JSON 文件读取当前赛季配置数据"""
    # 俄服clan battle在s28后被rating战所替代
    # SEASON_ID, SEASON_FINISH, SEASON_START = 28, 1739944800, 1744005600
    file_path = DATA_DIR / f'json/clan_season.json'
    if not file_path.exists():
        return {"id": 0,"start": None,"finish": None}

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        return data

def refresh_season_data(season_id: int) -> dict:
    """刷新本地 JSON 文件中的当前赛季配置数据"""
    file_path = DATA_DIR / f'json/clan_season.json'
    data = {"id": season_id,"start": None,"finish": None}
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)

def is_cb_active(season_start: int, season_finish: int) -> bool:
    """判断当前时间是否处于公会战活跃窗口内

    Args:
        season_start: 赛季开始时间戳
        season_finish: 赛季结束时间戳

    Returns:
        是否在活跃窗口内
    """
    # 没有配置赛季时间区间
    if not season_start or not season_finish:
        return False

    # 当前时间戳
    now_ts = get_current_timestamp()

    # 判断是否处于赛季工会战的开启时间内
    if not (season_start <= now_ts <= season_finish):
        return False

    now = datetime.fromtimestamp(now_ts, tz=timezone.utc)
    weekday = now.weekday()
    current_time = now.time()

    for start, end, regions in CLAN_BATTLE_WINDOWS[weekday]:
        if time(start[0], start[1]) <= current_time < time(end[0], end[1] + 29):
            if REGION in regions:
                return True
    return False