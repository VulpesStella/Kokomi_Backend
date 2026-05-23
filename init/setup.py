#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import json
import logging
import pymysql
import requests
import argparse
import traceback
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
DB_CONFIG = {
    "host": 'localhost',
    "port": int(os.getenv("MYSQL_PORT", 3306)),
    "user": 'root',
    "password": os.getenv("MYSQL_ROOT_PASSWORD"),
    "database": os.getenv("MYSQL_DATABASE"),
    'autocommit': False
}

DATA_DIR = Path(os.getenv("DATA_DIR"))
REGION_TIMEZONE = {'asia': 8, 'eu': 1, 'na': -7, 'ru': 3, 'cn': 8}

os.environ['NO_PROXY'] = '127.0.0.1,localhost'

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

    file_path = ROOT_DIR / 'data/const/endpoints.json'
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        VORTEX_API: list = data[region]['vortex_api']
    
    # 读取游戏版本
    base_url = VORTEX_API[0]
    url = f'{base_url}/api/v2/graphql/glossary/version/'
    body = [{"query":"query Version {\n  version\n}"}]
    resp = requests.post(url,json=body,timeout=5)
    if resp.status_code == 200:
        version_data = resp.json()
        full_version = version_data[0]['data']['version']
        short_version = ".".join(full_version.split(".")[:2])
        logging.info(log(f'Latest game version: {short_version}', '✅'))
        try:
            conn = pymysql.connect(**DB_CONFIG)
            with conn.cursor() as cursor:
                sql = """
                    INSERT INTO T_game_version (
                        is_latest, short_name, full_name
                    ) VALUES (
                        TRUE, %s, %s
                    );
                """
                cursor.execute(sql, [short_version, full_version])
            conn.commit()
        except Exception:
            conn.rollback()
            traceback.print_exc() 
        finally:
            conn.close() 
    else:
        logger.info(log(f'Request status code: {resp.status_code}', '❌️'))

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
