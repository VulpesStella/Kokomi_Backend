import time
import json
import random
import requests
from datetime import datetime, timezone
from celery.app.base import logger

from .exception import handle_program_exception_sync
from .middlewares import redis_client, db_pool
from .settings import REGION, VORTEX_API, CLAN_API


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

def get_insignias(data: dict):
    if data is None or data == {}:
        return None
    return f"{data['texture_id']}-{data['symbol_id']}-{data['border_color_id']}-{data['background_color_id']}-{data['background_id']}"

def get_activity_level(last_battle_time: int = 0):
    "获取activity_level"
    current_timestamp = int(time.time())
    time_since_last_battle = current_timestamp - last_battle_time
    for time_limit, return_value in TIME_DIFFERENCES:
        if time_since_last_battle <= time_limit:
            return return_value
    return 9

def fetch_data(url: str, params: dict = None):
    try:
        resp = requests.get(url, params=params, timeout=5)
        if resp.status_code == 200:
            result = resp.json()
            return result
        elif resp.status_code == 404:
            return {}
        return f'HTTP_STATUS_{resp.status_code}'
    except Exception as e:
        logger.warning(f"{type(e).__name__} {url}")
        return f'ERROR_{type(e).__name__}'

@handle_program_exception_sync
def refresh_user(account_id: int):
    now_time = now_iso()
    redis_client.incr(f'metrics:celery:{now_time[0:10]}')
    # 删除redis的key
    key = f"user_refresh:{account_id}"
    redis_client.delete(key)
    # 请求接口
    redis_key = f"token:ac:{account_id}"
    result = redis_client.get(redis_key)
    if result:
        result = json.loads(result)
        ac = result.get('ac')
    else:
        ac = None
    base_url = random.choice(VORTEX_API)
    url = f'{base_url}/api/accounts/{account_id}/'
    if ac:
        result = fetch_data(url, {'ac': ac})
    else:
        result = fetch_data(url)
    key = f"metrics:http_total:{now_time[:10]}"
    redis_client.incr(key)
    if isinstance(result, str):
        key = f"metrics:http_error:{now_time[:10]}"
        redis_client.incr(key)
        return result
    user_data = {
        'is_enabled': 1,
        'activity_level': 0,
        'is_public': 1,
        'total_battles': 0,
        'pvp_battles': 0,
        'ranked_battles': 0,
        'last_battle_at': 0,
        'username': None,
        'register_time': None,
        'insignias': None
    }
    if result == {}:
        user_data['is_enabled'] = 0
    else:
        result = result.get('data').get(str(account_id))
        if 'hidden_profile' in result:
            user_data['is_public'] = 0
            user_data['username'] = result['name']
        elif (
            result == None or
            'statistics' not in result or 
            'basic' not in result['statistics'] or 
            result['statistics']['basic']['leveling_points'] == 0
        ):
            user_data['is_enabled'] = 0
            if 'name' in result:
                user_data['username'] = result['name']
        else:
            user_data['username'] = result['name']
            user_data['register_time'] = result['statistics']['basic']['created_at']
            user_data['insignias'] = get_insignias(result['dog_tag'])
            user_data['total_battles'] = result['statistics']['basic']['leveling_points']
            user_data['last_battle_at'] = result['statistics']['basic']['last_battle_time']
            user_data['pvp_battles'] = 0 if result['statistics']['pvp'] == {} else result['statistics']['pvp']['battles_count']
            if REGION == 'ru':
                ranked_count = 0
                ranked_count += 0 if result['statistics']['rank_solo'] == {} else result['statistics']['rank_solo']['battles_count']
                ranked_count += 0 if result['statistics']['rating_solo'] == {} else result['statistics']['rating_solo']['battles_count']
                ranked_count += 0 if result['statistics']['rating_div'] == {} else result['statistics']['rating_div']['battles_count']
                user_data['ranked_battles'] = ranked_count
            else:
                user_data['ranked_battles'] = 0 if result['statistics']['rank_solo'] == {} else result['statistics']['rank_solo']['battles_count']
            user_data['activity_level'] = get_activity_level(user_data['last_battle_at'])
    conn = db_pool.connection()
    conn.begin()
    try:
        cursor = conn.cursor()
        if user_data['username']:
            if user_data['register_time'] == None:
                sql = """
                    UPDATE user_base 
                    SET 
                        username = %s, 
                        touch_at = CURRENT_TIMESTAMP 
                    WHERE account_id = %s;
                """
                cursor.execute(
                    sql,[user_data['username'], account_id]
                )
            else:
                sql = """
                    UPDATE user_base 
                    SET 
                        username = %s, 
                        register_time = FROM_UNIXTIME(%s), 
                        insignias = %s, 
                        touch_at = CURRENT_TIMESTAMP 
                    WHERE account_id = %s;
                """
                cursor.execute(
                    sql,[user_data['username'], user_data['register_time'], user_data['insignias'], account_id]
                )
        if user_data['is_enabled'] == 0:
            sql = """
                UPDATE user_stats 
                SET 
                    is_enabled = %s, 
                    touch_at = CURRENT_TIMESTAMP 
                WHERE account_id = %s;
            """
            cursor.execute(
                sql,
                [
                    user_data['is_enabled'], account_id
                ]
            )
        elif user_data['total_battles'] != 0:
            if user_data['total_battles'] >= 1000000:
                total_battles = user_data['total_battles'] - 1000000
            else:
                total_battles = user_data['total_battles']
            sql = """
                UPDATE user_stats 
                SET 
                    is_enabled = 1, 
                    activity_level = %s, 
                    is_public = 1, 
                    total_battles = %s, 
                    pvp_battles = %s, 
                    ranked_battles = %s, 
                    last_battle_at = FROM_UNIXTIME(%s), 
                    touch_at = CURRENT_TIMESTAMP 
                WHERE account_id = %s;
            """
            cursor.execute(
                sql,
                [
                    user_data['activity_level'], total_battles, user_data['pvp_battles'], user_data['ranked_battles'], 
                    user_data['last_battle_at'] if user_data['last_battle_at'] != 0 else None, account_id
                ]
            )
        else:
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
            cursor.execute(
                sql,
                [
                    user_data['is_enabled'], user_data['activity_level'], user_data['is_public'], account_id
                ]
            )
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()
    return f'OK'


