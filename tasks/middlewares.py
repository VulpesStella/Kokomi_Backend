import pymysql
import redis
from dbutils.pooled_db import PooledDB
from celery.app.base import logger

from .settings import REDIS_CONFIG, MYSQL_CONFIG


try:
    redis_client = redis.Redis(
        host=REDIS_CONFIG['host'],
        port=REDIS_CONFIG['port'],
        db=0,
        password=REDIS_CONFIG['password'],
        decode_responses=True  # 返回 str 而不是 bytes
    )
except:
    logger.error(msg='Failed to initialize the Redis connection')

try:
    db_pool = PooledDB(
        creator=pymysql,
        maxconnections=5,     # 最大连接数
        mincached=1,           # 初始化时创建的连接
        maxcached=2,           # 池中最大空闲连接
        blocking=True,         # 连接用完是否阻塞
        host=MYSQL_CONFIG['host'],
        port=MYSQL_CONFIG['port'],
        user=MYSQL_CONFIG['user'],
        password=MYSQL_CONFIG['password'],
        charset="utf8mb4",
        autocommit=False,
        database=MYSQL_CONFIG['database']
    )
except:
    logger.error(msg='Failed to initialize the MySQL connection')
