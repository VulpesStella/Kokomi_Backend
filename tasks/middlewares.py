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
    redis_client = redis.Redis(
        host=REDIS_CONFIG['host'],
        port=REDIS_CONFIG['port'],
        db=0,
        password=REDIS_CONFIG['password'],
        decode_responses=True  # 返回 str 而不是 bytes
    )
except:
    print('[ERROR] Failed to initialize the Redis connection')

try:
    db_pool = PooledDB(
        creator=pymysql,
        maxconnections=6,     # 最大连接数
        host=MYSQL_CONFIG['host'],
        port=MYSQL_CONFIG['port'],
        user=MYSQL_CONFIG['user'],
        password=MYSQL_CONFIG['password'],
        database=MYSQL_CONFIG['database'],
        charset="utf8mb4",
        autocommit=False      # 必须使用手动事务
    )
    print('[INIT] MySQL connection pool initialized')
except:
    print('[ERROR] Failed to initialize the MySQL connection')
