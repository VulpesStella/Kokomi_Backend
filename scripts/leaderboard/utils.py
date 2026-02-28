import os
import csv
import time
import gzip
import json
import array
import bisect
import sqlite3
import traceback
from pymysql import Connection
from pymysql.cursors import Cursor
from datetime import datetime, timezone

from logger import logger
from settings import (
    BATCH_SIZE, 
    DATA_DIR, 
    TEMP_DIR, 
    REGION
)


TOP_N_LIMIT = 50
TWO_YEAR_SECONDS = 2*365*24*60*60
BATTLES_LIMIT = {
    6: 40, 7: 40,
    8: 40, 9: 50,
    10: 60, 11: 60
}
OLD_SHIP_ID_LIST = [
    '4281317360','4285511376','4181112624','4292851408','4283414224',
    '3763320816','4289607376','4292851696','4277057520','4181603792',
    '4184749520','4179015472','4284364496','4183209776','4287543280',
    '4180555216','4181112816','3762272240','3762272048','4284463088',
    '4290754544','4184782288','4277122768','4183209968','4280203248',
    '4288657392','4288657104','4288558800','4179015664','4282300400',
    '4183700944','4282365648','4279220208','3763320528','4287510224',
    '4282365936','4279219920'
]
USER_CSV_HEADER = [
    'ranking', 'account_id', 'battles', 'rating', 'rating_amend', 
    'win_rate', 'solo_rate', 'avg_damage', 'avg_frags', 'avg_exp', 
    'max_exp', 'max_damage_dealt', 'rating_level', 'win_rate_level', 
    'solo_rate_level', 'avg_damage_level', 'avg_frags_level'
]
UserCreateSQL = """
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    account_id int, 
    pvp_count int, 
    cache str
);
CREATE UNIQUE INDEX idx_user ON users(account_id);
"""
ExistsCreateSQL = """
CREATE TABLE exists_ids (
    id INTEGER PRIMARY KEY,
    ship_id int
);
"""

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def decompress(gzip_bytes: bytes):
    # 数据解压
    if gzip_bytes:
        decompressed = gzip.decompress(gzip_bytes)
        return json.loads(decompressed)
    else:
        return {}
    
def read_ship_tier():
    result = {}
    file_path = DATA_DIR / f'json/ship_name.json'
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        for ship_id, ship_data in data.items():
            result[ship_id] = ship_data['tier']
    return result

def read_ship_server():
    result = {}
    file_path = DATA_DIR / f'json/ship_data.json'
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        result = data['ship_data']
    return result

def get_region(region_id: int):
    region_dict = {1: 'asia',2: 'eu',3: 'na',4: 'ru',5: 'cn'}
    return region_dict[region_id]

def user_exists(numbers: array, combined: int):
    i = bisect.bisect_left(numbers, combined)
    return i < len(numbers) and numbers[i] == combined

def get_region_rating(
    ship_data: list,
    server_data: list
):
    '''计算pr

    ship_data [solo_count, win_rate, avg_damage, avg_frags]
    server_data [expected_wins, expected_dmg, expected_frags]
    '''
    # 用户数据
    actual_wins = ship_data[1]
    actual_dmg = ship_data[2]
    actual_frags = ship_data[3]
    # 服务器数据
    expected_wins = server_data[0]
    expected_dmg = server_data[1]
    expected_frags = server_data[2]
    # 计算比率
    r_wins = actual_wins / expected_wins
    r_dmg = actual_dmg / expected_dmg
    r_frags = actual_frags / expected_frags
    # 归一化
    n_wins = max(0, (r_wins - 0.7) / (1 - 0.7))
    n_dmg = max(0, (r_dmg - 0.4) / (1 - 0.4))
    n_frags = max(0, (r_frags - 0.1) / (1 - 0.1))
    # 单野修正
    win_diff = int(150 * n_wins * 0.25 * (100 - ship_data[0]) / 100)
    personal_rating = 700 * n_dmg + 300 * n_frags + 150 * n_wins - win_diff
    return [
        round(personal_rating, 2),
        round(win_diff, 2),
        round(actual_dmg / expected_dmg, 2),
        round(actual_frags / expected_frags, 2)
    ]

