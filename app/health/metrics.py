import csv
import httpx
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Tuple

from app.middlewares import RedisClient


class ServiceMetrics:
    async def requests_incr(key: str, date: str):
        await RedisClient.incr(f"metrics:{key}:{date}")

    async def http_incrby(date: str, amount: int):
        await RedisClient.incrby(f"metrics:http_total:{date}", amount)

    async def http_error_incrby(date: str, amount: int):
        await RedisClient.incrby(f"metrics:http_error:{date}", amount)

    @staticmethod
    def get_hourly_request_stats(today, log_dir) -> Tuple[int, Dict[str, int], int]:
        """统计过去24h的请求数据
        Returns:
            total_count: 总请求数
            buckets: 按小时分组的请求数 { "08:00": 100, ... }
            avg_elapsed_ms: 平均响应时间(ms)
        """
        total_count = 0
        total_elapsed_ms = 0
        buckets = defaultdict(int)
        
        file = log_dir / f"metrics/{today.isoformat()}.csv"
        if file.exists():
            with open(file, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        ts = datetime.fromisoformat(row["timestamp"])
                        es = int(row["elapsed_ms"])
                    except Exception:
                        continue
                    if ts.date() != today:
                        continue
                    hour_key = ts.strftime("%H:00")
                    buckets[hour_key] += 1
                    total_count += 1
                    total_elapsed_ms += es
        
        avg_elapsed_ms = 0 if total_count == 0 else int(total_elapsed_ms / total_count)
        return total_count, buckets, avg_elapsed_ms

    @staticmethod
    def build_hourly_chart_data(now, buckets: Dict[str, int]) -> Tuple[List[str], List[Any]]:
        """构建过去24h图表数据
        
        Returns:
            hourly_keys: 小时标签列表 ["00:00", "01:00", ...]
            hourly_values: 对应的请求数，未来时间为None
        """
        hourly_keys = []
        hourly_values = []
        current_hour = now.replace(minute=0, second=0, microsecond=0)

        for hour in range(24):
            hour_time = now.replace(hour=hour, minute=0, second=0, microsecond=0)
            key = hour_time.strftime("%H:00")
            hourly_keys.append(key)
            if hour_time > current_hour:
                hourly_values.append(None)
            else:
                hourly_values.append(buckets.get(key, 0))
        
        return hourly_keys, hourly_values

    @staticmethod
    async def get_monthly_api_stats(now) -> Tuple[List[str], List[Any]]:
        """获取过去30d API调用统计数据
        Returns:
            monthly_keys: 日期标签列表
            monthly_values: 对应的API调用数
        """
        monthly_keys = []
        monthly_redis_keys = []
        
        for i in range(30, -1, -1):
            day = now - timedelta(days=i)
            monthly_keys.append(day.date().isoformat())
            monthly_redis_keys.append(f"metrics:api:{day.date().isoformat()}")
        
        values = await RedisClient.get_by_pipe(monthly_redis_keys)
        if values['code'] != 1000:
            monthly_values = [None] * 31
        else:
            monthly_values = values['data']
        
        return monthly_keys, monthly_values

    @staticmethod
    async def get_monthly_celery_stats(now) -> Tuple[List[str], List[Any]]:
        """获取过去30d Celery任务消费统计数据
        Returns:
            celery_keys: 日期标签列表
            celery_values: 对应的任务数
        """
        celery_keys = []
        celery_redis_keys = []
        
        for i in range(30, -1, -1):
            day = now - timedelta(days=i)
            celery_keys.append(day.date().isoformat())
            celery_redis_keys.append(f"metrics:celery:{day.date().isoformat()}")
        
        values = await RedisClient.get_by_pipe(celery_redis_keys)
        if values['code'] != 1000:
            celery_values = [None] * 31
        else:
            celery_values = values['data']
        
        return celery_keys, celery_values

    @staticmethod
    def get_today_error_count(today, log_dir) -> int:
        """统计今日错误日志数"""
        error_count = 0
        file = log_dir / f"error/{today.isoformat()}.txt"
        
        if file.exists():
            with open(file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith('>Platform:'):
                        error_count += 1
        
        return error_count

    @staticmethod
    def get_mq_pending_count(config) -> int:
        """获取MQ待处理消息数"""
        url = f'http://{config.RABBITMQ.host}:15672/api'
        client = httpx.Client(
            base_url=url,
            auth=(config.RABBITMQ.username, config.RABBITMQ.password),
            timeout=2,
            trust_env=False
        )
        
        try:
            resp = client.get('/queues/%2F/refresh_queue')
            if resp.status_code == 200:
                result = resp.json()
                return result.get('messages', 0)
        except Exception:
            pass
        finally:
            client.close()
        
        return -1

    @staticmethod
    async def get_services_status() -> Tuple[int, int]:
        """获取服务状态
        Returns:
            active_count: 活跃服务数
            total_count: 总服务数
        """
        active_count = 0
        services = ['UserCache', 'Maintenanse', 'ClanSeason', 'ServerStats']
        for service in services:
            key = f'status:{service}'
            exists = await RedisClient.exists(key)
            if exists['code'] == 1000 and exists['data']:
                active_count += 1
        return active_count, len(services)