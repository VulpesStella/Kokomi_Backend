import os
import csv
import time
import gzip
import json
import httpx
import asyncio
import traceback
from redis import Redis
from pymysql import Connection
from pymysql.cursors import Cursor
from datetime import datetime, timezone

from logger import logger
from settings import (
    BATCH_SIZE,
    WG_API_TOKEN, 
    LESTA_API_TOKEN, 
    DATA_DIR,
    TEMP_DIR
)


SERVER_RESET_OFFSET = 5 * 3600
REGION_UTC_LIST = {1:8, 2:1, 3:-7, 4:3, 5:8}
ACHIEVEMENTS = [
    'PCH001_DoubleKill', 'PCH002_OneSoldierInTheField', 'PCH003_MainCaliber', 
    'PCH004_Dreadnought', 'PCH005_Support', 'PCH006_Withering', 
    'PCH010_Retribution', 'PCH011_InstantKill', 'PCH012_Arsonist', 
    'PCH014_Headbutt', 'PCH016_FirstBlood', 'PCH017_Fireproof', 
    'PCH018_Unsinkable', 'PCH019_Detonated', 'PCH020_ATBACaliber', 
    'PCH023_Warrior', 'PCH174_AirDefenseExpert', 'PCH364_MainCaliber_Squad', 
    'PCH365_ClassDestroy_Squad', 'PCH366_Warrior_Squad', 'PCH367_Support_Squad', 
    'PCH368_Frag_Squad', 'PCH395_CombatRecon'
]
OFFICIAL_API_ENDPOINTS = {
    1: 'https://api.worldofwarships.asia',
    2: 'https://api.worldofwarships.eu',
    3: 'https://api.worldofwarships.com',
    4: 'https://api.korabli.su',
    5: None
}
OFFICIAL_API = {
    1: 'https://api.worldoftanks.asia',
    2: 'https://api.worldoftanks.eu',
    3: 'https://api.worldoftanks.com',
    4: 'https://api.tanki.su',
    5: None
}

def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")

def formtimestamp(region_id: int, diff: int = 0):
    timestamp = time.time() + REGION_UTC_LIST[region_id]*3600 - SERVER_RESET_OFFSET - diff*24*60*60
    return datetime.fromtimestamp(timestamp, timezone.utc).strftime("%Y%m%d")

def get_region(region_id: int):
    region_dict = {1: 'asia',2: 'eu',3: 'na',4: 'ru',5: 'cn'}
    return region_dict[region_id]

def get_region_id(region: str):
    region_id_dict = {
        'asia': 1,
        'eu': 2,
        'na': 3,
        'ru': 4,
        'cn': 5
    }
    return region_id_dict.get(region)

def compress(data: dict):
    # 数据压缩
    if data:
        json_str = json.dumps(
            data,
            ensure_ascii=False,
            separators=(",", ":")  # 去空格，减小体积
        )
        json_bytes = json_str.encode("utf-8")
        return gzip.compress(json_bytes)
    else:
        return None

def decompress(gzip_bytes: bytes):
    # 数据解压
    if gzip_bytes:
        decompressed = gzip.decompress(gzip_bytes)
        return json.loads(decompressed)
    else:
        return None

def get_update_ids(conn: Connection, redis_client: Redis) -> list:
    result = {}
    cursor = 0
    while True:
        cursor, keys = redis_client.scan(cursor=cursor, match="token:auth:*", count=100)
        if keys:
            values = redis_client.mget(keys)
            result.update(dict(zip(keys, values)))
        if cursor == 0:
            break
    update_list = []
    conn.begin()
    cursor: Cursor = conn.cursor()
    try:
        for user_id in result.keys():
            user_data = json.loads(result[user_id])
            account_id = int(user_id.replace('token:auth:', ''))
            region_id = get_region_id(user_data['region'])
            sql = """
                SELECT 
                    update_date 
                FROM user_private 
                WHERE account_id = %s;
            """
            cursor.execute(sql,[account_id])
            data = cursor.fetchone()
            if data is None:
                sql = """
                    INSERT INTO user_private (
                        account_id
                    ) VALUES (
                        %s
                    );
                """
                cursor.execute(sql,[account_id])
                update_list.append([region_id, account_id, user_data['auth']])
            elif data[0] != formtimestamp(region_id):
                update_list.append([region_id, account_id, user_data['auth']])
        conn.commit()
    except Exception:
        conn.rollback()
        logger.error((f"{traceback.format_exc()}"))
    finally:
        cursor.close()
    return update_list