def get_content_class(
    index: int, 
    value: int | float
) -> int:
    '''index [wr, dmg, frag, pr, sr]'''
    index_list = [
        [45, 49, 51, 52.5, 55, 60, 70],
        [0.8, 0.95, 1.0, 1.1, 1.2, 1.4, 1.7],
        [0.2, 0.3, 0.6, 1.0, 1.3, 1.5, 2],
        [750, 1100, 1350, 1550, 1750, 2100, 2450],
        [10, 30, 40, 50, 60, 70, 80]
    ]
    if value == -2:
        return 0
    if value == -1:
        return 0
    data = index_list[index]
    for i in range(len(data)):
        if value < data[i]:
            return i + 1
    return 8

def get_version():
    file_path = DATA_DIR / f"json/version.json"
    with open(file_path, "r", encoding="utf-8") as f:
        version_data = json.load(f)
        return version_data['version']

def get_update_ids(mysql_connection: Connection):
    # 先获取数据库中id最大值，确定循环上限
    update_list = []
    mysql_cursor: Cursor = mysql_connection.cursor()
    try:
        # 读取缓存中的用户数据
        numbers = array.array("Q")
        cache_path = DATA_DIR / 'cache/leaderboard_user.db'
        cache_exists = cache_path.exists()
        with sqlite3.connect(cache_path) as conn:
            cur = conn.cursor()
            if not cache_exists:
                cur.executescript(UserCreateSQL)
                conn.commit()
            else:
                sql = """
                    SELECT account_id, pvp_count
                    FROM users
                """
                cur.execute(sql)
                for account_id, pvp_count in cur:
                    combined = int(str(account_id) + str(pvp_count))
                    pos = bisect.bisect_left(numbers, combined)
                    numbers.insert(pos, combined)
                logger.debug(f"Array Len: {len(numbers)}")  
            cur.close()
        # 读取用户的数据，并判断那些用户的缓存数据和数据库不同
        sql = """
            SELECT 
                MAX(id) 
            FROM user_cache;
        """
        mysql_cursor.execute(sql)
        data = mysql_cursor.fetchone()
        max_id = data[0]
        logger.info(f'Max id in table user_cache: {max_id}')
        for offset in range(0, max_id, BATCH_SIZE):
            sql = """
                SELECT 
                    account_id, 
                    pvp_count 
                FROM user_cache 
                WHERE id BETWEEN %s AND %s;
            """
            mysql_cursor.execute(sql, [offset+1, offset+BATCH_SIZE])
            rows = mysql_cursor.fetchall()
            for row in rows:
                if row is None:
                    continue
                if row[1] <= 40:
                    continue
                if not user_exists(numbers, int(str(row[0])+str(row[1]))):
                    update_list.append(row[0])
    except Exception:
        logger.error((f"{traceback.format_exc()}"))
    finally:
        mysql_cursor.close()
    return update_list

def format_ship_data(ship_data: list):
    return [
        ship_data[0],
        round(ship_data[1]/ship_data[0]*100, 2),
        round(ship_data[2]/ship_data[0]*100, 2),
        round(ship_data[3]/ship_data[0], 2),
        round(ship_data[4]/ship_data[0], 2),
        round(ship_data[5]/ship_data[0], 2),
        ship_data[7],
        ship_data[8]
    ]

