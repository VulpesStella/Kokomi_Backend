import csv
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from app.core import EnvConfig
from app.middlewares import RedisClient


class ServiceMetrics:
    async def requests_incr(key: str, date: str):
        await RedisClient.incr(f"metrics:{key}:{date}")

    async def http_incrby(date: str, amount: int):
        await RedisClient.incrby(f"metrics:http_total:{date}", amount)

    async def http_error_incrby(date: str, amount: int):
        await RedisClient.incrby(f"metrics:http_error:{date}", amount)
    
    @staticmethod
    def collect_today_hourly_metrics():
        now = datetime.now(timezone.utc)
        today = now.date()
        total_count = 0
        total_elapsed_ms = 0
        # 初始化桶
        buckets = defaultdict(int)
        # buckets = defaultdict(lambda: {"value1": 0, "value2": 0})
        file = EnvConfig.LOG_DIR / f"metrics/{today.isoformat()}.csv"
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
        keys = []
        values = []
        current_hour = now.replace(minute=0, second=0, microsecond=0)
        for hour in range(24):
            hour_time = now.replace(hour=hour, minute=0, second=0, microsecond=0)
            key = hour_time.strftime("%H:00")
            keys.append(key)
            if hour_time > current_hour:
                values.append(None)
            else:
                values.append(buckets.get(key, 0))
        error_count = 0
        file =  EnvConfig.LOG_DIR / f"error/{today.isoformat()}.txt" 
        if file.exists():
            with open(file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith('>Platform:'):
                        error_count += 1
        return {
            "summary":{
                "total_requests": total_count,
                "total_errors": error_count,
                "elapsed_ms": 0 if total_count == 0 else int(total_elapsed_ms/total_count)
            },
            "hourly": {
                "keys": keys,
                "series":[
                        {
                        "name": "resquest",
                        "type": "bar",
                        "data": values
                    }
                ]
            }
        }
    
    @staticmethod
    async def collect_api_metrics():
        now = datetime.now(timezone.utc)
        keys = []
        for i in range(30, 0, -1):
            day = now - timedelta(days=i)
            keys.append(day.date().isoformat())
        values = await RedisClient.get_by_pipe("metrics:api:key", keys)
        if values['code'] != 1000:
            values = [None * 30]
        else:
            values = values['data']
        return {
            "keys": keys,
            "series":[
                    {
                    "name": "resquest",
                    "type": "bar",
                    "data": values
                }
            ]
        }
    
    @staticmethod
    async def collect_celery_metrics():
        now = datetime.now()
        keys = []
        for i in range(30, 0, -1):
            day = now - timedelta(days=i)
            keys.append(day.date().isoformat())
        values = await RedisClient.get_by_pipe("metrics:celery:key", keys)
        if values['code'] != 1000:
            values = [None * 30]
        else:
            values = values['data']
        return {
            "keys": keys,
            "series":[
                    {
                    "name": "resquest",
                    "type": "bar",
                    "data": values
                }
            ]
        }
    
    @staticmethod
    async def collect_http_metrics():
        now = datetime.now()
        today_count = [0,0]
        keys = ['http_total','http_error']
        values = await RedisClient.get_by_pipe(f"metrics:key:{now.date().isoformat()}", keys)
        if values['code'] == 1000:
            values = values['data']
            today_count[0] = values[0]
            today_count[1] = values[1]
        return today_count