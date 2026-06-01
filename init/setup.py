#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import json
import logging
import argparse
from pathlib import Path
from dotenv import load_dotenv


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

ROOT_DIR = Path(os.getcwd())

def log(step_text: str, symbol: str, width: int = 58):
    text_len = len(step_text)
    dots_count = max(width - text_len, 2)  # 最少 2 个点
    dots = "." * dots_count
    return f"{step_text}{dots}{symbol}"

if (ROOT_DIR / 'env.dev').exists():
    load_dotenv('env.dev')
    logger.info(log('Loaded environment file: env.dev', '✅'))
elif (ROOT_DIR / 'env.prod').exists():
    load_dotenv('env.prod')
    logger.info(log('Loaded environment file: env.pros', '✅'))
else:
    raise FileNotFoundError('No environment file found')

REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")

REGION_TIMEZONE = {'asia': 8, 'eu': 1, 'na': -7, 'ru': 3, 'cn': 8}

def main(region: str, location: str):
    # 生成redis配置文件
    file_path = ROOT_DIR / "redis.conf"
    if not file_path.exists():
        redis_conf = f"bind 0.0.0.0\nappendonly yes\nrequirepass {REDIS_PASSWORD}"
        file_path.write_text(redis_conf)
    logging.info(log('File `redis.conf` generated successfully', '✅'))
    
    # # 生成mysql配置文件
    # file_path = ROOT_DIR / f"my.cnf"
    # if not file_path.exists():
    #     redis_conf = "[mysqld]\ntransaction-isolation = READ-COMMITTED"
    #     file_path.write_text(redis_conf)
    # logging.info(log('File `my.cnf` generated successfully', '✅'))

    file_path = ROOT_DIR / 'data/const/constants.json'
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        SERVICE_LIST: list = data['SERVICE_LIST']

    # 确保文件路径存在
    dir_list = [
        ROOT_DIR / 'logs/error',
        ROOT_DIR / 'logs/exception',
        ROOT_DIR / 'logs/metrics',
        ROOT_DIR / 'logs/scripts',
        ROOT_DIR / 'data/db',
        ROOT_DIR / 'data/json',
        ROOT_DIR / 'data/trash',
    ]
    for dir_path in dir_list:
        os.makedirs(dir_path, exist_ok=True)

    # 生成空日志文件
    for service in SERVICE_LIST:
        log_path = ROOT_DIR / 'logs/scripts' / f'{service}.log'
        if not log_path.exists():
            with open(log_path, 'w'):
                pass
    
    # 生成工会战赛季信息文件
    init_file_path = ROOT_DIR / f"data/json/clan_season.json"
    if not init_file_path.exists():
        result = {
            "id": 28,
            "start": 1739944800,
            "finish": 1744005600
        }
        with open(init_file_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False)
    logging.info(log('File `clan_season.json` generated successfully', '✅'))

    # 生成初始化文件
    init_file_path = ROOT_DIR / f"data/json/init_marker.json"
    if not init_file_path.exists():
        result = {
            'init_time': int(time.time()),
            'region': region,
            'location': location,
            'timezone': REGION_TIMEZONE[region],
            'token': None
        }
        with open(init_file_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False)
    logging.info(log('File `init_marker.json` generated successfully', '✅'))

if __name__ == "__main__":
    # 加载参数并效验
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-r", "--region",
        type=str,
        required=True,
        help="API Token"
    )
    parser.add_argument(
        "-l", "--location",
        type=str,
        required=True,
        help="Location"
    )
    args = parser.parse_args()
    region = args.region
    location = args.location
    if region not in ['asia', 'eu', 'na', 'ru', 'cn']:
        raise ValueError('Incorrect region')
    main(
        region=region,
        location=location
    )
    print('----------  Initialization completed successfully  ----------')
