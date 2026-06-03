import pymysql
import redis
import requests
from dbutils.pooled_db import PooledDB

from .settings import REDIS_CONFIG, MYSQL_CONFIG, SSL_CA_BUNDLE


session = requests.Session()
if SSL_CA_BUNDLE:
    # 处理俄服接口证书效验问题
    session.verify= SSL_CA_BUNDLE

try:
    redis_client = redis.Redis(**REDIS_CONFIG)
    REDIS_CONFIG['db'] += 1
    lock_client = redis.Redis(**REDIS_CONFIG)
except:
    print('[ERROR] Failed to initialize the Redis connection')

try:
    db_pool = PooledDB(
        creator=pymysql,
        maxconnections=4,     # 最大连接数
        **MYSQL_CONFIG,
        charset="utf8mb4",
        autocommit=False      # 必须使用手动事务
    )
    print('[INIT] MySQL connection pool initialized')
except:
    print('[ERROR] Failed to initialize the MySQL connection')
