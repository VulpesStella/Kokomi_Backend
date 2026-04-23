import os
import sys
import json
from pathlib import Path
from datetime import datetime


CLIENT_NAME = 'ClanSeason'
REFRESH_INTERVAL = 300
DATE_FMT = '%Y-%m-%d %H:%M:%S'
USE_TQDM = sys.stdout.isatty()

# 通过api获取season数据
# 更新SeasonID同时要创建对应的表
# https://developers.wargaming.net/reference/all/wows/clans/season/?language=en&r_realm=asia

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
REDIS_CONFIG = {
    "host": os.getenv("REDIS_HOST"),
    "port": int(os.getenv("REDIS_PORT", 6379)),
    "db": 0,
    "password": os.getenv("REDIS_PASSWORD"),
    "decode_responses": True
}

file_path = DATA_DIR / 'json/init_marker.json'
with open(file_path, "r", encoding="utf-8") as f:
    data = json.load(f)
    REGION: str = data['region']
file_path = DATA_DIR / 'const/endpoints.json'
with open(file_path, "r", encoding="utf-8") as f:
    data = json.load(f)
    CLAN_API: list = data[REGION]['clan_api']
file_path = DATA_DIR / 'const/constants.json'
with open(file_path, "r", encoding="utf-8") as f:
    data = json.load(f)
    CLAN_INIT_TABLE_LIST: list = data['CLAN_INIT_TABLE_LIST']
    CLAN_REALM_MAP: list = data['CLAN_REALM_MAP']
    CLAN_LEAGUE_LIST: list = data['CLAN_LEAGUE_LIST']
    CLAN_BATTLE_WINDOWS: list = data['CLAN_BATTLE_WINDOWS']
print(f"{datetime.now().strftime(DATE_FMT)} [INIT] Configuration data loading complete")