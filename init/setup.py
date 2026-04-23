#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import csv
import time
import json
import pymysql
import requests
import argparse
import traceback
from pathlib import Path
from dotenv import load_dotenv


HOUR: int = 60 * 60
HALF_HOUR: int = 30*60
DAY: int = 24 * HOUR
api_config = {
    'TOP_N_LIMIT': 50,
    # 工会内用户数据刷新间隔
    'CLAN_REFRESH_INTERVAL': 6 * HOUR,
    # 用户缓存刷新间隔
    'USER_REFRESH_INTERVAL': {
        # 普通用户  | recent用户  | recents用户
        0: (5 * DAY,  6 * HOUR,   2 * HOUR),
        1: (25 * DAY, 12 * HOUR,  2 * HOUR),
        2: (1 * DAY,  HALF_HOUR,  20 * 60),
        3: (2 * DAY,  1 * HOUR,   25 * 60),
        4: (3 * DAY,  2 * HOUR,   30 * 60),
        5: (5 * DAY,  3 * HOUR,   30 * 60),
        6: (7 * DAY,  4 * HOUR,   1 * HOUR),
        7: (15 * DAY, 5 * HOUR,   2 * HOUR),
        8: (20 * DAY, 6 * HOUR,   2 * HOUR),
        9: (30 * DAY, 12 * HOUR,  2 * HOUR)
    },
    'BATTLES_LIMIT': {6: 40, 7: 40,8: 40, 9: 50,10: 60, 11: 60},
    'TIME_DIFFERENCES': [
        (1 * 24 * 60 * 60, 2),
        (3 * 24 * 60 * 60, 3),
        (7 * 24 * 60 * 60, 4),
        (30 * 24 * 60 * 60, 5),
        (90 * 24 * 60 * 60, 6),
        (180 * 24 * 60 * 60, 7),
        (365 * 24 * 60 * 60, 8)
    ],
    'OLD_SHIP_ID_LIST': [
        '4281317360','4285511376','4181112624','4292851408','4283414224',
        '3763320816','4289607376','4292851696','4277057520','4181603792',
        '4184749520','4179015472','4284364496','4183209776','4287543280',
        '4180555216','4181112816','3762272240','3762272048','4284463088',
        '4290754544','4184782288','4277122768','4183209968','4280203248',
        '4288657392','4288657104','4288558800','4179015664','4282300400',
        '4183700944','4282365648','4279220208','3763320528','4287510224',
        '4282365936','4279219920'
    ],
    'FIELD_COLOR_INDEX': [
        # [wr, dmg, frag, pr, sr]
        [40, 45, 50, 52.5, 55, 60, 67],
        [0.8, 0.95, 1.0, 1.1, 1.2, 1.4, 1.7],
        [0.2, 0.3, 0.6, 1.0, 1.3, 1.5, 2],
        [750, 1100, 1350, 1550, 1750, 2100, 2450],
        [10, 30, 40, 50, 60, 70, 80]
    ]
}


def log(step_text: str, symbol: str, width: int = 58):
    text_len = len(step_text)
    dots_count = max(width - text_len, 2)  # 最少 2 个点
    dots = "." * dots_count
    print(f"{step_text}{dots}{symbol}")

def exec_sql_file(cursor, file_path: Path):
    with file_path.open("r", encoding="utf-8") as f:
        sql = f.read()
    for statement in sql.split(";"):
        stmt = statement.strip()
        if stmt:
            try:
                cursor.execute(stmt)
            except Exception as e:
                print(stmt)
                raise e
    log(f"  - Executing {file_path.name} ", '✅')

