import json
import gzip
import time
import random
import asyncio
import traceback
from redis import Redis
from httpx import AsyncClient
from pymysql import Connection
from pymysql.cursors import Cursor
from datetime import datetime, timezone

from logger import logger
from settings import BATCH_SIZE, DATA_DIR, VORTEX_API, REGION


TIME_DIFFERENCES = [
    (1 * 24 * 60 * 60, 2),
    (3 * 24 * 60 * 60, 3),
    (7 * 24 * 60 * 60, 4),
    (30 * 24 * 60 * 60, 5),
    (90 * 24 * 60 * 60, 6),
    (180 * 24 * 60 * 60, 7),
    (360 * 24 * 60 * 60, 8)
]

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def get_activity_level(is_public: bool, total_battles: int = 0, last_battle_time: int = 0):
    "获取activity_level"
    if not is_public:
        return 0
    if total_battles == 0 or last_battle_time == 0:
        return 1
    current_timestamp = int(time.time())
    time_since_last_battle = current_timestamp - last_battle_time
    for time_limit, return_value in TIME_DIFFERENCES:
        if time_since_last_battle <= time_limit:
            return return_value
    return 9

def get_insignias(data: dict):
    if data is None or data == {}:
        return None
    else:
        return f"{data['texture_id']}-{data['symbol_id']}-{data['border_color_id']}-{data['background_color_id']}-{data['background_id']}"

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

def get_version():
    file_path = DATA_DIR / f"json/version.json"
    with open(file_path, "r", encoding="utf-8") as f:
        version_data = json.load(f)
        return version_data['version']

def get_update_ids(mysql_connection: Connection):
    # 从数据库中批量读取并判断那些用户需要更新
    update_list = []
    cursor: Cursor = mysql_connection.cursor()
    try:
        sql = f"""
            SELECT 
                MAX(id) 
            FROM user_stats;
        """
        cursor.execute(sql)
        data = cursor.fetchone()
        max_id = data[0]
        logger.info(f'Max ID: {max_id}')
        for offset in range(0, max_id, BATCH_SIZE):
            sql = """
                SELECT 
                    s.account_id,
                    s.pvp_battles, 
                    c.pvp_count 
                FROM user_stats AS s 
                LEFT JOIN user_cache AS c 
                    ON s.account_id = c.account_id 
                WHERE s.id BETWEEN %s AND %s;
            """
            cursor.execute(sql, [offset+1, offset+BATCH_SIZE])
            rows = cursor.fetchall()
            for row in rows:
                if row[1] != row[2]:
                    update_list.append(row[0])
    except Exception:
        logger.error((f"{traceback.format_exc()}"))
    finally:
        cursor.close()
    return update_list

async def fetch_data(async_client: AsyncClient, url: str):
    try:
        res = await async_client.get(url)
        requset_code = res.status_code
        requset_result = res.json()
        if requset_code == 200:
            logger.debug(f'200 {url}')
            return requset_result['data']
        if requset_code == 404:
            logger.debug(f'404 {url}')
            return {}
        logger.warning(f'Code_{requset_code} {url}')
        return f'HTTP_STATUS_{requset_code}'
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

