import os
import csv
import sys
import gzip
import json
import array
import bisect
import sqlite3
import traceback
from redis import Redis
from pymysql import Connection
from pymysql.cursors import Cursor
from datetime import datetime, timezone

from settings import BATCH_SIZE, DATA_DIR, TEMP_DIR
from logger import logger


TOP_N_LIMIT = 50
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
    'ranking', 'region_id', 'account_id', 'battles', 'rating', 'rating_amend', 
    'win_rate', 'solo_rate', 'avg_damage', 'avg_frags', 'avg_exp', 
    'max_damage_dealt', 'max_exp', 'rating_level', 'win_rate_level', 
    'solo_rate_level', 'avg_damage_level', 'avg_frags_level '
]
CLAN_CSV_HEADER = [
    'ranking', 'region_id', 'clan_id', 'clan_tag', 'battles_count', 'rating', 'league', 
    'division', 'division_rating', 'longest_winning_streak', 'last_battle_time'
]
UserCreateSQL = """
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    region_id int,
    account_id int, 
    pvp_count int, 
    cache str
);
CREATE UNIQUE INDEX idx_user ON users(region_id, account_id);
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
    result = {
        'wg': {},
        'lesta': {}
    }
    for realm in ['wg', 'lesta']:
        file_path = DATA_DIR / f'json/ship_name_{realm}.json'
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            for ship_id, ship_data in data.items():
                result[realm][ship_id] = ship_data['tier']
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
    # 计算PR
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

def get_season(connection: Connection):
    cursor: Cursor = connection.cursor()
    try:
        sql = """
            SELECT 
                season_id 
            FROM clan_battle;
        """
        cursor.execute(sql)
        data = cursor.fetchone()
        return data[0]
    except Exception:
        logger.warning("Failed to read season data")
        logger.error((f"{traceback.format_exc()}"))
    finally:
        cursor.close()

def get_update_ids(connection: Connection):
    # 先获取数据库中id最大值，确定循环上限
    update_list = []
    cursor: Cursor = connection.cursor()
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
                    SELECT region_id, account_id, pvp_count
                    FROM users
                """
                cur.execute(sql)
                for region_id, account_id, pvp_count in cur:
                    combined = int(str(region_id) + str(account_id) + str(pvp_count))
                    pos = bisect.bisect_left(numbers, combined)
                    numbers.insert(pos, combined)
                logger.debug(f"Array Len: {len(numbers)}")  
                logger.debug(f"Array Size: {sys.getsizeof(numbers) / 1024 / 1024:.2f} MB")
            cur.close()
        # 读取用户的数据，并判断那些用户的缓存数据和数据库不同
        sql = """
            SELECT 
                MAX(id) 
            FROM user_cache;
        """
        cursor.execute(sql)
        data = cursor.fetchone()
        max_id = data[0]
        logger.info(f'User Max ID: {max_id}')
        for offset in range(0, max_id, BATCH_SIZE):
            sql = """
                SELECT 
                    b.region_id, 
                    b.account_id, 
                    c.pvp_count 
                FROM user_cache AS c 
                LEFT JOIN user_base AS b 
                  ON c.account_id = b.account_id 
                LEFT JOIN user_clan as s 
                  ON c.account_id = s.account_id
                WHERE c.id BETWEEN %s AND %s;
            """
            cursor.execute(sql, [offset+1, offset+BATCH_SIZE])
            rows = cursor.fetchall()
            for row in rows:
                if row is None:
                    continue
                if row[2] <= 40:
                    continue
                if not user_exists(numbers, int(str(row[0])+str(row[1])+str(row[2]))):
                    update_list.append([row[0], row[1]])
    except Exception:
        logger.error((f"{traceback.format_exc()}"))
    finally:
        cursor.close()
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
    # return [
    #     str(ship_data[0]),
    #     str(round(ship_data[1]/ship_data[0]*100, 2)),
    #     str(round(ship_data[2]/ship_data[0]*100, 2)),
    #     str(round(ship_data[3]/ship_data[0], 2)),
    #     str(round(ship_data[4]/ship_data[0], 2)),
    #     str(round(ship_data[5]/ship_data[0], 2)),
    #     str(ship_data[7]),
    #     str(ship_data[8])
    # ]

