import os
import sys
import json
from pathlib import Path
from datetime import datetime


CLIENT_NAME = 'UserCache'
REFRESH_INTERVAL = 600
MAX_REFRESH_BATCH = 2000
DATE_FMT = '%Y-%m-%d %H:%M:%S'
USE_TQDM = sys.stdout.isatty() # 只有在交互式终端中才使用tqdm显示进度条

ROOT_DIR = Path(os.getcwd())
LOG_DIR = ROOT_DIR / 'logs'
DATA_DIR = ROOT_DIR / 'data'

# 生产环境下的环境变量由Docker Compose注入env.prod，开发环境下则通过加载env.dev文件来设置
if not os.getenv('PLATFORM') or not os.getenv('PLATFORM').startswith('KokomiAPI'):
    # 关闭代理，避免请求外部API时被本地环境变量干扰
    os.environ['NO_PROXY'] = '127.0.0.1,localhost'
    from dotenv import load_dotenv
    if not load_dotenv('env.dev'):
        # 开发环境下如果加载env.dev失败，直接退出程序
        print(f"{datetime.now().strftime(DATE_FMT)} [ERROR] Failed to load env.dev configuration")
        exit(1)
    print(f"{datetime.now().strftime(DATE_FMT)} [INIT] Env config loaded: env.dev")
else:
    print(f"{datetime.now().strftime(DATE_FMT)} [INIT] Env config loaded: env.prod")

SSL_CA_BUNDLE = os.getenv("SSL_CA_BUNDLE")
MAIN_NODE_URL = os.getenv("MAIN_NODE_URL")
MAIN_NODE_TOKEN = os.getenv("MAIN_NODE_TOKEN")
LOG_LEVEL = os.getenv("LOG_LEVEL")
MYSQL_CONFIG = {
    "host": os.getenv("MYSQL_HOST"),
    "port": int(os.getenv("MYSQL_PORT", 3306)),
    "user": os.getenv("MYSQL_USER"),
    "password": os.getenv("MYSQL_PASSWORD"),
    "database": os.getenv("MYSQL_DATABASE"),
    "autocommit": False  # 关闭自动提交，改为手动控制事务，以便在发生异常时能正确回滚，保证数据一致性
}
REDIS_CONFIG = {
    "host": os.getenv("REDIS_HOST"),
    "port": int(os.getenv("REDIS_PORT", 6379)),
    "db": int(os.getenv("REDIS_DATABASE", 0)),
    "password": os.getenv("REDIS_PASSWORD"),
    "decode_responses": True
}

# 因为是运行必要数据，故不处理可能存在的文件加载异常
# 确保在文件缺失或格式错误时能直接raise并停止服务，避免进入不稳定状态
file_path = DATA_DIR / 'json/init_marker.json'
with open(file_path, "r", encoding="utf-8") as f:
    data = json.load(f)
    REGION: str = data['region']
file_path = DATA_DIR / 'const/endpoints.json'
with open(file_path, "r", encoding="utf-8") as f:
    data = json.load(f)
    VORTEX_API: list = data[REGION]['vortex_api']
file_path = DATA_DIR / 'const/constants.json'
with open(file_path, "r", encoding="utf-8") as f:
    data = json.load(f)
    SHIP_METRIC_MAP: dict = data['SHIP_METRIC_MAP']
    USER_ACTIVITY_THRESHOLDS: list = data['USER_ACTIVITY_THRESHOLDS']
    METRIC_RATING_THRESHOLDS: list = data['METRIC_RATING_THRESHOLDS']

METRIC_ID_TO_INDEX = {
    SHIP_METRIC_MAP['exp']: 0,
    SHIP_METRIC_MAP['frags']: 1,
    SHIP_METRIC_MAP['planes']: 2,
    SHIP_METRIC_MAP['damage']: 3,
    SHIP_METRIC_MAP['scouting_dmg']: 4,
    SHIP_METRIC_MAP['potential_dmg']: 5
}
# 反向映射，方便从索引取 metric_id
INDEX_TO_METRIC_ID = {v: k for k, v in METRIC_ID_TO_INDEX.items()}

print(f"{datetime.now().strftime(DATE_FMT)} [INIT] Configuration data loading complete")