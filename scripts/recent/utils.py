import time
import json
import asyncio
import sqlite3
import traceback
from pathlib import Path
from httpx import AsyncClient
from redis import Redis
from pymysql import Connection
from pymysql.cursors import Cursor
from datetime import datetime, timezone

from logger import logger
from settings import BATCH_SIZE, SQLITE_PATH, REGION, TIMEZOEN, WG_API_TOKEN, LESTA_API_TOKEN, OFFICIAL_API


CreateSQL = """
CREATE TABLE users (
    date int PRIMARY KEY,
    is_public bool, 
    leveling_points int, 
    karma int, 
    pvp_count int,
    win_rate float, 
    avg_damage float, 
    avg_frags float, 
    table_name str
);
CREATE TABLE cache (
    date int PRIMARY KEY,
    total_battles int,
    cache str
);
CREATE TABLE ships (
    ship_id int,
    date int,
    cache str
);
CREATE UNIQUE INDEX idx_ship ON ships(ship_id, date);
"""
SERVER_RESET_OFFSET = 5 * 3600
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

def formtimestamp(timedelta: int = 0):
    # 当地时间凌晨5点更新
    timestamp = int(time.time()) + TIMEZOEN*3600 - SERVER_RESET_OFFSET - timedelta*24*60*60
    return datetime.fromtimestamp(timestamp, timezone.utc).strftime("%Y%m%d")

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

def db_stats():
    db_files = list(SQLITE_PATH.rglob("*.db"))
    total_size = 0
    for file in db_files:
        if file.is_file():
            total_size += file.stat().st_size
    result = {
        "db_file_count": len(db_files),
        "total_size_mb": round(total_size / (1024 * 1024), 2),
    }
    output_file = SQLITE_PATH / "db_stats.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=4)
    return result

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

async def post_data(async_client: AsyncClient, url: str, body):
    try:
        res = await async_client.post(url, data=body, timeout=5)
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
 
def init_db_if_needed(db_path: Path) -> bool:
    """
    检查 sqlite3 数据库是否存在且包含用户表，
    若不存在或为空数据库，则创建表。
    """
    need_init = False
    # 文件是否存在
    if not db_path.exists():
        need_init = True
    try:
        # 连接数据库（不存在会自动创建）
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            # 检查是否存在用户表
            cursor.execute("""
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                AND name NOT LIKE 'sqlite_%'
                LIMIT 1;
            """)
            has_table = cursor.fetchone() is not None
            if not has_table:
                need_init = True
            # 需要初始化 → 创建表
            if need_init:
                cursor.executescript(CreateSQL)
                conn.commit()
            return True
    except Exception:
        logger.error((f"{traceback.format_exc()}"))
        return False

def del_recent(conn: Connection, account_id: int):
    conn.begin()
    cursor: Cursor = conn.cursor()
    try:
        sql = """
            UPDATE recent 
            SET
                enable_recent = 0, 
                enable_daily = 0 
            FROM recent 
            WHERE account_id = %s;
        """
        cursor.execute(sql, [account_id])
        conn.commit()
    except Exception:
        conn.rollback()
        logger.error((f"{traceback.format_exc()}"))
    finally:
        cursor.close()

def del_recents(conn: Connection, account_id: int):
    conn.begin()
    cursor: Cursor = conn.cursor()
    try:
        sql = """
            UPDATE recent 
            SET
                enable_daily = 0 
            FROM recent 
            WHERE account_id = %s;
        """
        cursor.execute(sql, [account_id])
        sql = """
            SELECT 
                id 
            FROM user_base 
            WHERE account_id = %s;
        """
        cursor.execute(sql,[account_id])
        data = cursor.fetchone()
        game_id = data[0]
        sql = """
            DELETE FROM recent_pro 
            WHERE game_id = %s;
        """
        cursor.execute(sql, [game_id])
        conn.commit()
    except Exception:
        conn.rollback()
        logger.error((f"{traceback.format_exc()}"))
    finally:
        cursor.close()

def get_private_update_ids(mysql_connection: Connection, redis_client: Redis) -> list:
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
    mysql_connection.begin()
    cursor: Cursor = mysql_connection.cursor()
    try:
        for user_id in result.keys():
            user_data = json.loads(result[user_id])
            account_id = int(user_id.replace('token:auth:', ''))
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
                update_list.append([account_id, user_data['auth']])
            elif data[0] != formtimestamp():
                update_list.append([account_id, user_data['auth']])
        mysql_connection.commit()
    except Exception:
        mysql_connection.rollback()
        logger.error((f"{traceback.format_exc()}"))
    finally:
        cursor.close()
    return update_list
   
