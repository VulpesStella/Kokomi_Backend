import os
import gzip
import csv
import sqlite3
import json
import pymysql
from datetime import datetime, timezone

from middlewares import db_pool, redis_client
from settings import BATCH_SIZE, DATA_DIR
from logger import logger

CSV_HEADER = [
    'region_id', 'account_id', 'battles', 'rating', 'rating_amend', 
    'win_rate', 'solo_rate', 'avg_damage', 'avg_frags', 'avg_exp', 
    'max_damage_dealt', 'max_exp', 'rating_color', 'win_rate_color', 
    'solo_rate_color', 'avg_damage_color', 'avg_frags_color'
]

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def decompress(gzip_bytes: bytes):
    # 数据解压
    if gzip_bytes:
        decompressed = gzip.decompress(gzip_bytes)
        return json.loads(decompressed)
    else:
        return None
    
def get_update_ids():
    try:
        result = redis_client.get('status:cache_refresh_time')
        cache_refresh_time = json.loads(result) if result else 0
    except:
        cache_refresh_time = 0
    # 先获取数据库中id最大值，确定循环上限
    conn = db_pool.connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    try:
        sql = """
            SELECT 
                MAX(id) AS max_id 
            FROM user_cache;
        """
        cursor.execute(sql)
        data = cursor.fetchone()
        max_id = data['max_id']
        update_ids = []
        for offset in range(0, max_id, BATCH_SIZE):
            sql = """
                SELECT 
                    id, 
                    UNIX_TIMESTAMP(updated_at) AS updated_at 
                FROM user_cache
                WHERE id BETWEEN %s AND %s;
            """
            cursor.execute(sql, [offset+1, offset+BATCH_SIZE])
            data = cursor.fetchall()
            for user in data:
                updated_at = user['updated_at'] if user['updated_at'] else 0
                if updated_at > cache_refresh_time:
                    update_ids.append(user['id'])
        return update_ids
    finally:
        cursor.close()
        conn.close()

def get_cache_data(region_id: int, account_id: int):
    cache_db_path = os.path.join(DATA_DIR, 'cache/user.db')
    try:
        conn = sqlite3.connect(cache_db_path)
        cursor = conn.cursor()
        # 检查是否存在用户表
        cursor.execute("""
            SELECT cache 
            FROM users 
            WHERE region_id = ? 
                AND account_id = ?;
        """, [region_id, account_id])
        row = cursor.fetchone()
        cache_data = {}
        for value in row.split('_'):
            key = value.split(':')
            cache_data[key[0]] = int(key[1])
        return cache_data
    finally:
        conn.close()

def process_clans():
    conn = db_pool.connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    try:
        sql = """
            SELECT 
                b.region_id, 
                b.account_id, 
                s.season, 
                s.public_rating, 
                s.league, 
                s.division, 
                s.division_rating 
            FROM clan_stats AS s 
            LEFT JOIN clan_base AS b 
              ON b.account_id = s.account_id 
            WHERE s.id = %s;
        """
    finally:
        cursor.close()
        conn.close()

def process_users(current_id: int):
    conn = db_pool.connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    try:
        # 获取 region_id 和 cache 数据
        sql = """
            SELECT 
                b.region_id, 
                b.account_id, 
                c.cache 
            FROM user_cache AS c 
            LEFT JOIN user_base AS b 
                ON c.account_id = b.account_id 
            WHERE c.id = %s;
        """
        cursor.execute(sql, [current_id])
        row = cursor.fetchone()
        if row is None:
            return
        region_id = row['region_id']
        account_id = row['account_id']
        blob_data = row['cache']
        if not blob_data:
            return
        user_ship_data = decompress(blob_data)
        user_cache_data = get_cache_data(region_id, account_id)
        update_data = {}
        for ship_id, ship_data in user_ship_data.items():
            if str(ship_id) not in user_cache_data or ship_data[0] != user_cache_data[str(ship_id)]:
                if ship_data[0] == 0:
                    continue
                solo_rate = ship_data[1] / ship_data[0]
                win_rate = ship_data[2] / ship_data[0]
                avg_damage = ship_data[3] / ship_data[0]
                avg_frags = ship_data[4] / ship_data[0]
                avg_exp = ship_data[5] / ship_data[0]
                update_data[ship_id] = [
                    region_id,
                    account_id,
                    ship_data[0],
                    round(win_rate, 4),
                    round(solo_rate, 4),
                    round(avg_damage, 2),
                    round(avg_frags, 2),
                    round(avg_exp, 2),
                    ship_data[8],
                    ship_data[7]
                ]
        csv_path = os.path.join(DATA_DIR, 'cache')
        csv_file_list = []
        for filename in os.listdir(csv_path):
            if not filename.endswith(".csv"):
                continue
            csv_file_list.append(filename)
        for key in update_data.keys():
            if f'{key}.csv' not in csv_file_list:
                csv_file_path = os.path.join(csv_path, f'{key}.csv')
                with open(csv_file_path, "w", encoding="utf-8", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow(CSV_HEADER)
        
    finally:
        cursor.close()
        conn.close()