def update_user_cache(connection: Connection, ship_tier_data: dict, region_id: int, account_id: int):
    # 解压数据库中的数据
    pvp_count = 0
    db_data = {}
    new_cache_data = []
    if region_id == 4:
        tier_data = ship_tier_data['lesta']
    else:
        tier_data = ship_tier_data['wg']
    cursor: Cursor = connection.cursor()
    try:
        sql = """
            SELECT  
                pvp_count, 
                cache 
            FROM user_cache 
            WHERE account_id = %s;
        """
        cursor.execute(sql, [account_id])
        row = cursor.fetchone()
        if row is None:
            return 'NoData'
        pvp_count = row[0]
        for ship_id, ship_data in decompress(row[1]).items():
            ship_tier = tier_data.get(ship_id, 1)
            if ship_tier <= 5:
                continue
            ship_battles_limit = BATTLES_LIMIT.get(ship_tier, 40)
            if ship_data[0] < ship_battles_limit:
                continue
            db_data[int(ship_id)] = ship_data
            new_cache_data.append(f"{ship_id}_{ship_data[0]}")
    except Exception:
        logger.error((f"{traceback.format_exc()}"))
    finally:
        cursor.close()
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
            WHERE region_id = ? 
                AND account_id = ?;
        """
        cur.execute(sql, [region_id, account_id])
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
                    UPDATE users SET pvp_count = ?, cache = ?  
                    WHERE region_id = ? 
                        AND account_id = ?;
                """
                cur.execute(sql, [pvp_count, None, region_id, account_id])
            else:
                sql = """
                    INSERT INTO users (region_id, account_id, pvp_count, cache) VALUES (?,?,?,?);
                """
                cur.execute(sql, [region_id, account_id, pvp_count, None])
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
                    region_id int, 
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
            # sql = f"""
            #     CREATE TABLE ship_{ship_id} (
            #         region_id int, 
            #         account_id int,
            #         ship_data str
            #     );
            # """
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
                    region_id, 
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
                    ?,?,?,?,?,?,?,?,?,?
                );
            """
            cur.execute(sql, [region_id, account_id] + ship_data)
            # sql = f"""
            #     INSERT OR REPLACE INTO ship_{ship_id} (
            #         region_id, 
            #         account_id,
            #         ship_data
            #     ) VALUES (
            #         ?,?,?
            #     );
            # """
            # cur.execute(sql, [region_id, account_id, ':'.join(ship_data)])
        conn.commit()
        cur.close()
    # 更新用户缓存
    with sqlite3.connect(cache_path) as conn:
        cur = conn.cursor()
        if user_cache_exists:
            sql = """
                UPDATE users SET pvp_count = ?, cache = ?  
                WHERE region_id = ? 
                    AND account_id = ?;
            """
            cur.execute(sql, [pvp_count, ':'.join(new_cache_data), region_id, account_id])
        else:
            sql = """
                INSERT INTO users (region_id, account_id, pvp_count, cache) VALUES (?,?,?,?);
            """
            cur.execute(sql, [region_id, account_id, pvp_count, ':'.join(new_cache_data)])
        cur.close()
    return len(insert_ship_data)