def update_base(mysql_connection: Connection, account_id: int, user_basic: dict):
    refresh_data = {
        'is_enabled': 0,
        'activity_level': 0,
        'is_public': 0,
        'username': "",
        'register_time': None,
        'insignias': None,
        'total_battles': 0,
        'pvp_battles': 0,
        'ranked_battles': 0,
        'last_battle_at': 0
    }
    if user_basic:
        user_basic = user_basic[str(account_id)]
    if 'hidden_profile' in user_basic:
        refresh_data['is_enabled'] = 1
        refresh_data['is_public'] = 0
        refresh_data['activity_level'] = get_activity_level(is_public=0)
        refresh_data['username'] = user_basic['name']
    elif (
        user_basic == None or user_basic == {} or
        'statistics' not in user_basic or 
        'basic' not in user_basic['statistics'] or 
        user_basic['statistics']['basic']['leveling_points'] == 0
    ):
        refresh_data['is_enabled'] = 0
    else:
        refresh_data['is_enabled'] = 1
        refresh_data['is_public'] = 1
        total_battles = user_basic['statistics']['basic']['leveling_points']
        if total_battles >= 1000000:
            total_battles = total_battles - 1000000
        refresh_data['activity_level'] = get_activity_level(
            is_public=1,
            total_battles= total_battles,
            last_battle_time=user_basic['statistics']['basic']['last_battle_time']
        )
        if REGION == 'ru':
            ranked_count = 0
            ranked_count += 0 if user_basic['statistics']['rank_solo'] == {} else user_basic['statistics']['rank_solo']['battles_count']
            ranked_count += 0 if user_basic['statistics']['rating_solo'] == {} else user_basic['statistics']['rating_solo']['battles_count']
            ranked_count += 0 if user_basic['statistics']['rating_div'] == {} else user_basic['statistics']['rating_div']['battles_count']
        else:
            ranked_count = 0 if user_basic['statistics']['rank_solo'] == {} else user_basic['statistics']['rank_solo']['battles_count']
        refresh_data['username'] = user_basic['name']
        refresh_data['register_time'] = user_basic['statistics']['basic']['created_at']
        refresh_data['insignias'] = get_insignias(user_basic['dog_tag'])
        refresh_data['total_battles'] = user_basic['statistics']['basic']['leveling_points']
        refresh_data['pvp_battles'] = 0 if user_basic['statistics']['pvp'] == {} else user_basic['statistics']['pvp']['battles_count']
        refresh_data['ranked_battles'] = ranked_count
        refresh_data['last_battle_at'] = user_basic['statistics']['basic']['last_battle_time']
    cursor: Cursor = mysql_connection.cursor()
    try:
        sql = """
            SELECT 
                username, 
                UNIX_TIMESTAMP(register_time), 
                insignias 
            FROM user_base 
            WHERE account_id = %s;
        """
        cursor.execute(sql, [account_id])
        result = cursor.fetchone()
        if refresh_data['is_enabled'] == 0:
            sql = """
                UPDATE user_stats 
                SET 
                    is_enabled = %s, 
                    touch_at = CURRENT_TIMESTAMP 
                WHERE account_id = %s;
            """
            cursor.execute(sql, [refresh_data['is_enabled'], account_id])
        elif refresh_data['is_public'] == 0:
            sql = """
                UPDATE user_base 
                SET 
                    username = %s, 
                    touch_at = CURRENT_TIMESTAMP 
                WHERE account_id = %s;
            """
            cursor.execute(sql, [refresh_data['username'], account_id])
            sql = """
                UPDATE user_stats 
                SET 
                    is_enabled = %s, 
                    activity_level = %s, 
                    is_public = %s, 
                    total_battles = 0, 
                    pvp_battles = 0, 
                    ranked_battles = 0,
                    last_battle_at = NULL,
                    touch_at = CURRENT_TIMESTAMP 
                WHERE account_id = %s;
            """
            cursor.execute(sql, [refresh_data['is_enabled'], refresh_data['activity_level'], refresh_data['is_public'], account_id])
        else:
            if (
                result[0] != refresh_data['username'] or
                result[1] != refresh_data['register_time'] or
                result[2] != refresh_data['insignias']
            ):
                sql = """
                    UPDATE user_base 
                    SET 
                        username = %s, 
                        register_time = FROM_UNIXTIME(%s), 
                        insignias = %s, 
                        touch_at = CURRENT_TIMESTAMP 
                    WHERE account_id = %s;
                """
                cursor.execute(sql, [refresh_data['username'],refresh_data['register_time'],refresh_data['insignias'],account_id])
            sql = """
                UPDATE user_stats 
                SET 
                    is_enabled = %s, 
                    activity_level = %s, 
                    is_public = %s, 
                    total_battles = %s, 
                    pvp_battles = %s, 
                    ranked_battles = %s, 
                    last_battle_at = FROM_UNIXTIME(%s), 
                    touch_at = CURRENT_TIMESTAMP 
                WHERE account_id = %s;
            """
            cursor.execute(sql, [
                refresh_data['is_enabled'],refresh_data['activity_level'],refresh_data['is_public'],
                refresh_data['total_battles'],refresh_data['pvp_battles'],refresh_data['ranked_battles'],
                refresh_data['last_battle_at'],account_id
            ])
        mysql_connection.commit()
    except Exception:
        mysql_connection.rollback()
        logger.error((f"{traceback.format_exc()}"))
    finally:
        cursor.close()

