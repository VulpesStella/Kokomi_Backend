import os
from pathlib import Path
from datetime import datetime


CLIENT_NAME = 'SchedulerCache'
LOG_LEVEL = 'debug'
REFRESH_INTERVAL = 3600
BATCH_SIZE = 1000
DATE_FMT = '%Y-%m-%d %H:%M:%S'

if os.getenv('PLATFORM') is None:
    from dotenv import load_dotenv
    load_result = load_dotenv('.env.dev')
    print(f"{datetime.now().strftime(DATE_FMT)} [INIT] Env config loaded: .env.dev")
else:
    print(f"{datetime.now().strftime(DATE_FMT)} [INIT] Env config loaded: .env.prod")

LOG_DIR = Path(os.getenv("LOG_DIR"))
DATA_DIR = Path(os.getenv("DATA_DIR"))
MYSQL_CONFIG = {
    "host": os.getenv("MYSQL_HOST"),
    "port": int(os.getenv("MYSQL_PORT", 3306)),
    "user": os.getenv("MYSQL_USERNAME"),
    "password": os.getenv("MYSQL_PASSWORD"),
    "database": os.getenv("MYSQL_DATABASE"),
    "autocommit": False
}
REDIS_CONFIG = {
    "host": os.getenv("REDIS_HOST"),
    "port": int(os.getenv("REDIS_PORT", 6379)),
    "db": 0,
    "password": os.getenv("REDIS_PASSWORD"),
    "decode_responses": True
}