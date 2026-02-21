import os
import json
from pathlib import Path
from datetime import datetime


CLIENT_NAME = 'Recent'
REFRESH_INTERVAL = 60
BATCH_SIZE = 1000
DATE_FMT = '%Y-%m-%d %H:%M:%S'
if os.getenv('PLATFORM') is None:
    from dotenv import load_dotenv
    load_result = load_dotenv('.env.dev')
    print(f"{datetime.now().strftime(DATE_FMT)} [INIT] Env config loaded: .env.dev")
else:
    print(f"{datetime.now().strftime(DATE_FMT)} [INIT] Env config loaded: .env.prod")

LOG_LEVEL = os.getenv("LOG_LEVEL")
LOG_DIR = Path(os.getenv("LOG_DIR"))
DATA_DIR = Path(os.getenv("DATA_DIR"))
if os.getenv("SQLITE_PATH") == "default":
    SQLITE_PATH = DATA_DIR / 'db'
else:
    SQLITE_PATH = Path(os.getenv("SQLITE_PATH"))
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
WG_API_TOKEN = os.getenv("WG_API_TOKEN")
LESTA_API_TOKEN = os.getenv("LESTA_API_TOKEN")

file_path = DATA_DIR / 'json/init_marker.json'
with open(file_path, "r", encoding="utf-8") as f:
    data = json.load(f)
    REGION: str = data['region']
    TIMEZOEN: int = data['timezone']
    print(f"{datetime.now().strftime(DATE_FMT)} [INIT] Init config loaded: init_marker.json")
file_path = DATA_DIR / 'json/endpoints.json'
with open(file_path, "r", encoding="utf-8") as f:
    data = json.load(f)
    VORTEX_API: list = data['vortex_api']
    OFFICIAL_API: str = data['official_api']