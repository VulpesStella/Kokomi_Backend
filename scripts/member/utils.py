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

def get_seconds_until_end_of_day() -> int:
    """计算从当前时刻到今天 23:59:59 剩余的秒数"""
    now = datetime.now(timezone.utc)
    end_of_day = now.replace(hour=23, minute=59, second=59, microsecond=0)
    return int((end_of_day - now).total_seconds())