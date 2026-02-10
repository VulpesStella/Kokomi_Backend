import time
import traceback
import json
import pymysql
import requests
from datetime import datetime
from logger import logger
from settings import WG_API_TOKEN, LESTA_API_TOKEN
from middlewares import redis_client, db_pool


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

def get_refresh_time(activity_level: int, lbt: int, enable_recent: bool, enable_daily: bool):
    hour = 60*60
    day = 24*hour
    refresh_time_dict = {
        0: [5*day,  6*hour,   2*hour],
        1: [25*day, 12*hour,  2*hour],
        2: [1*day,  0.5*hour, 20*60],
        3: [2*day,  1*hour,   25*60],
        4: [3*day,  2*hour,   30*60],
        5: [5*day,  3*hour,   30*60],
        6: [7*day,  4*hour,   60*60],
        7: [15*day, 5*hour,   2*hour],
        8: [20*day, 6*hour,   2*hour],
        9: [30*day, 12*hour,  2*hour]
    }
    if enable_daily:
        if lbt < 60*60:
            return 5*60
        else:
            return refresh_time_dict[activity_level][2]
    elif enable_recent:
        return refresh_time_dict[activity_level][1]
    else:
        return refresh_time_dict[activity_level][0]

def get_max_id():
    # 先获取数据库中id最大值，确定循环上限
    conn = db_pool.connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    try:
        sql = """
            SELECT 
                MAX(id) AS max_id 
            FROM user_stats;
        """
        cursor.execute(sql)
        data = cursor.fetchone()
        return data['max_id']
    except:
        logger.error(f'Read max_id failed')
    finally:
        cursor.close()
        conn.close()

def get_recent_user():
    recent_user = set()
    recents_user = set()
    # 先获取数据库中id最大值，确定循环上限
    conn = db_pool.connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    try:
        sql = """
            SELECT 
                account_id, 
                enable_recent, 
                enable_daily 
            FROM recent;
        """
        cursor.execute(sql)
        datas = cursor.fetchall()
        for data in datas:
            if data['enable_recent'] == 1:
                recent_user.add(data['account_id'])
                if data['enable_daily'] == 1:
                    recents_user.add(data['account_id'])
    except:
        logger.error(f'Read recent_user failed')
    finally:
        cursor.close()
        conn.close()
    return recent_user, recents_user

def update_version(region_id: int, full_version: str):
    # 先获取数据库中id最大值，确定循环上限
    conn = db_pool.connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
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
        if data is None or data['short_version'] != short_version:
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
                sql,[short_version, region_id]
            )
        conn.commit()
    except:
        conn.rollback()
        logger.error((f"{traceback.format_exc()}"))
    finally:
        cursor.close()
        conn.close()

def fetch_data(url):
    try:
        resp = requests.get(url,timeout=5)
        if resp.status_code == 200:
            result = resp.json()
            logger.debug(f'200 {url}')
            return result
        logger.warning(f'Code_{resp.status_code} {url}')
    except Exception as e:
        logger.warning(f"{type(e).__name__} {url}")

def post_data(url):
    try:
        body = [{"query":"query Version {\n  version\n}"}]
        resp = requests.post(url,json=body,timeout=5)
        if resp.status_code == 200:
            result = resp.json()
            logger.debug(f'200 {url}')
            return result
        logger.warning(f'Code_{resp.status_code} {url}')
    except Exception as e:
        logger.warning(f"{type(e).__name__} {url}")

def get_online_player():
    try:
        result = redis_client.get('status:online_refresh_time')
        online_refresh_time = json.loads(result) if result else None
    except:
        online_refresh_time = None
    now_time = now_iso()
    region_dict = {1: 'asia',2: 'eu',3: 'na',4: 'ru',5: 'cn'}
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
    for region_id in [1, 2, 3, 4]:
        if online_refresh_time == timestamp:
            return
        region = region_dict[region_id]
        base_url = ONLINE_API[region_id]
        if region_id == 4:
            url = f'{base_url}/wgn/servers/info/?application_id={LESTA_API_TOKEN}&game=wows'
        else:
            url = f'{base_url}/wgn/servers/info/?application_id={WG_API_TOKEN}&game=wows'
        result = fetch_data(url)
        key = f"metrics:http:{now_time[:10]}:{region}_total"
        redis_client.incrby(key, 1)
        if result is None:
            key = f"metrics:http:{now_time[:10]}:{region}_error"
            redis_client.incrby(key, 1)
        else:
            try:
                users = result['data']['wows'][0]['players_online']
                online_data['total'] += users
                online_data[region] = users
                total_region += 1
            except:
                pass
    key = f"online:{timestamp}"
    redis_client.set(key, json.dumps(online_data), 25*60*60)
    if total_region == 4:
        redis_client.set('status:online_refresh_time', json.dumps(timestamp))
    logger.info(f"Total: {online_data['total']}")
    logger.info(f"Asia: {online_data['asia']} | Eu: {online_data['eu']} | Na: {online_data['na']} | Eu: {online_data['eu']} | Cn: {online_data['cn']}")

def get_version():
    try:
        result = redis_client.get('status:version_refresh_time')
        online_refresh_time = json.loads(result) if result else None
    except:
        online_refresh_time = None
    now_time = now_iso()
    region_dict = {1: 'asia',2: 'eu',3: 'na',4: 'ru',5: 'cn'}
    version_data = {
        'asia': '/',
        'eu': '/',
        'na': '/',
        'ru': '/',
        'cn': '/'
    }
    total_region = 0
    timestamp = int(time.time()) // 3600 * 3600
    for region_id in [1, 2, 3, 4, 5]:
        if online_refresh_time == timestamp:
            return
        region = region_dict[region_id]
        base_url = VORTEX_API_URL_LIST[region_id]
        url = f'{base_url}/api/v2/graphql/glossary/version/'
        result = post_data(url)
        key = f"metrics:http:{now_time[:10]}:{region}_total"
        redis_client.incrby(key, 1)
        if result is None:
            key = f"metrics:http:{now_time[:10]}:{region}_error"
            redis_client.incrby(key, 1)
        else:
            try:
                version = result[0]['data']['version']
                version_data[region] = ".".join(version.split(".")[:2])
                update_version(region_id, version)
                total_region += 1
            except:
                logger.error((f"{traceback.format_exc()}"))
    if total_region == 5:
        redis_client.set('status:version_refresh_time', timestamp)
    logger.info(f"Asia: {version_data['asia']} | Eu: {version_data['eu']} | Na: {version_data['na']} | Ru: {version_data['ru']} | Cn: {version_data['cn']}")