def process_clan(connection: Connection, SEASON_ID: int):
    cursor: Cursor = connection.cursor()
    try:
        sql = """
            SELECT 
                b.region_id, 
                s.clan_id, 
                b.tag, 
                s.battles_count, 
                s.public_rating, 
                s.league, 
                s.division, 
                s.division_rating, 
                s.longest_winning_streak, 
                UNIX_TIMESTAMP(s.last_battle_at)
            FROM clan_stats AS s
            LEFT JOIN clan_base AS b 
              ON s.clan_id = b.clan_id
            WHERE s.season = %s;
        """
        cursor.execute(sql, [SEASON_ID])
        rows = cursor.fetchall()
        if rows and len(rows) != 1:
            rows = list(rows)
            rows.sort(key=lambda x: x[4], reverse=True)
        # 处理单独服务器
        region_groups = {1: [], 2: [], 3: [], 4: [], 5: []}
        for row in rows:
            region_id = int(row[0])
            if region_id in region_groups:
                region_groups[region_id].append(row)
        for region_id, data in region_groups.items():
            ranked_data = []
            for i, row in enumerate(data):
                row = list(row)
                current_rating = int(row[4])
                if i == 0:
                    rank = 1
                else:
                    prev_rating = int(data[i-1][4])
                    prev_rank = ranked_data[i-1][0]
                    if current_rating == prev_rating:
                        rank = prev_rank
                    else:
                        rank = i + 1
                new_row = [rank] + row
                ranked_data.append(new_row)
            output_path = DATA_DIR / f'ranking/{region_id}/clan.csv'
            temp_path = TEMP_DIR / f'clan.csv'
            with open(temp_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(CLAN_CSV_HEADER)
                for row in ranked_data:
                    writer.writerow(row)
                csvfile.flush()
                os.fsync(csvfile.fileno())
            os.replace(temp_path, output_path)
            if temp_path.exists():
                os.remove(temp_path)
        # 处理总服务器
        ranked_data = []
        for i, row in enumerate(rows[:50]):
            row = list(row)
            current_rating = int(row[4])
            if i == 0:
                rank = 1
            else:
                prev_rating = int(rows[i-1][4])
                prev_rank = ranked_data[i-1][0] # 上一行的排名是最后一列
                if current_rating == prev_rating:
                    rank = prev_rank
                else:
                    rank = i + 1
            new_row = [rank] + row
            ranked_data.append(new_row)
        output_path = DATA_DIR / f'ranking/0/clan.csv'
        temp_path = TEMP_DIR / f'clan.csv'
        with open(temp_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(CLAN_CSV_HEADER)
            for row in ranked_data:
                writer.writerow(row)
            csvfile.flush()
            os.fsync(csvfile.fileno())
        os.replace(temp_path, output_path)
        if temp_path.exists():
            os.remove(temp_path)
        return 'Success'
    except Exception:
        logger.warning("Failed to read season data")
        logger.error((f"{traceback.format_exc()}"))
    finally:
        cursor.close()

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
            for region_id in [1,2,3,4,5]:
                region_data = []
                server_data = ship_server_data[str(ship_id)].get(get_region(region_id))
                if server_data != {}:
                    sql = f"""
                        SELECT 
                            region_id, 
                            account_id,
                            battles_count,
                            solo_rate,
                            win_rate,
                            avg_damage,
                            avg_frags,
                            avg_exp,
                            max_exp,
                            max_damage 
                        FROM ship_{ship_id} 
                        WHERE region_id = ?;
                    """
                    cur.execute(sql, [region_id])
                    rows = cur.fetchall()
                    for row in rows:
                        rating,adjusted_rating,n_dmg,n_kd = get_region_rating(
                            ship_data=[row[3], row[4], row[5], row[6]],
                            server_data=[
                                server_data['win_rate'],
                                server_data['avg_damage'],
                                server_data['avg_frags']
                            ]
                        )
                        region_data.append([
                            row[0], row[1], row[2], rating, adjusted_rating, 
                            row[3], row[4], row[5], row[6], row[7], row[8], 
                            row[9], n_dmg, n_kd
                        ])
                region_data.sort(key=lambda x: x[3], reverse=True)
                ranked_data = []
                for i, row in enumerate(region_data):
                    row = list(row)
                    current_rating = int(row[3])
                    if i == 0:
                        rank = 1
                    else:
                        prev_rating = int(region_data[i-1][3])
                        prev_rank = ranked_data[i-1][0]
                        if current_rating == prev_rating:
                            rank = prev_rank
                        else:
                            rank = i + 1
                    rating_level = get_content_class(3, row[3])
                    win_rate_level = get_content_class(0, row[6])
                    solo_rate_level = get_content_class(4, row[5])
                    avg_damage_level = get_content_class(1, row[12])
                    avg_frags_level = get_content_class(2, row[13])
                    new_row = [
                        rank, row[0], row[1], row[2], int(row[3]), row[4], row[6], 
                        row[5], int(row[7]), row[8], int(row[9]), row[11], row[10],
                        rating_level, win_rate_level, solo_rate_level, 
                        avg_damage_level, avg_frags_level
                    ]
                    ranked_data.append(new_row)
                if len(ranked_data) == 0:
                    continue
                output_path = DATA_DIR / f'ranking/{region_id}/ship_{ship_id}.csv'
                temp_path = TEMP_DIR / f'ship_{ship_id}.csv'
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
    return 'Success'