def get_expiring_ids(conn: Connection, redis_client: Redis):
    try:
        result = redis_client.get('status:token_refresh_time')
        stats_refresh_time = json.loads(result) if result else None
    except Exception:
        stats_refresh_time = None
    timestamp = int(time.time())
    # 每6h刷新一次
    if stats_refresh_time and (timestamp - stats_refresh_time <= 6*60*60):
        return []
    cursor = 0
    expiring_user_ids = []
    while True:
        cursor, keys = redis_client.scan(cursor=cursor, match="token:auth:*", count=1000)
        for key in keys:
            ttl = redis_client.ttl(key)
            if 0 < ttl <= 2*24*60*60:
                expiring_user_ids.append(int(key.replace('token:auth:', '')))
        if cursor == 0:
            break
    update_list = []
    cursor: Cursor = conn.cursor()
    try:
        sql = """
            SELECT id FROM bind_idx WHERE renew_token = 1;
        """
        cursor.execute(sql)
        rows = cursor.fetchall()
        renew_token_ids = []
        for row in rows:
            user_id = row[0]
            sql = """
                SELECT game_id FROM bind_list WHERE user_id = %s;
            """
            cursor.execute(sql, [user_id])
            game_ids = cursor.fetchall()
            for game_data in game_ids:
                renew_token_ids.append(game_data[0])
            for game_id in renew_token_ids:
                sql = """
                    SELECT region_id, account_id FROM user_base WHERE id = %s;
                """
                cursor.execute(sql, [game_id])
                data = cursor.fetchone()
                if data is None:
                    continue
                region_id = data[0]
                account_id = data[1]
                if account_id in expiring_user_ids:
                    result = redis_client.get(f'token:auth:{account_id}')
                    token_data = json.loads(result) if result else None
                    if token_data is None:
                        continue
                    update_list.append([region_id,account_id,token_data['auth']])
        redis_client.set('status:token_refresh_time', json.dumps(timestamp))
    except Exception:
        logger.error((f"{traceback.format_exc()}"))
    finally:
        cursor.close()
    return update_list

async def fetch_data(url):
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(url, timeout=5)
            requset_code = res.status_code
            requset_result = res.json()
            if requset_code == 200:
                logger.debug(f'200 {url}')
                if requset_result['status'] == 'error' and requset_result['error']['message'] == 'INVALID_ACCESS_TOKEN':
                    return {}
                elif requset_result['status'] == 'error':
                    return 'GameAPIError'
                return requset_result
            logger.warning(f'Code_{requset_code} {url}')
            return f'HTTP_STATUS_{requset_code}'
    except Exception as e:
        logger.warning(f"{type(e).__name__} {url}")
        return f'ERROR_{type(e).__name__}'

async def post_data(url, body):
    try:
        async with httpx.AsyncClient() as client:
            res = await client.post(url, data=body, timeout=5)
            requset_code = res.status_code
            requset_result = res.json()
            if requset_code == 200:
                logger.debug(f'200 {url}')
                if requset_result['status'] == 'error' and requset_result['error']['message'] == 'INVALID_ACCESS_TOKEN':
                    return {}
                elif requset_result['status'] == 'error':
                    return 'GameAPIError'
                return requset_result
            logger.warning(f'Code_{requset_code} {url}')
            return f'HTTP_STATUS_{requset_code}'
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