def main(region: str, env_file: str):
    # 加载配置文件
    log('1. Read environment configuration file ', '🛠️')
    ROOT_DIR = Path(__file__).resolve().parent.parent
    load_dotenv(ROOT_DIR / env_file)
    # if os.getenv('PLATFORM') is None:
    #     log(f'  - {env_file} file reading failed ', '❌')
    #     return
    # MYSQL_CONFIG = {
    #     "host": "127.0.0.1",
    #     "port": 3306,
    #     "user": "root",
    #     "password": os.getenv("MYSQL_ROOT_PASSWORD"),
    #     "autocommit": False
    # }
    # DATABASE = os.getenv("MYSQL_DATABASE")
    # REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")
    # WG_API_TOKEN = os.getenv("WG_API_TOKEN")
    # LESTA_API_TOKEN = os.getenv("LESTA_API_TOKEN")
    # REGION_TIMEZONE = {
    #     'asia': 8, 
    #     'eu': 1, 
    #     'na': -7, 
    #     'ru': 3, 
    #     'cn': 8
    # }
    # log(f'  - {env_file} file read successfully ', '✅')

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

    # # 加载游戏api地址、代理策略和令牌
    # log('2. Loading game data ', '🛠️')
    # # 加载船只数据
    # if region == 'ru':
    #     csv_file_path = ROOT_DIR / "init/data/ship_name_lesta.csv"
    # else:
    #     csv_file_path = ROOT_DIR / "init/data/ship_name_wg.csv"
    # result = {}
    # with open(csv_file_path, newline="", encoding="utf-8-sig") as csvfile:
    #     reader = csv.DictReader(csvfile)
    #     for row in reader:
    #         ship_id = row['ship_id']
    #         premium = row.get("premium", "0") == "1"
    #         special = row.get("special", "0") == "1"
    #         verify = row.get("verify", "0") == "1"
    #         rarity = row.get("rarity")
    #         translations = {
    #             "en": {
    #                 "short": row.get("en_short"),
    #                 "full": row.get("en_full")
    #             },
    #             "zh": {
    #                 "cn": row.get("zh_cn"),
    #                 "sg": row.get("zh_sg"),
    #                 "tw": row.get("zh_tw")
    #             },
    #             "ja": row.get("ja"),
    #             "ru": row.get("ru")
    #         }
    #         ship_data = {
    #             "tier": int(row.get("tier", 0)),
    #             "type": row.get("type"),
    #             "nation": row.get("nation"),
    #             "premium": premium,
    #             "special": special,
    #             "rarity": rarity,
    #             "index": row.get("index"),
    #             "verify": verify,
    #             "name": translations
    #         }
    #         result[ship_id] = ship_data
    # file_path = ROOT_DIR / "data/json/ship_name.json"
    # with open(file_path, "w", encoding="utf-8") as f:
    #     json.dump(result, f, ensure_ascii=False)
    # log(f'  - ship_name.json file generated successfully ', '✅')
    # file_path = ROOT_DIR / "data/json/ship_data.json"
    # if not file_path.exists():
    #     with open(file_path, "w", encoding="utf-8") as f:
    #         json.dump({"update_time": int(time.time()), "ship_data": {}}, f, ensure_ascii=False)
    # log(f'  - ship_data.json file generated successfully ', '✅')

    # # 读取游戏版本
    # base_url = endpoints['vortex_api'][0]
    # url = f'{base_url}/api/v2/graphql/glossary/version/'
    # body = [{"query":"query Version {\n  version\n}"}]
    # resp = requests.post(url,json=body,timeout=5)
    # if resp.status_code == 200:
    #     version_data = resp.json()
    #     full_version = version_data[0]['data']['version']
    #     log(f'  - Game version readed successfully ', '✅')
    #     short_version = ".".join(full_version.split(".")[:2])
    #     file_path = ROOT_DIR / f"data/json/game_version.json"
    #     with open(file_path, "w", encoding="utf-8") as f:
    #         json.dump({'update_time': int(time.time()), 'short': short_version, 'full': full_version, 'start': int(time.time())}, f, ensure_ascii=False)
    #     log(f'  - version.json file generated successfully ', '✅')
    # else:
    #     resp.raise_for_status()

    # # 执行数据库初始化
    # log('3. Initialize MySQL database ', '🛠️')
    # sql_files = [
    #     ROOT_DIR / "init/mysql/01-schema.sql"
    # ]
    # for f in sql_files:
    #     if not f.exists():
    #         print(f"Missing SQL file: {f}")
    #         return
    # conn = pymysql.connect(**MYSQL_CONFIG)
    # try:
    #     with conn.cursor() as cursor:
    #         cursor.execute(f"CREATE DATABASE `{DATABASE}`;")
    #         cursor.execute(f"USE `{DATABASE}`;")
    #         for sql_file in sql_files:
    #             exec_sql_file(cursor, sql_file)
    #     conn.commit()
    # except Exception:
    #     conn.rollback()
    #     traceback.print_exc()   
    # finally:
    #     conn.close()

    # # 生成初始化文件
    # result = {
    #     'init_time': int(time.time()),
    #     'region': region,
    #     'token': None,
    #     'timezone': REGION_TIMEZONE[region]
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
