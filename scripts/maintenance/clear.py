import os
import redis
import logging
from pathlib import Path
from dotenv import load_dotenv


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

ROOT_DIR = Path(os.getcwd())

if (ROOT_DIR / 'env.dev').exists():
    load_dotenv('env.dev')
elif (ROOT_DIR / 'env.prod').exists():
    load_dotenv('env.prod')
else:
    raise FileNotFoundError('No environment file found')

REDIS_CONFIG = {
    "host": 'localhost',
    "port": int(os.getenv("REDIS_PORT", 6379)),
    "db": int(os.getenv("REDIS_DATABASE", 0)),
    "password": os.getenv("REDIS_PASSWORD"),
    "decode_responses": True
}

SCAN_BATCH_SIZE = 1000

def main():
    redis_client = redis.Redis(**REDIS_CONFIG)

    try:
        pattern = 'refresh_lock:user:*'
        logger.info(f"Scanning keys matching: {pattern}")

        cursor = 0
        deleted_count = 0

        while True:
            cursor, keys = redis_client.scan(cursor, match=pattern, count=SCAN_BATCH_SIZE)
            if keys:
                redis_client.delete(*keys)
                deleted_count += len(keys)
                logger.info(f"Deleted {len(keys)} keys, total: {deleted_count}")
            if cursor == 0:
                break

        logger.info(f"Done. Total keys deleted: {deleted_count}")
    finally:
        if redis_client:
            redis_client.close()


if __name__ == '__main__':
    """删除用户刷新的分布式锁

    运行前请确保所有子服务已停止运行，避免读取到异常数据或影响服务正常运行

    使用示例：
    python scripts/maintenance/clear.py
    """
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(e)