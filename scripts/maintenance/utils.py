import time
import json
import requests
import traceback
from redis import Redis
from pymysql import Connection
from pymysql.cursors import Cursor
from datetime import datetime

from logger import logger
from settings import (
    WG_API_TOKEN, 
    LESTA_API_TOKEN, 
    BATCH_SIZE
)


HOUR: int = 60 * 60
DAY: int = 24 * HOUR
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
ONLINE_API = {
    1: 'https://api.worldoftanks.asia',
    2: 'https://api.worldoftanks.eu',
    3: 'https://api.worldoftanks.com',
    4: 'https://api.tanki.su',
    5: None
}
VORTEX_API_URL_LIST = {
    1: 'https://vortex.worldofwarships.asia',
    2: 'https://vortex.worldofwarships.eu',
    3: 'https://vortex.worldofwarships.com',
    4: 'https://vortex.korabli.su',
    5: 'https://vortex.wowsgame.cn'
}

def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")

def get_region(region_id: int):
    region_dict = {1: 'asia',2: 'eu',3: 'na',4: 'ru',5: 'cn'}
    return region_dict[region_id]

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
        resp = requests.get(url,timeout=5)
        if resp.status_code == 200:
            result = resp.json()
            logger.debug(f'200 {url}')
            return result
        logger.warning(f'Code_{resp.status_code} {url}')
        return f'HTTP_STATUS_{resp.status_code}'
    except Exception as e:
        logger.warning(f"{type(e).__name__} {url}")
        return f'ERROR_{type(e).__name__}'

def post_data(url):
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

def verify_responses(region: str, redis_client: Redis, responses: list):
    error = 0
    error_return = None
    now_time = now_iso()
    for response in responses:
        if isinstance(response, str):
            error += 1
            error_return = response
    key = f"metrics:http:{now_time[:10]}:{region}_total"
    redis_client.incrby(key, len(responses))
    if error == 0:
        return None
    else:
        key = f"metrics:http:{now_time[:10]}:{region}_error"
        redis_client.incrby(key, error)
        return error_return

def get_update_ids(conn: Connection, redis_client: Redis):
    # 从数据库中批量读取并判断那些用户需要更新
    update_list = []
    cursor: Cursor = conn.cursor()
    try:
        sql = """
            SELECT 
                MAX(id) 
            FROM user_stats;
        """
        cursor.execute(sql)
        data = cursor.fetchone()
        max_id = data[0] if data else 0
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
        logger.info(f'Max ID: {max_id}')
        logger.info(f'Recent: {len(recent)} | Recents: {len(recents)}')
        temp_update_list = []
        now_ts = int(time.time())
        for offset in range(0, max_id, BATCH_SIZE):
            sql = """
                SELECT 
                    b.region_id, 
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
                region_id = user[0]
                account_id = user[1]
                enable_recent = account_id in recent
                enable_daily = account_id in recents
                touch_time = user[4] if user[4] else 0
                last_battle_time = user[3] if user[3] else 0
                next_refresh_time = get_refresh_time(
                    user[2], 
                    now_ts - last_battle_time, 
                    enable_recent, 
                    enable_daily
                ) + touch_time
                if next_refresh_time <= now_ts:
                    temp_update_list.append((region_id,account_id))
        pipe = redis_client.pipeline()
        keys = [f"user_refresh:{rid}:{aid}" for rid, aid in temp_update_list]
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

def update_version(conn: Connection, region_id: int, full_version: str):
    conn.begin()
    cursor: Cursor = conn.cursor()
    try:
        sql = """
            SELECT 
                short_version 
            FROM region_version 
            WHERE region_id = %s;
        """
        cursor.execute(sql, [region_id])
        data = cursor.fetchone()
        short_version = ".".join(full_version.split(".")[:2])
        if data is None or data[0] != short_version:
            sql = """
                UPDATE region_version 
                SET 
                    short_version = %s, 
                    version_start = CURRENT_TIMESTAMP, 
                    full_version = %s 
                WHERE region_id = %s;
            """
            cursor.execute(
                sql,[short_version, full_version, region_id]
            )
        else:
            sql = """
                UPDATE region_version 
                SET 
                    full_version = %s 
                WHERE region_id = %s;
            """
            cursor.execute(
                sql,[full_version, region_id]
            )
        conn.commit()
    except Exception:
        conn.rollback()
        logger.error((f"{traceback.format_exc()}"))
    finally:
        cursor.close()

def refresh_online_player(redis_client: Redis):
    try:
        result = redis_client.get('status:online_refresh_time')
        online_refresh_time = json.loads(result) if result else None
    except Exception:
        online_refresh_time = None
    online_data = {
        'total': 0,
        'asia': '/',
        'eu': '/',
        'na': '/',
        'ru': '/',
        'cn': '/'
    }
    total_region = 0
    timestamp = int(time.time()) // 600 * 600
    if online_refresh_time == timestamp:
        return
    for region_id in [1, 2, 3, 4]:
        base_url = ONLINE_API[region_id]
        if region_id == 4:
            url = f'{base_url}/wgn/servers/info/?application_id={LESTA_API_TOKEN}&game=wows'
        else:
            url = f'{base_url}/wgn/servers/info/?application_id={WG_API_TOKEN}&game=wows'
        result = fetch_data(url)
        error = verify_responses(get_region(region_id), redis_client, [result])
        if error != None:
            pass
            # return error
        else:
            try:
                users = result['data']['wows'][0]['players_online']
                online_data['total'] += users
                online_data[get_region(region_id)] = users
                total_region += 1
            except Exception:
                logger.error(f"{traceback.format_exc()}")
    key = f"online:{timestamp}"
    redis_client.set(key, json.dumps(online_data), 25*60*60)
    if total_region == 4:
        redis_client.set('status:online_refresh_time', json.dumps(timestamp))
    return [online_data['total'], online_data['asia'], online_data['eu'], online_data['na'], online_data['ru'], online_data['cn']]

def refresh_game_version(conn: Connection, redis_client: Redis):
    try:
        result = redis_client.get('status:version_refresh_time')
        version_refresh_time = json.loads(result) if result else None
    except Exception:
        version_refresh_time = None
    version_data = {
        'asia': '/',
        'eu': '/',
        'na': '/',
        'ru': '/',
        'cn': '/'
    }
    total_region = 0
    timestamp = int(time.time())
    if version_refresh_time and (timestamp - version_refresh_time) < 6*60*60:
        return
    for region_id in [1, 2, 3, 4, 5]:
        base_url = VORTEX_API_URL_LIST[region_id]
        url = f'{base_url}/api/v2/graphql/glossary/version/'
        result = post_data(url)
        error = verify_responses(get_region(region_id), redis_client, [result])
        if error != None:
            pass
            # return error
        else:
            try:
                version = result[0]['data']['version']
                version_data[get_region(region_id)] = ".".join(version.split(".")[:2])
                update_version(conn, region_id, version)
                total_region += 1
            except Exception:
                logger.error(f"{traceback.format_exc()}")
    if total_region == 5:
        redis_client.set('status:version_refresh_time', timestamp)
    return [version_data['asia'], version_data['eu'], version_data['na'], version_data['ru'], version_data['cn']]
