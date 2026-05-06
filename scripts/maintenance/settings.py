import os
import sys
import json
from pathlib import Path
from datetime import datetime


CLIENT_NAME = 'Maintenanse'
REFRESH_INTERVAL = 60
DATE_FMT = '%Y-%m-%d %H:%M:%S'
USE_TQDM = sys.stdout.isatty() # 只有在交互式终端中才使用tqdm显示进度条

BATCH_SIZE = 10000
STAGING_DELETE_DELAY_ENABLED = True  # 暂存数据是否延时删除

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

LOG_LEVEL = os.getenv("LOG_LEVEL")
LOG_DIR = Path(os.getenv("LOG_DIR"))
DATA_DIR = Path(os.getenv("DATA_DIR"))
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
    "db": 0,
    "password": os.getenv("REDIS_PASSWORD"),
    "decode_responses": True
}
RABBITMQ_CONFIG = {
    "host": os.getenv("RABBITMQ_HOST"),
    "user": os.getenv("RABBITMQ_DEFAULT_USER"),
    "password": os.getenv("RABBITMQ_DEFAULT_PASS")
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
    USER_INIT_TABLE_LIST: list = data['USER_INIT_TABLE_LIST']
    CLAN_INIT_TABLE_LIST: list = data['CLAN_INIT_TABLE_LIST']
print(f"{datetime.now().strftime(DATE_FMT)} [INIT] Configuration data loading complete")