async def get_cache_data(
    mysql_connection: Connection,
    redis_client: Redis, 
    async_client: AsyncClient,
    account_id: int,
    ac_value: str = None
):
    base_url = random.choice(VORTEX_API)
    urls = [
        f'{base_url}/api/accounts/{account_id}/' + (f'?ac={ac_value}' if ac_value else ''),
        f'{base_url}/api/accounts/{account_id}/ships/' + (f'?ac={ac_value}' if ac_value else ''),
        f'{base_url}/api/accounts/{account_id}/ships/pvp/' + (f'?ac={ac_value}' if ac_value else '')
    ]
    tasks = [fetch_data(async_client, url) for url in urls]
    responses = await asyncio.gather(*tasks)
    error = verify_responses(redis_client, responses)
    if error != None:
        return error
    result = {}
    overall = {}
    basic_data = responses[0]
    update_base(mysql_connection, account_id, basic_data)
    if basic_data:
            basic_data = basic_data[str(account_id)]
    if 'hidden_profile' in basic_data:
        return {}
    if (
        basic_data == None or basic_data == {} or
        'statistics' not in basic_data or 
        'basic' not in basic_data['statistics'] or 
        basic_data['statistics']['basic']['leveling_points'] == 0
    ):
        return {}
    pvp_count = basic_data['statistics']['pvp'].get('battles_count')
    if pvp_count and pvp_count > 0:
        overall = {
            'battles_count': pvp_count,
            'win_rate': round(basic_data['statistics']['pvp']['wins']/pvp_count*100,4),
            'avg_damage': round(basic_data['statistics']['pvp']['damage_dealt']/pvp_count,4),
            'avg_frags': round(basic_data['statistics']['pvp']['frags']/pvp_count,4),
            'max_damage': basic_data['statistics']['pvp']['max_damage_dealt'],
            'max_damage_id': basic_data['statistics']['pvp']['max_damage_dealt_vehicle'],
            'max_exp': basic_data['statistics']['pvp']['max_exp'],
            'max_exp_id': basic_data['statistics']['pvp']['max_exp_vehicle']
        }
    else:
        overall = {
            'battles_count': 0,
            'win_rate': 0,
            'avg_damage': 0,
            'avg_frags': 0,
            'max_damage': 0,
            'max_damage_id': 0,
            'max_exp': 0,
            'max_exp_id': 0
        }
    ships_data = responses[1]
    pvp_data = responses[2][str(account_id)]['statistics']
    for ship_id, ship_data in pvp_data.items():
        ship_data = pvp_data[str(ship_id)]['pvp']
        if ship_data == {}:
            continue
        solo_data = ships_data[str(account_id)]['statistics'][ship_id]
        if 'pvp_solo' in solo_data and solo_data['pvp_solo'] != {}:
            solo_count = solo_data['pvp_solo']['battles_count']
        else:
            solo_count = 0
        result[ship_id]=[
                ship_data['battles_count'],
                solo_count,
                ship_data['wins'],
                ship_data['damage_dealt'],
                ship_data['frags'],
                ship_data['original_exp'],
                ship_data['survived'],
                ship_data['max_exp'],
                ship_data['max_damage_dealt']
            ]
    if pvp_count <= 0:
        return {}
    else:
        return {'overall':overall, 'data':result}

