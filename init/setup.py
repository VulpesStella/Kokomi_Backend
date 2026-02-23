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


ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / '.env.prod')
MYSQL_CONFIG = {
    "host": "127.0.0.1",
    "port": 3306,
    "user": os.getenv("MYSQL_USERNAME"),
    "password": os.getenv("MYSQL_PASSWORD"),
    "autocommit": False
}
WG_API_TOKEN = os.getenv("WG_API_TOKEN")
LESTA_API_TOKEN = os.getenv("LESTA_API_TOKEN")
REGION_TIMEZONE = {
    'asia': 8, 
    'eu': 1, 
    'na': -7, 
    'ru': 3, 
    'cn': 8
}
def exec_sql_file(cursor, file_path: Path):
    print(f"🔎  Executing {file_path.name}")
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

def main():
    # 加载参数并效验
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-r", "--region",
        type=str,
        required=True,
        help="API Token"
    )
    args = parser.parse_args()
    region = args.region
    if region not in ['asia', 'eu', 'na', 'ru', 'cn']:
        raise ValueError('Incorrect region')

    # 加载游戏api地址、代理策略和令牌
    file_path = ROOT_DIR / "init/data/apis.json"
    with open(file_path, "r", encoding="utf-8") as f:
        api_data = json.load(f)
    endpoints = api_data.get(region)
    if region == 'ru':
        endpoints['api_token'] = LESTA_API_TOKEN
    elif region == 'cn':
        endpoints['api_token'] = None
    else:
        endpoints['api_token'] = WG_API_TOKEN
    file_path = ROOT_DIR / "data/json/endpoints.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(endpoints, f, ensure_ascii=False)
    print("1. Game API endpoints, proxy policy, and token loaded.....✅")

    # 加载船只数据
    if region == 'ru':
        csv_file_path = ROOT_DIR / "init/data/ship_name_lesta.csv"
    else:
        csv_file_path = ROOT_DIR / "init/data/ship_name_wg.csv"
    result = {}
    with open(csv_file_path, newline="", encoding="utf-8-sig") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            ship_id = row['ship_id']
            premium = row.get("premium", "0") == "1"
            special = row.get("special", "0") == "1"
            verify = row.get("verify", "0") == "1"
            rarity = row.get("rarity")
            translations = {
                "en": {
                    "short": row.get("en_short"),
                    "full": row.get("en_full")
                },
                "zh": {
                    "cn": row.get("zh_cn"),
                    "sg": row.get("zh_sg"),
                    "tw": row.get("zh_tw")
                },
                "ja": row.get("ja"),
                "ru": row.get("ru")
            }
            ship_data = {
                "tier": int(row.get("tier", 0)),
                "type": row.get("type"),
                "nation": row.get("nation"),
                "premium": premium,
                "special": special,
                "rarity": rarity,
                "index": row.get("index"),
                "verify": verify,
                "name": translations
            }
            result[ship_id] = ship_data
    file_path = ROOT_DIR / "data/json/ship_name.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False)
    print("2. Ship data loaded and JSON generated....................✅")

    # 读取游戏版本
    base_url = endpoints['vortex_api'][0]
    url = f'{base_url}/api/v2/graphql/glossary/version/'
    body = [{"query":"query Version {\n  version\n}"}]
    resp = requests.post(url,json=body,timeout=5)
    if resp.status_code == 200:
        version_data = resp.json()
        full_version = version_data[0]['data']['version']
        short_version = ".".join(full_version.split(".")[:2])
        file_path = ROOT_DIR / f"data/json/version.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump({'version': short_version}, f, ensure_ascii=False)
    else:
        resp.raise_for_status()
    print(f'3. Game version retrieved and saved......................✅')

    # 执行数据库初始化
    sql_files = [
        ROOT_DIR / "init/mysql/01-schema.sql"
    ]
    for f in sql_files:
        if not f.exists():
            print(f"Missing SQL file: {f}")
            return
    conn = pymysql.connect(**MYSQL_CONFIG)
    try:
        with conn.cursor() as cursor:
            for sql_file in sql_files:
                exec_sql_file(cursor, sql_file)
        conn.commit()
        print("4. MySQL initialization finished..........................✅")
    except Exception:
        conn.rollback()
        print("4. MySQL initialization failed............................⚠️")
        traceback.print_exc()   
    finally:
        conn.close()

    # 生成初始化文件
    result = {
        'init_time': int(time.time()),
        'region': region,
        'timezone': REGION_TIMEZONE[region]
    }
    hash_value = hash(frozenset(result.items()))
    result['hash'] = hash_value
    init_file_path = ROOT_DIR / f"data/json/init_marker.json"
    with open(init_file_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False)
    print("5. Initialization file generated..........................✅")


if __name__ == "__main__":
    main()
