import os
import sys
import json
from pathlib import Path
from datetime import datetime


CLIENT_NAME = 'ServerStats'
REFRESH_INTERVAL = 21600
BATCH_SIZE = 1000
DATE_FMT = '%Y-%m-%d %H:%M:%S'
USE_TQDM = sys.stdout.isatty()

if os.getenv('PLATFORM') is None:
    from dotenv import load_dotenv
    load_result = load_dotenv('env.dev')
    print(f"{datetime.now().strftime(DATE_FMT)} [INIT] Env config loaded: env.dev")
else:
    print(f"{datetime.now().strftime(DATE_FMT)} [INIT] Env config loaded: env.prod")

LOG_LEVEL = os.getenv("LOG_LEVEL")
LOG_DIR = Path(os.getenv("LOG_DIR"))
DATA_DIR = Path(os.getenv("DATA_DIR"))
MYSQL_CONFIG = {
    "host": os.getenv("MYSQL_HOST"),
    "port": int(os.getenv("MYSQL_PORT", 3306)),
    "user": os.getenv("MYSQL_USER"),
    "password": os.getenv("MYSQL_PASSWORD"),
    "database": os.getenv("MYSQL_DATABASE"),
    "autocommit": False
}

file_path = DATA_DIR / 'json/init_marker.json'
with open(file_path, "r", encoding="utf-8") as f:
    data = json.load(f)
    REGION: str = data['region']
print(f"{datetime.now().strftime(DATE_FMT)} [INIT] Configuration data loading complete")