async def update_user_private(
    conn: Connection, 
    redis_client: Redis,
    region_id: int,
    account_id: int,
    auth_value: str
):
    if region_id == 4:
        token = LESTA_API_TOKEN
    else:
        token = WG_API_TOKEN
    api_url = OFFICIAL_API_ENDPOINTS.get(region_id)
    urls = [
        f'{api_url}/wows/account/info/?application_id={token}&account_id={account_id}&access_token={auth_value}&extra=private.port',
        f'{api_url}/wows/account/achievements/?application_id={token}&account_id={account_id}'
    ]
    tasks = []
    responses = []
    async with asyncio.Semaphore(len(urls)):
        for url in urls:
            tasks.append(fetch_data(url))
        responses = await asyncio.gather(*tasks)
    error = verify_responses(get_region(region_id), redis_client, responses)
    if error != None:
        return error
    for response in responses:
        if response == {}:
            redis_client.delete(f'token:auth:{account_id}')
            return 'TokenExpired'
        if response['meta']['hidden'] != None:
            redis_client.delete(f'token:auth:{account_id}')
            return "HiddenProfile"
    if responses[0]['data'][str(account_id)] is None:
        redis_client.delete(f'token:auth:{account_id}')
        return 'NoData'
    basic_data = responses[0]['data'][str(account_id)]
    result = {
        'update_date': formtimestamp(region_id),
        'battles': basic_data['statistics']['battles'],
        'life_time': basic_data['private']['battle_life_time'],
        'distance': basic_data['statistics']['distance'],
        'gold': basic_data['private']['gold'],
        'free_xp': basic_data['private']['free_xp'],
        'credits': basic_data['private']['credits'],
        'slots': basic_data['private']['slots']
    }
    result['port'] = basic_data['private']['port']
    achieve_data = responses[1]['data'][str(account_id)].get('battle')
    result['achieve'] = {}
    for achieve_name in ACHIEVEMENTS:
        if achieve_name in achieve_data:
            result['achieve'][achieve_name[:6]] = achieve_data[achieve_name]
    conn.begin()
    cursor: Cursor = conn.cursor()
    try:
        sql = """
            UPDATE user_private 
            SET 
                update_date = %s, 
                battles = %s, 
                life_time = %s, 
                distance = %s, 
                gold = %s, 
                free_xp = %s, 
                credits = %s, 
                slots = %s, 
                port = %s, 
                achieve = %s 
            WHERE account_id = %s;
        """
        cursor.execute(sql,[
            result['update_date'],
            result['battles'],
            result['life_time'],
            result['distance'],
            result['gold'],
            result['free_xp'],
            result['credits'],
            result['slots'],
            json.dumps(result['port']),
            json.dumps(result['achieve']),
            account_id
        ])
        conn.commit()
    except Exception:
        conn.rollback()
        logger.error((f"{traceback.format_exc()}"))
    finally:
        cursor.close()
    return 'Success'

async def update_user_token(
    redis_client: Redis,
    region_id: int,
    account_id: int,
    auth_value: str
):
    if region_id == 4:
        token = LESTA_API_TOKEN
    else:
        token = WG_API_TOKEN
    api_url = OFFICIAL_API.get(region_id)
    region = get_region(region_id)
    url = f'{api_url}/wot/auth/prolongate/'
    responses = [
        await post_data(url, {'application_id': token,'access_token': auth_value,'expires_at':int(time.time())+14*24*60*60-30})
    ]
    error = verify_responses(region, redis_client, responses)
    if error != None:
        return error
    response = responses[0]
    if response == {}:
        redis_client.delete(f'token:auth:{account_id}')
        return 'InvalidToken'
    redis_client.set(f'token:auth:{account_id}',json.dumps({'region': region,'auth': response['data']['access_token']}),response['data']['expires_at']-int(time.time())-30)
    return 'Success'

