"""
全局配置模块

负责加载环境变量（开发环境从 env.dev 文件，生产环境由 Docker Compose 注入），
初始化 MySQL / Redis 连接配置以及统计聚合所需的各项参数常量。
所有模块级变量在 import 时即完成初始化，加载失败会直接 exit(1)。
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime


CLIENT_NAME = 'ServerStats'
REFRESH_INTERVAL = 3600
DATE_FMT = '%Y-%m-%d %H:%M:%S'
USE_TQDM = sys.stdout.isatty() # 只有在交互式终端中才使用tqdm显示进度条

BATCH_SIZE = 1000
BUCKETS = 400  # 直方图桶数
MIN_SAMPLES = 200  # Rating 统计最低限制

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
    "db": int(os.getenv("REDIS_DATABASE", 0)),
    "password": os.getenv("REDIS_PASSWORD"),
    "decode_responses": True
}

# 因为是运行必要数据，故不处理可能存在的文件加载异常
# 确保在文件缺失或格式错误时能直接 raise 并停止服务，避免进入不稳定状态
marker_file_path = DATA_DIR / 'json/init_marker.json'
with open(marker_file_path, "r", encoding="utf-8") as f:
    data = json.load(f)
    REGION: str = data['region']
constants_file_path = DATA_DIR / 'const/constants.json'
with open(constants_file_path, "r", encoding="utf-8") as f:
    data = json.load(f)
    SHIP_METRIC_MAP: dict[str, int] = data['SHIP_METRIC_MAP']
print(f"{datetime.now().strftime(DATE_FMT)} [INIT] Configuration data loading complete")