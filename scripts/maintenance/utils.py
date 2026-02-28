import os
import csv
import time
import json
import gzip
import random
import requests
import traceback
from redis import Redis
from pymysql import Connection
from pymysql.cursors import Cursor
from datetime import datetime, timezone

from logger import logger
from settings import (
    BATCH_SIZE,
    VORTEX_API,
    DATA_DIR,
    TEMP_DIR,
    REGION
)


HOUR: int = 60 * 60
DAY: int = 24 * HOUR
CLAN_UPDATE_INTERVAL = 6*HOUR
REFRESH_TIME_CONFIG: dict[int, tuple[int, int, int]] = {
    0: (5 * DAY,  6 * HOUR,   2 * HOUR),
    1: (25 * DAY, 12 * HOUR,  2 * HOUR),
    2: (1 * DAY,  int(0.5 * HOUR), 20 * 60),
    3: (2 * DAY,  1 * HOUR,   25 * 60),
    4: (3 * DAY,  2 * HOUR,   30 * 60),
    5: (5 * DAY,  3 * HOUR,   30 * 60),
    6: (7 * DAY,  4 * HOUR,   1 * HOUR),
    7: (15 * DAY, 5 * HOUR,   2 * HOUR),
    8: (20 * DAY, 6 * HOUR,   2 * HOUR),
    9: (30 * DAY, 12 * HOUR,  2 * HOUR),
}

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def decompress(gzip_bytes: bytes):
    # 数据解压
    if gzip_bytes:
        decompressed = gzip.decompress(gzip_bytes)
        return json.loads(decompressed)
    else:
        return None

def get_refresh_time(activity_level: int, lbt: int, enable_recent: bool, enable_daily: bool):
    if enable_daily:
        if lbt < 60*60:
            return 5*60
        else:
            return REFRESH_TIME_CONFIG[activity_level][2]
    elif enable_recent:
        return REFRESH_TIME_CONFIG[activity_level][1]
    else:
        return REFRESH_TIME_CONFIG[activity_level][0]

def fetch_data(url):
    try:
        body = [{"query":"query Version {\n  version\n}"}]
        resp = requests.post(url,json=body,timeout=5)
        if resp.status_code == 200:
            result = resp.json()
            logger.debug(f'200 {url}')
            return result
        logger.warning(f'Code_{resp.status_code} {url}')
        return f'HTTP_STATUS_{resp.status_code}'
    except Exception as e:
        logger.warning(f"{type(e).__name__} {url}")
        return f'ERROR_{type(e).__name__}'

def verify_responses(redis_client: Redis, responses: list):
    error = 0
    error_return = None
    now_time = now_iso()
    for response in responses:
        if isinstance(response, str):
            error += 1
            error_return = response
    key = f"metrics:http_total:{now_time[:10]}"
    redis_client.incrby(key, len(responses))
    if error == 0:
        return None
    else:
        key = f"metrics:http_error:{now_time[:10]}"
        redis_client.incrby(key, error)
        return error_return

def get_user_update_ids(mysql_connection: Connection, redis_client: Redis):
    # 从数据库中批量读取并判断那些用户需要更新
    update_list = []
    cursor: Cursor = mysql_connection.cursor()
    try:
        sql = """
            SELECT 
                MAX(id) 
            FROM user_base;
        """
        cursor.execute(sql)
        data = cursor.fetchone()
        max_id = data[0] if data[0] else 0
        recent = set()
        recents = set()
        sql = """
            SELECT 
                account_id, 
                enable_recent, 
                enable_daily 
            FROM recent;
        """
        cursor.execute(sql)
        rows = cursor.fetchall()
        for row in rows:
            if row[1] == 1:
                recent.add(row[0])
            if row[2] == 1:
                recents.add(row[0])
        logger.info(f'Max id in table user_base: {max_id}')
        logger.info(f'Recent: {len(recent)} | Recents: {len(recents)}')
        temp_update_list = []
        now_ts = int(time.time())
        for offset in range(0, max_id, BATCH_SIZE):
            sql = """
                SELECT 
                    b.account_id, 
                    s.activity_level, 
                    UNIX_TIMESTAMP(s.last_battle_at), 
                    UNIX_TIMESTAMP(s.touch_at) 
                FROM user_base AS b 
                LEFT JOIN user_stats AS s 
                    ON b.account_id = s.account_id 
                WHERE b.id BETWEEN %s AND %s;
            """
            cursor.execute(sql, [offset+1, offset+BATCH_SIZE])
            rows = cursor.fetchall()
            for user in rows:
                account_id = user[0]
                enable_recent = account_id in recent
                enable_daily = account_id in recents
                touch_time = user[3] if user[3] else 0
                last_battle_time = user[2] if user[2] else 0
                next_refresh_time = get_refresh_time(
                    user[1], 
                    now_ts - last_battle_time, 
                    enable_recent, 
                    enable_daily
                ) + touch_time
                if next_refresh_time <= now_ts:
                    temp_update_list.append(account_id)
        pipe = redis_client.pipeline()
        keys = [f"user_refresh:{aid}" for aid in temp_update_list]
        for key in keys:
            pipe.set(key, 1, nx=True, ex=4*60*60)
        # 批量执行
        results = pipe.execute()
        # 根据结果过滤未重复的用户
        update_list = [
            temp_update_list[i] for i, r in enumerate(results) if r
        ]
    except Exception:
        logger.error((f"{traceback.format_exc()}"))
    finally:
        cursor.close()
    return update_list