async def update_user_private(
    conn: Connection, 
    redis_client: Redis,
    async_client: AsyncClient,
    account_id: int,
    auth_value: str
):
    if REGION == 'ru':
        token = LESTA_API_TOKEN
    else:
        token = WG_API_TOKEN
    api_url = OFFICIAL_API
    urls = [
        f'{api_url}/wows/account/info/?application_id={token}&account_id={account_id}&access_token={auth_value}&extra=private.port',
        f'{api_url}/wows/account/achievements/?application_id={token}&account_id={account_id}'
    ]
    tasks = [fetch_data(async_client, url) for url in urls]
    responses = await asyncio.gather(*tasks)
    error = verify_responses(redis_client, responses)
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
        'update_date': formtimestamp(),
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

def get_token_update_ids(mysql_connection: Connection, redis_client: Redis):
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
    cursor: Cursor = mysql_connection.cursor()
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
    except Exception:
        logger.error((f"{traceback.format_exc()}"))
    finally:
        cursor.close()
    return update_list

async def update_user_token(
    redis_client: Redis,
    async_client: AsyncClient,
    account_id: int,
    auth_value: str
):
    if REGION == 'ru':
        token = LESTA_API_TOKEN
    else:
        token = WG_API_TOKEN
    api_url = OFFICIAL_API
    url = f'{api_url}/wot/auth/prolongate/'
    responses = [
        await post_data(async_client, url, {'application_id': token,'access_token': auth_value,'expires_at':int(time.time())+14*24*60*60-30})
    ]
    error = verify_responses(redis_client, responses)
    if error != None:
        return error
    response = responses[0]
    if response == {}:
        redis_client.delete(f'token:auth:{account_id}')
        return 'InvalidToken'
    redis_client.set(f'token:auth:{account_id}',json.dumps(response['data']['access_token']),response['data']['expires_at']-int(time.time())-30)
    return 'Success'

def get_recent_update_ids(mysql_connection: Connection):
    # 从数据库中批量读取并判断那些用户需要更新
    update_list = []
    temp_ids = {}
    cursor: Cursor = mysql_connection.cursor()
    try:
        sql = """
            SELECT 
                MAX(id) 
            FROM recent;
        """
        cursor.execute(sql)
        data = cursor.fetchone()
        max_id = data[0]
        logger.info(f'Max id in table recent: {max_id}')
        for offset in range(0, max_id, BATCH_SIZE):
            sql = """
                SELECT 
                    r.account_id,  
                    r.enable_recent, 
                    r.enable_daily, 
                    s.total_battles 
                FROM recent AS r 
                LEFT JOIN user_stats AS s 
                    ON r.account_id = s.account_id 
                WHERE r.id BETWEEN %s AND %s;
            """
            cursor.execute(sql, [offset+1, offset+BATCH_SIZE])
            rows = cursor.fetchall()
            for row in rows:
                account_id = row[0]
                if row[1] == 1:
                    temp_ids[account_id] = [row[2], row[3]]
    except Exception:
        logger.error((f"{traceback.format_exc()}"))
    finally:
        cursor.close()
    date_1 = formtimestamp(0)
    date_2 = formtimestamp(1)
    for account_id, account_data in temp_ids.items():
        db_path = SQLITE_PATH / f'{account_id}.db'
        if init_db_if_needed(db_path) is False:
            continue
        try:
            # 连接数据库（不存在会自动创建）
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            # 检查是否存在用户表
            cursor.execute("""
                SELECT 
                    is_public, 
                    leveling_points, 
                    karma, 
                    win_rate, 
                    avg_damage, 
                    avg_frags, 
                    table_name 
                FROM users 
                WHERE date = ?;
            """, [date_2])
            date2_data = cursor.fetchone()
            if date2_data is None:
                update_list.append([account_id, account_data[0]])
                continue
            cursor.execute("""
                SELECT 
                    is_public, 
                    leveling_points, 
                    karma, 
                    pvp_count,
                    win_rate, 
                    avg_damage, 
                    avg_frags, 
                    table_name
                FROM users
                WHERE date = ?;
            """, [date_1])
            date1_data = cursor.fetchone()
            if date1_data is None:
                # 今日日期下没有数据条目，先复制昨日数据条目
                cursor.execute("""
                    INSERT INTO users (
                        date,is_public,leveling_points,karma,
                        pvp_count,win_rate,avg_damage,
                        avg_frags,table_name
                    ) VALUES (
                        ?,?,?,?,?,?,?,?
                    );
                """,[date_1,date2_data[0],date2_data[1],date2_data[2],date2_data[3],date2_data[4],date2_data[5],date2_data[6],date2_data[7]])
                conn.commit()
                continue
            if date1_data[1] != account_data[1]:
                update_list.append([account_id, account_data[0]])
                continue
        except Exception:
            logger.error((f"{traceback.format_exc()}"))
        finally:
            cursor.close()
            conn.close()
    return update_list

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