def update_user_cache(mysql_connection: Connection, ship_tier_data: dict, account_id: int):
    # 解压数据库中的数据
    pvp_count = 0
    db_data = {}
    mysql_cursor: Cursor = mysql_connection.cursor()
    try:
        sql = """
            SELECT  
                pvp_count, 
                cache 
            FROM user_cache 
            WHERE account_id = %s;
        """
        mysql_cursor.execute(sql, [account_id])
        row = mysql_cursor.fetchone()
        if row is None:
            return 'NoData'
        pvp_count = row[0]
        for ship_id, ship_data in decompress(row[1]).items():
            ship_tier = ship_tier_data.get(ship_id, 1)
            if ship_tier <= 5:
                continue
            ship_battles_limit = BATTLES_LIMIT.get(ship_tier, 40)
            if ship_data[0] < ship_battles_limit:
                continue
            db_data[int(ship_id)] = ship_data
    except Exception:
        logger.error((f"{traceback.format_exc()}"))
    finally:
        mysql_cursor.close()
    # 读取缓存中的数据
    user_cache_exists = True
    cache_data = {}
    cache_path = DATA_DIR / 'cache/leaderboard_user.db'
    cache_exists = cache_path.exists()
    with sqlite3.connect(cache_path) as conn:
        cur = conn.cursor()
        if not cache_exists:
            cur.executescript(UserCreateSQL)
            conn.commit()
        sql = """
            SELECT 
                cache 
            FROM users 
            WHERE account_id = ?;
        """
        cur.execute(sql, [account_id])
        data = cur.fetchone()
        if data:
            if data[0]:
                for split_str in data[0].split(':'):
                    split_split_str = split_str.split('_')
                    cache_data[int(split_split_str[0])] = int(split_split_str[1])
        else:
            user_cache_exists = False
        if pvp_count == 0 or db_data == {}:
            if user_cache_exists:
                sql = """
                    UPDATE users 
                    SET 
                        pvp_count = ?, 
                        cache = ?  
                    WHERE account_id = ?;
                """
                cur.execute(sql, [pvp_count, None, account_id])
            else:
                sql = """
                    INSERT INTO users (account_id, pvp_count, cache) VALUES (?,?,?);
                """
                cur.execute(sql, [account_id, pvp_count, None])
            conn.commit()
            cur.close()
            return 0
        cur.close()
    # 对比新旧数据需要写入的条目
    insert_ship_data = {}
    for ship_id, ship_data in db_data.items():
        if ship_id not in cache_data:
            insert_ship_data[ship_id] = format_ship_data(ship_data)
        elif cache_data[ship_id] != ship_data[0]:
            insert_ship_data[ship_id] = format_ship_data(ship_data)
    # 写入数据
    ship_path = DATA_DIR / 'cache/leaderboard_ship.db'
    ship_exists = ship_path.exists()
    with sqlite3.connect(ship_path) as conn:
        existing_ship_ids = []
        cur = conn.cursor()
        if not ship_exists:
            cur.executescript(ExistsCreateSQL)
            conn.commit()
        else:
            sql = """
                SELECT 
                    ship_id 
                FROM exists_ids;
            """
            cur.execute(sql)
            rows = cur.fetchall()
            if rows:
                for row in rows:
                    existing_ship_ids.append(row[0])
        missing_ship_ids = []
        for ship_id in insert_ship_data.keys():
            if ship_id not in existing_ship_ids:
                missing_ship_ids.append(ship_id)
        cur.execute("BEGIN")
        for ship_id in missing_ship_ids:
            sql = f"""
                CREATE TABLE ship_{ship_id} (
                    account_id int,
                    battles_count int,
                    solo_rate float,
                    win_rate float,
                    avg_damage float,
                    avg_frags float,
                    avg_exp float,
                    max_exp int,
                    max_damage int
                );
            """
            cur.execute(sql)
            sql = f"""
                INSERT INTO exists_ids (ship_id) VALUES (?);
            """
            cur.execute(sql, [ship_id])
        conn.commit()
        cur.execute("BEGIN")
        for ship_id, ship_data in insert_ship_data.items():
            sql = f"""
                INSERT OR REPLACE INTO ship_{ship_id} (
                    account_id,
                    battles_count,
                    solo_rate,
                    win_rate,
                    avg_damage,
                    avg_frags,
                    avg_exp,
                    max_exp,
                    max_damage
                ) VALUES (
                    ?,?,?,?,?,?,?,?,?
                );
            """
            cur.execute(sql, [account_id] + ship_data)
        conn.commit()
        cur.close()
    # 更新用户缓存
    new_cache_list = []
    for ship_id, ship_data in db_data.items():
        new_cache_list.append(f'{ship_id}_{ship_data[0]}')
    new_cache_data = ':'.join(new_cache_list)
    with sqlite3.connect(cache_path) as conn:
        cur = conn.cursor()
        if user_cache_exists:
            sql = """
                UPDATE users 
                SET 
                    pvp_count = ?, 
                    cache = ?  
                WHERE account_id = ?;
            """
            cur.execute(sql, [pvp_count, new_cache_data, account_id])
        else:
            sql = """
                INSERT INTO users (
                    account_id, 
                    pvp_count, 
                    cache
                ) VALUES (
                    ?,?,?
                );
            """
            cur.execute(sql, [account_id, pvp_count, new_cache_data])
        cur.close()
    return len(insert_ship_data)

