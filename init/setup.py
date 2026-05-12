#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import json
import pymysql
import requests
import argparse
import traceback
from pathlib import Path
from dotenv import load_dotenv


def log(step_text: str, symbol: str, width: int = 58):
    text_len = len(step_text)
    dots_count = max(width - text_len, 2)  # 最少 2 个点
    dots = "." * dots_count
    print(f"{step_text}{dots}{symbol}")

def main(region: str, env_file: str):
    # 加载配置文件
    log('1. Read environment configuration file ', '🛠️')
    ROOT_DIR = Path(__file__).resolve().parent.parent
    load_dotenv(ROOT_DIR / env_file)
    if os.getenv('PLATFORM') is None:
        log(f'  - {env_file} file reading failed ', '❌')
        return
    MYSQL_CONFIG = {
        "host": "127.0.0.1",
        "port": 3306,
        "user": "root",
        "password": os.getenv("MYSQL_ROOT_PASSWORD"),
        "autocommit": False
    }
    DATABASE = os.getenv("MYSQL_DATABASE")
    REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")
    REGION_TIMEZONE = {
        'asia': 8, 
        'eu': 1, 
        'na': -7, 
        'ru': 3, 
        'cn': 8
    }
    log(f'  - {env_file} file read successfully ', '✅')

    # # 生成redis配置文件
    # file_path = ROOT_DIR / "redis.conf"
    # if not file_path.exists():
    #     redis_conf = f"bind 0.0.0.0\nappendonly yes\nrequirepass {REDIS_PASSWORD}"
    #     file_path.write_text(redis_conf)
    # log(f'  - redis.conf file generated successfully ', '✅')
    
    # # 生成mysql配置文件
    # file_path = ROOT_DIR / f"my.cnf"
    # if not file_path.exists():
    #     redis_conf = "[mysqld]\ntransaction-isolation = READ-COMMITTED"
    #     file_path.write_text(redis_conf)
    # log(f'  - my.cnf file generated successfully ', '✅')

    file_path = ROOT_DIR / 'data/const/endpoints.json'
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        VORTEX_API: list = data[region]['vortex_api']

    # 执行数据库初始化
    log('3. Initialize MySQL database ', '🛠️')
    conn = pymysql.connect(**MYSQL_CONFIG)
    try:
        with conn.cursor() as cursor:
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{DATABASE}`;")
            cursor.execute(f"USE `{DATABASE}`;")
            sql_files = [
                ROOT_DIR / "init/mysql/01-schemas/01-base.sql",
                ROOT_DIR / "init/mysql/01-schemas/02-user.sql",
                ROOT_DIR / "init/mysql/01-schemas/03-clan.sql",
                ROOT_DIR / "init/mysql/01-schemas/04-ship.sql",
                ROOT_DIR / "init/mysql/01-schemas/05-recent.sql",
                ROOT_DIR / "init/mysql/02-data/01-base.sql",
                ROOT_DIR / "init/mysql/03-views/01-base.sql",
                ROOT_DIR / "init/mysql/04-functions/01-base.sql"
            ]
            for sql_file in sql_files:
                with sql_file.open("r", encoding="utf-8") as f:
                    sql = f.read()
                    cursor.execute(sql)
        conn.commit()
    except Exception:
        conn.rollback()
        traceback.print_exc()  
        return 

    
    # 读取游戏版本
    base_url = VORTEX_API[0]
    url = f'{base_url}/api/v2/graphql/glossary/version/'
    body = [{"query":"query Version {\n  version\n}"}]
    resp = requests.post(url,json=body,timeout=5)
    if resp.status_code == 200:
        version_data = resp.json()
        full_version = version_data[0]['data']['version']
        log(f'  - Game version readed successfully ', '✅')
        short_version = ".".join(full_version.split(".")[:2])
        
        try:
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
    else:
        resp.raise_for_status()

    conn.close()

    # # 生成初始化文件
    # result = {
    #     'init_time': int(time.time()),
    #     'region': region,
    #     'location': '-',
    #     'timezone': REGION_TIMEZONE[region],
    #     'token': None
    # }
    # hash_value = hash(frozenset(result.items()))
    # result['hash'] = hash_value
    # init_file_path = ROOT_DIR / f"data/json/init_marker.json"
    # with open(init_file_path, "w", encoding="utf-8") as f:
    #     json.dump(result, f, ensure_ascii=False)
    # log(f'4. init_marker.json file generated successfully ', '✅')

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
        "-e", "--env",
        type=str,
        required=True,
        help="Env File"
    )
    args = parser.parse_args()
    region = args.region
    env = args.env
    if region not in ['asia', 'eu', 'na', 'ru', 'cn']:
        raise ValueError('Incorrect region')
    if env not in ['.env', 'env.dev', 'env.prod']:
        raise ValueError('Incorrect env file')
    main(
        region=region,
        env_file=env
    )
    print('----------  Initialization completed successfully  ----------')