def process_region_stats(conn: Connection, redis_client: Redis):
    try:
        result = redis_client.get('status:stats_refresh_time')
        stats_refresh_time = json.loads(result) if result else None
    except Exception:
        stats_refresh_time = None
    timestamp = int(time.time())
    # 每12h刷新一次
    if stats_refresh_time and (timestamp - stats_refresh_time <= 12*60*60):
        return
    if datetime.now().hour in [3, 4, 12, 13, 20, 21, 22, 23]:
        return
    cursor: Cursor = conn.cursor()
    try:
        sql = """
            SELECT 
                MAX(id) 
            FROM user_base;
        """
        cursor.execute(sql)
        max_id_result = cursor.fetchone()
        max_id = max_id_result[0]
        logger.info(f'Max ID: {max_id}')
        sql = """
            SELECT 
                region_id, 
                short_version 
            FROM region_version;
        """
        cursor.execute(sql)
        regions_version = cursor.fetchall()
        region_version_map = {}
        for region_v in regions_version:
            region_version_map[region_v[0]] = region_v[1]
        all_region_stats = {i: {} for i in range(1, 6)}
        for offset in range(0, max_id, BATCH_SIZE):
            if offset % 10000 == 0:
                logger.info(f'[{offset+1}/{max_id}] Processing~')
            sql = """
                SELECT 
                    b.region_id, 
                    b.account_id, 
                    c.cache 
                FROM user_base AS b 
                LEFT JOIN user_cache AS c 
                  ON b.account_id = c.account_id  
                WHERE b.id BETWEEN %s AND %s;
            """
            cursor.execute(sql, [offset+1, offset+BATCH_SIZE])
            rows = cursor.fetchall()
            for row in rows:
                # 获取 region_id 和 cache 数据
                if row is None:
                    continue
                account_id = row[1]
                region_id = row[0]
                blob_data = row[2]
                if not blob_data:
                    continue
                user_ship_data = decompress(blob_data)
                for ship_id, stats in user_ship_data.items():
                    if ship_id not in all_region_stats[region_id]:
                        all_region_stats[region_id][ship_id] = [0] * 12
                    target_list = all_region_stats[region_id][ship_id]
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
                    all_region_stats[region_id][ship_id] = target_list
        headers = [
            'ship_id', 'battles_count', 'wins', 'damage_dealt', 'frags', 
            'original_exp', 'survived', 'max_exp', 'max_exp_id', 
            'max_damage_dealt', 'max_damage_id', 'max_battles', 'max_battles_id'
        ]
        ship_data_result = {
            "update_time": int(time.time()),
            "ship_data": {}
        }
        region_dict = {1: 'asia',2: 'eu',3: 'na',4: 'ru',5: 'cn'}
        for r_id in range(1, 6):
            region = region_dict[r_id]
            stats_dict = all_region_stats[r_id]
            short_ver = region_version_map[r_id]
            output_path = DATA_DIR / f'stats/{r_id}/{short_ver}.csv'
            temp_path = TEMP_DIR / f'{short_ver}.csv'
            with open(temp_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(headers)
                for ship_id, data in stats_dict.items():
                    writer.writerow([ship_id] + data)
                csvfile.flush()
                os.fsync(csvfile.fileno())
            os.replace(temp_path, output_path)
            if temp_path.exists():
                os.remove(temp_path)
            for ship_id, ship_data in stats_dict.items():
                ship_id = str(ship_id)
                if ship_data[0] >= 1000:
                    if ship_id not in ship_data_result['ship_data']:
                        ship_data_result['ship_data'][ship_id] = {
                            'asia': {}, 'eu': {}, 'na': {}, 'ru': {}, 'cn': {}
                        }
                    ship_data_result['ship_data'][ship_id][region] = {
                        "win_rate": round(ship_data[1]/ship_data[0]*100,4),
                        "avg_damage": round(ship_data[2]/ship_data[0],4),
                        "avg_frags": round(ship_data[3]/ship_data[0],4),
                        "avg_exp": round(ship_data[4]/ship_data[0],4)
                    }
        output_path = DATA_DIR / f'json/ship_data.json'
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(ship_data_result, f, ensure_ascii=False)
        redis_client.set('status:stats_refresh_time', json.dumps(timestamp))
    finally:
        cursor.close()
    