def process_user(ship_server_data: dict):
    ship_path = DATA_DIR / 'cache/leaderboard_ship.db'
    ship_exists = ship_path.exists()
    with sqlite3.connect(ship_path) as conn:
        existing_ship_ids = []
        cur = conn.cursor()
        if not ship_exists:
            cur.executescript(ExistsCreateSQL)
            conn.commit()
        else:
            sql = """
                SELECT 
                    ship_id 
                FROM exists_ids;
            """
            cur.execute(sql)
            rows = cur.fetchall()
            if rows:
                for row in rows:
                    existing_ship_ids.append(row[0])
        for ship_id in existing_ship_ids:
            if str(ship_id) not in ship_server_data:
                continue
            region_data = []
            server_data = ship_server_data[str(ship_id)]
            if server_data == {}:
                continue
            sql = f"""
                SELECT 
                    account_id,
                    battles_count,
                    solo_rate,
                    win_rate,
                    avg_damage,
                    avg_frags,
                    avg_exp,
                    max_exp,
                    max_damage 
                FROM ship_{ship_id};
            """
            cur.execute(sql)
            for row in cur.fetchall():
                rating,adjusted_rating,n_dmg,n_kd = get_region_rating(
                    ship_data=[row[2], row[3], row[4], row[5]],
                    server_data=[
                        server_data['win_rate'],
                        server_data['avg_damage'],
                        server_data['avg_frags']
                    ]
                )
                region_data.append([
                    row[0], row[1], rating, adjusted_rating, row[2], 
                    row[3], row[4], row[5], row[6], row[7], row[8], 
                    n_dmg, n_kd
                ])
            region_data.sort(key=lambda x: x[2], reverse=True)
            ranked_data = []
            for i, row in enumerate(region_data):
                row = list(row)
                current_rating = int(row[2])
                if i == 0:
                    rank = 1
                else:
                    prev_rating = int(region_data[i-1][2])
                    prev_rank = ranked_data[i-1][0]
                    if current_rating == prev_rating:
                        rank = prev_rank
                    else:
                        rank = i + 1
                rating_level = get_content_class(3, row[2])
                win_rate_level = get_content_class(0, row[5])
                solo_rate_level = get_content_class(4, row[4])
                avg_damage_level = get_content_class(1, row[11])
                avg_frags_level = get_content_class(2, row[12])
                new_row = [
                    rank, row[0], row[1], int(row[2]), row[3], row[5], 
                    row[4], int(row[6]), row[7], int(row[8]), row[9], row[10],
                    rating_level, win_rate_level, solo_rate_level, 
                    avg_damage_level, avg_frags_level
                ]
                ranked_data.append(new_row)
            if len(ranked_data) == 0:
                continue
            output_path = DATA_DIR / f'ranking/{REGION}_{ship_id}.csv'
            temp_path = TEMP_DIR / f'{REGION}_{ship_id}.csv'
            with open(temp_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(USER_CSV_HEADER)
                for row in ranked_data:
                    writer.writerow(row)
                csvfile.flush()
                os.fsync(csvfile.fileno())
            os.replace(temp_path, output_path)
            if temp_path.exists():
                os.remove(temp_path)
        cur.close()
    return 'Success'
