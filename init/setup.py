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


ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / '.env.prod')
MYSQL_CONFIG = {
    "host": "127.0.0.1",
    "port": 3306,
    "user": os.getenv("MYSQL_USERNAME"),
    "password": os.getenv("MYSQL_PASSWORD"),
    "autocommit": False
}
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
    # 加载游戏api地址和代理策略
    file_path = ROOT_DIR / f"init/data/apis.json"
    with open(file_path, "r", encoding="utf-8") as f:
        api_data = json.load(f)
    endpoints = api_data.get(region)
    file_path = ROOT_DIR / f"data/json/endpoints.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(endpoints, f, ensure_ascii=False)
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
        print(f'✅  Current game version: {short_version}')
    else:
        resp.raise_for_status()
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
        print("✅  MySQL initialization finished")
        conn.commit()
    except:
        conn.rollback()
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
    file_path = ROOT_DIR / f"data/json/init_marker.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False)
    print("✅  API initialization successful!")


if __name__ == "__main__":
    main()