def get_clan_update_ids(mysql_connection: Connection, redis_client: Redis):
    # 从数据库中批量读取并判断哪些需要更新
    update_list = []
    cursor: Cursor = mysql_connection.cursor()
    try:
        sql = """
            SELECT 
                MAX(id) 
            FROM clan_users;
        """
        cursor.execute(sql)
        data = cursor.fetchone()
        max_id = data[0] if data[0] else 0
        logger.info(f'Max id in table clan_users: {max_id}')
        now_ts = int(time.time())
        temp_update_list = []
        for offset in range(0, max_id, BATCH_SIZE):
            sql = """
                SELECT 
                    clan_id, 
                    is_enabled, 
                    UNIX_TIMESTAMP(touch_at) AS touch_at 
                FROM clan_users 
                WHERE id BETWEEN %s AND %s;
            """
            cursor.execute(sql, [offset+1, offset+BATCH_SIZE])
            rows = cursor.fetchall()
            for row in rows:
                if row[2] is None:
                    temp_update_list.append(row[0])
                    continue
                if row[1] == 0:
                    continue
                if now_ts - row[2] > CLAN_UPDATE_INTERVAL:
                    temp_update_list.append(row[0])
        pipe = redis_client.pipeline()
        keys = [f"clan_refresh:{cid}" for cid in temp_update_list]
        for key in keys:
            pipe.set(key, 1, nx=True, ex=4*60*60)
        # 批量执行
        results = pipe.execute()
        # 根据结果过滤未重复的用户
        update_list = [
            temp_update_list[i] for i, r in enumerate(results) if r
        ]
    except Exception:
        logger.error((f"{traceback.format_exc()}"))
    finally:
        cursor.close()
    return update_list

def maintenance_database(mysql_connection: Connection):
    # 从数据库中批量读取并判断那些用户需要更新
    fixed_count = 0
    mysql_connection.begin()
    cursor: Cursor = mysql_connection.cursor()
    try:
        # 效验user表的完整型
        sql = """
            SELECT 
                MAX(id) 
            FROM user_base;
        """
        cursor.execute(sql)
        data = cursor.fetchone()
        max_id = data[0] if data[0] else 0
        verify_list = []
        for offset in range(0, max_id, BATCH_SIZE):
            sql = """
                SELECT 
                    account_id, 
                    verify 
                FROM user_base 
                WHERE id BETWEEN %s AND %s;
            """
            cursor.execute(sql, [offset+1, offset+BATCH_SIZE])
            rows = cursor.fetchall()
            for row in rows:
                if row[1] == 0:
                    verify_list.append(row[0])
        for account_id in verify_list:
            sql = """
                SELECT 
                    account_id 
                FROM user_base
                WHERE account_id = %s;
            """
            result = cursor.fetchone()
            if result is None:
                sql = """
                    INSERT INTO user_stats (
                        account_id
                    ) VALUES (
                        %s
                    );
                """
                cursor.execute(sql, [account_id])
                fixed_count += 1
            sql = """
                SELECT 
                    account_id 
                FROM user_clan
                WHERE account_id = %s;
            """
            result = cursor.fetchone()
            if result is None:
                sql = """
                    INSERT INTO user_clan (
                        account_id
                    ) VALUES (
                        %s
                    );
                """
                cursor.execute(sql, [account_id])
                fixed_count += 1
            sql = """
                SELECT 
                    account_id 
                FROM user_cache
                WHERE account_id = %s;
            """
            result = cursor.fetchone()
            if result is None:
                sql = """
                    INSERT INTO user_cache (
                        account_id
                    ) VALUES (
                        %s
                    );
                """
                cursor.execute(sql, [account_id])
                fixed_count += 1
            sql = """
                UPDATE user_base 
                SET 
                    verify = 1 
                WHERE account_id = %s;
            """
            cursor.execute(sql, [account_id])
        # 效验clan表的完整型
        sql = """
            SELECT 
                MAX(id) 
            FROM clan_base;
        """
        cursor.execute(sql)
        data = cursor.fetchone()
        max_id = data[0] if data[0] else 0
        verify_list = []
        for offset in range(0, max_id, BATCH_SIZE):
            sql = """
                SELECT 
                    clan_id, 
                    verify, 
                FROM clan_base 
                WHERE id BETWEEN %s AND %s;
            """
            cursor.execute(sql, [offset+1, offset+BATCH_SIZE])
            rows = cursor.fetchall()
            for row in rows:
                if row[1] == 0:
                    verify_list.append(row[0])
        for clan_id in verify_list:
            sql = """
                SELECT 
                    clan_id 
                FROM clan_users
                WHERE clan_id = %s;
            """
            result = cursor.fetchone()
            if result is None:
                sql = """
                    INSERT INTO clan_users (
                        clan_id
                    ) VALUES (
                        %s
                    );
                """
                cursor.execute(sql, [clan_id])
                fixed_count += 1
            sql = """
                UPDATE clan_base 
                SET 
                    verify = 1 
                WHERE clan_id = %s;
            """
            cursor.execute(sql, [clan_id])
        mysql_connection.commit()
    except Exception:
        mysql_connection.rollback()
        logger.error((f"{traceback.format_exc()}"))
    finally:
        cursor.close()
    return fixed_count