@handle_program_exception_sync
def refresh_clan(clan_id: int):
    # metrics
    now_time = now_iso()
    redis_client.incr(f'metrics:celery:{now_time[0:10]}')
    # 先删除redis的key
    key = f"clan_refresh:{clan_id}"
    redis_client.delete(key)
    url = f'{CLAN_API}/api/members/{clan_id}/'
    result = fetch_data(url)
    key = f"metrics:http_total:{now_time[:10]}"
    redis_client.incr(key)
    if isinstance(result, str):
        key = f"metrics:http_error:{now_time[:10]}"
        redis_client.incr(key)
        return result
    users = {}
    for user_info in result.get('items'):
        users[user_info['id']] = user_info['name']
    # 当前工会内玩家id列表
    user_ids = list(users.keys())
    conn = db_pool.connection()
    conn.begin()
    try:
        cursor = conn.cursor()
        sql = """
            SELECT 
                member_ids, 
                UNIX_TIMESTAMP(touch_at) 
            FROM clan_users 
            WHERE clan_id = %s;
        """
        cursor.execute(sql, [clan_id])
        data = cursor.fetchone()
        if len(user_ids) == 0:
            sql = """
                UPDATE clan_users 
                SET 
                    is_enabled = 0, 
                    member_count = 0, 
                    member_ids = NULL, 
                    touch_at = CURRENT_TIMESTAMP 
                WHERE clan_id = %s;
            """
            cursor.execute(sql, [clan_id])
        else:
            placeholders = ",".join(["%s"] * len(user_ids))
            sql = f"""
                SELECT account_id 
                FROM user_clan 
                WHERE account_id IN ({placeholders});
            """
            cursor.execute(sql, user_ids)
            existing_ids = {row[0] for row in cursor.fetchall()}
            missing_ids = set(user_ids) - existing_ids
            # 写入数据库中不存在的用户
            for account_id in missing_ids:
                sql = """
                    INSERT INTO user_base (
                        account_id, 
                        username,
                        touch_at 
                    ) VALUES (
                        %s, %s, CURRENT_TIMESTAMP
                    );
                """
                cursor.execute(sql, [account_id, users[account_id]])
                sql = """
                    INSERT INTO user_stats (
                        account_id
                    ) VALUES (
                        %s
                    );
                """
                cursor.execute(sql, [account_id])
                sql = """
                    INSERT INTO user_clan (
                        account_id
                    ) VALUES (
                        %s
                    );
                """
                cursor.execute(sql, [account_id])
                sql = """
                    INSERT INTO user_cache (
                        account_id
                    ) VALUES (
                        %s
                    );
                """
                cursor.execute(sql, [account_id])
            # 删除已不再工会内的用户
            sql = """
                SELECT 
                    account_id 
                FROM user_clan 
                WHERE clan_id = %s;
            """
            cursor.execute(sql,[clan_id])
            for existing_clan_user in cursor.fetchall():
                if existing_clan_user[0] not in user_ids:
                    sql = """
                        UPDATE user_clan 
                        SET 
                            clan_id = NULL, 
                            touch_at = CURRENT_TIMESTAMP 
                        WHERE account_id = %s;
                    """
                    cursor.execute(sql,[existing_clan_user[0]])
            # 刷新工会内所有用户的记录
            sql = f"""
                UPDATE user_clan 
                SET 
                    clan_id = %s, 
                    touch_at = CURRENT_TIMESTAMP 
                WHERE account_id IN ({placeholders});
            """
            cursor.execute(sql, [clan_id] + user_ids)
            # 更新clan_users表
            sql = """
                UPDATE clan_users 
                SET 
                    is_enabled = 1, 
                    member_count = %s, 
                    member_ids = %s, 
                    touch_at = CURRENT_TIMESTAMP 
                WHERE clan_id = %s;
            """
            cursor.execute(sql, [len(user_ids), json.dumps(user_ids), clan_id])
            # 更新工会所在用户数据
            if data[1]:
                old_data = json.loads(data[0] if data[0] else '[]')
                added_ids = list(set(user_ids) - set(old_data))
                removed_ids = list(set(old_data) - set(user_ids))
                for added_id in added_ids:
                    sql = """
                        INSERT INTO clan_action (
                            clan_id, 
                            account_id, 
                            action_type
                        ) VALUES (
                            %s, %s, %s
                        );
                    """
                    cursor.execute(sql, [clan_id, added_id, 1])
                for removed_id in removed_ids:
                    sql = """
                        INSERT INTO clan_action (
                            clan_id, 
                            account_id, 
                            action_type
                        ) VALUES (
                            %s, %s, %s
                        );
                    """
                    cursor.execute(sql, [clan_id, removed_id, 2])
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()
        conn.close()
    return 'OK'