async def update_user_cahce(
    mysql_connection: Connection, 
    redis_client: Redis, 
    async_client: AsyncClient,
    account_id: int, 
    version: str
):
    redis_key = f"token:ac:{account_id}"
    result = redis_client.get(redis_key)
    if result:
        ac = json.loads(result)
    else:
        ac = None
    old_data = None
    old_pvp = None
    cache_data = await get_cache_data(mysql_connection, redis_client, async_client, account_id, ac)
    if isinstance(cache_data, str):
        return cache_data
    cursor: Cursor = mysql_connection.cursor()
    try:
        if cache_data == {}:
            sql = """
                UPDATE user_cache 
                SET 
                    pvp_count = %s, 
                    win_rate = %s, 
                    avg_damage = %s, 
                    avg_frags = %s, 
                    max_damage = %s, 
                    max_damage_id = %s, 
                    max_exp = %s, 
                    max_exp_id = %s, 
                    cache = %s 
                WHERE 
                    account_id = %s;
            """
            cursor.execute(
                sql,[
                    0,
                    0,
                    0,
                    0,
                    0,
                    None,
                    0,
                    None,
                    None,
                    account_id
                ]
            )
            return 'NoData or Hidden'
        else:
            basic_data = cache_data['overall']
            new_data = cache_data['data']
            sql = """
                SELECT 
                    pvp_count, 
                    cache 
                FROM user_cache 
                WHERE account_id = %s;
            """
            cursor.execute(sql,[account_id])
            data = cursor.fetchone()
            old_pvp = data[0]
            old_data = decompress(data[1])
            sql = """
                UPDATE user_cache 
                SET 
                    pvp_count = %s, 
                    win_rate = %s, 
                    avg_damage = %s, 
                    avg_frags = %s, 
                    max_damage = %s, 
                    max_damage_id = %s, 
                    max_exp = %s, 
                    max_exp_id = %s, 
                    cache = %s 
                WHERE 
                    account_id = %s;
            """
            cursor.execute(
                sql,[
                    basic_data['battles_count'],
                    basic_data['win_rate'],
                    basic_data['avg_damage'],
                    basic_data['avg_frags'],
                    basic_data['max_damage'],
                    basic_data['max_damage_id'],
                    basic_data['max_exp'],
                    basic_data['max_exp_id'],
                    compress(new_data),
                    account_id
                ]
            )
        mysql_connection.commit()
    except Exception as e:
        mysql_connection.rollback()
        logger.error((f"{traceback.format_exc()}"))
    finally:
        cursor.close()
    # 计算差值，统计近期数据
    if old_pvp != 0 and basic_data['battles_count'] != 0:
        add_count = basic_data['battles_count'] - old_pvp
        # 计算recent数据
        recent = {}
        for ship_id,ship_info in new_data.items():
            if ship_id not in old_data:
                recent[ship_id] = ship_info
            else:
                if ship_info[0] > old_data[ship_id][0]:
                    recent[ship_id] = [x - y for x, y in zip(ship_info, old_data[ship_id])]
        # 读取当前数据
        file_path = DATA_DIR / 'recent' / f'{REGION}_{version}.json'
        if file_path.exists():
            with open(file_path, 'r', encoding='utf-8') as f:
                current_data = json.load(f)
        else:
            current_data = {}
        # 将recent进行累加
        for ship_id, ship_data in recent.items():
            del ship_data[1] # 删除solo_count
            if ship_id not in current_data:
                current_data[ship_id] = ship_data[:6]
            else:
                current_data[ship_id] = [a + b for a, b in zip(ship_data[:6], current_data[ship_id])]
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(current_data, f, ensure_ascii=False)
        return f'Successful, {add_count} new data entries'
    else:
        return f'Successful, no new data added'