def get_version(redis_client: Redis):
    base_url = random.choice(VORTEX_API)
    url = f'{base_url}/api/v2/graphql/glossary/version/'
    result = fetch_data(url)
    error = verify_responses(redis_client, [result])
    if error != None:
        return error
    try:
        version = result[0]['data']['version']
        return {
            'version': ".".join(version.split(".")[:2])
        }
    except Exception as e:
        logger.error(f"{traceback.format_exc()}")
        return type(e).__name__

def process_region_stats(mysql_connection: Connection):
    cursor: Cursor = mysql_connection.cursor()
    try:
        sql = """
            SELECT 
                MAX(id) 
            FROM user_cache;
        """
        cursor.execute(sql)
        max_id_result = cursor.fetchone()
        max_id = max_id_result[0]
        logger.info(f'Max id in table user_cache: {max_id}')
        file_path = DATA_DIR / f"json/version.json"
        with open(file_path, "r", encoding="utf-8") as f:
            version_data = json.load(f)
            version = version_data['version']
        region_stats = {}
        for offset in range(0, max_id, BATCH_SIZE):
            if offset % 10000 == 0:
                logger.info(f'[{offset+1}/{max_id}] Processing~')
            sql = """
                SELECT 
                    account_id, 
                    cache 
                FROM user_cache 
                WHERE id BETWEEN %s AND %s;
            """
            cursor.execute(sql, [offset+1, offset+BATCH_SIZE])
            rows = cursor.fetchall()
            for row in rows:
                # 获取 region_id 和 cache 数据
                if row is None:
                    continue
                account_id = row[0]
                blob_data = row[1]
                if not blob_data:
                    continue
                user_ship_data = decompress(blob_data)
                for ship_id, stats in user_ship_data.items():
                    if ship_id not in region_stats:
                        region_stats[ship_id] = [0] * 12
                    target_list = region_stats[ship_id]
                    target_list[0] += stats[0]  # battles
                    target_list[1] += stats[2]  # wins
                    target_list[2] += stats[3]  # damage
                    target_list[3] += stats[4]  # frags
                    target_list[4] += stats[5]  # original_exp
                    target_list[5] += stats[6]  # survived
                    # 记录 Max Exp 及对应的 User ID
                    if stats[7] > target_list[6]:
                        target_list[6] = stats[7]
                        target_list[7] = account_id
                    # 记录 Max Damage 及对应的 User ID
                    if stats[8] > target_list[8]:
                        target_list[8] = stats[8]
                        target_list[9] = account_id
                    if stats[0] > target_list[10]:
                        target_list[10] = stats[0]
                        target_list[11] = account_id
                    region_stats[ship_id] = target_list
        headers = [
            'ship_id', 'battles_count', 'wins', 'damage_dealt', 'frags', 
            'original_exp', 'survived', 'max_exp', 'max_exp_id', 
            'max_damage_dealt', 'max_damage_id', 'max_battles', 'max_battles_id'
        ]
        ship_data_result = {
            "update_time": int(time.time()),
            "ship_data": {}
        }
        output_path = DATA_DIR / f'stats/{REGION}_{version}.csv'
        temp_path = TEMP_DIR / f'{REGION}_{version}.csv'
        with open(temp_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(headers)
            for ship_id, data in region_stats.items():
                writer.writerow([ship_id] + data)
            csvfile.flush()
            os.fsync(csvfile.fileno())
        os.replace(temp_path, output_path)
        if temp_path.exists():
            os.remove(temp_path)
        for ship_id, ship_data in region_stats.items():
            ship_id = str(ship_id)
            if ship_data[0] >= 1000:
                if ship_id not in ship_data_result['ship_data']:
                    ship_data_result['ship_data'][ship_id] = {}
                ship_data_result['ship_data'][ship_id] = {
                    "win_rate": round(ship_data[1]/ship_data[0]*100,4),
                    "avg_damage": round(ship_data[2]/ship_data[0],4),
                    "avg_frags": round(ship_data[3]/ship_data[0],4),
                    "avg_exp": round(ship_data[4]/ship_data[0],4)
                }
        output_path = DATA_DIR / f'json/ship_data.json'
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(ship_data_result, f, ensure_ascii=False)
    finally:
        cursor.close()
    