import time
from functools import wraps
from datetime import datetime, timezone

from app.core import EnvConfig, api_logger


SERVER_RESET_OFFSET = 5

class TimeUtils:
    """时间相关工具函数集合"""
    @staticmethod
    def timestamp() -> int:
        """
        获取当前 UTC 时间戳（秒）
        """
        return int(datetime.now(timezone.utc).timestamp())

    @staticmethod
    def timestamp_ms() -> int:
        """
        获取当前 UTC 时间戳（毫秒）
        """
        return int(datetime.now(timezone.utc).timestamp() * 1000)
    
    def now_iso() -> str:
        """
        获取指定时区的当前时间（ISO 8601 格式，默认当前时区）
        """
        return datetime.now(timezone.utc).isoformat(timespec="seconds")
    
    def fromtimestamp(timestamp: int, strftime: str = "%Y-%m-%d %H:%M:%S"):
        """
        获取指定时间戳的UTC时间（默认 %Y-%m-%d %H:%M:%S 格式）
        """
        if timestamp is None:
            return None
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime(strftime)
    
    def get_recent_date(current_timestamp: int) -> int:
        """获取Recent服务重置日期"""
        reset_timestamp = current_timestamp + EnvConfig.TIMEZORE * 3600 - SERVER_RESET_OFFSET * 3600
        strftime = datetime.fromtimestamp(reset_timestamp, timezone.utc).strftime("%Y%m%d")
        return int(strftime)
    
    def calu_time_diff(timestamp):
        """
        计算当前时间与输入时间戳的差值
        """
        current = time.time()
        if timestamp < current:
            return '-1'
        diff = timestamp - current
        days = int(diff // 86400)
        hours = int((diff % 86400) // 3600)
        minutes = int((diff % 3600) // 60)
        seconds = int(diff % 60)
        if days != 0:
            return f"{days}d {hours}h {minutes}m {seconds}s"
        else:
            return f"{hours}h {minutes}m {seconds}s"

    def async_timing(func):
        """
        测试异步函数运行时间的装饰器
        """
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start = time.time()
            result = await func(*args, **kwargs)
            end = time.time()
            api_logger.info(f"[Timing] {func.__name__} Cost: {end - start:.6f} s")
            return result
        return async_wrapper

    def sync_timing(func):
        """
        测试同步函数运行时间的装饰器
        """
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start = time.time()
            result = func(*args, **kwargs)
            end = time.time()
            api_logger.info(f"[Timing] {func.__name__} Cost: {end - start:.6f} s")
            return result
        return sync_wrapper

