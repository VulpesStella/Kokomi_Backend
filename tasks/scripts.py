import os
import json
import random
import requests
from dbutils.pooled_db import PooledDedicatedDBConnection
from datetime import datetime, timezone

from .exception import handle_program_exception_sync
from .middlewares import redis_client, db_pool
from .settings import (
    REGION, 
    VORTEX_API, 
    CLAN_API, 
    USER_INIT_TABLE_LIST
)


os.environ['NO_PROXY'] = '127.0.0.1,localhost'

def now_utc_date() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")[0:10]

def get_insignias(data: dict):
    if not data:
        return None
    keys = [
        "texture_id",
        "symbol_id",
        "border_color_id",
        "background_color_id",
        "background_id"
    ]
    if any(k not in data for k in keys):
        return None
    return "-".join(str(data[k]) for k in keys)

def fetch_data(url: str, params: dict = None):
    try:
        resp = requests.get(url, params=params, timeout=3)
        if resp.status_code == 200:
            result = resp.json()
            return result
        elif resp.status_code == 404:
            return {}
        return f'HTTP_STATUS_{resp.status_code}'
    except Exception as e:
        print(f"{type(e).__name__} {url}")
        return f'ERROR_{type(e).__name__}'

@handle_program_exception_sync
def refresh_user(account_id: int):
    now_date = now_utc_date()
    redis_client.incr(f'metrics:celery:{now_date}')
    # 删除redis的key
    key = f"refresh_lock:user:{account_id}"
    redis_client.delete(key)
    # 请求接口
    redis_key = f"token:ac:{account_id}"
    result = redis_client.get(redis_key)
    if result:
        ac = json.loads(result)
    else:
        ac = None
    base_url = random.choice(VORTEX_API)
    url = f'{base_url}/api/accounts/{account_id}/'
    if ac:
        result = fetch_data(url, {'ac': ac})
    else:
        result = fetch_data(url)
    key = f"metrics:http_total:{now_date}"
    redis_client.incr(key)
    if isinstance(result, str):
        key = f"metrics:http_error:{now_date}"
        redis_client.incr(key)
        return result
    # 处理异常情况
    if result.get('status') != 'ok':
        return 'GameAPI Error'
    result: dict = result['data']
    user_data = {
        'is_enabled': 1,
        'is_public': 1,
        'total_battles': 0,
        'pve_battles': 0,
        'pvp_battles': 0,
        'ranked_battles': 0,
        'rating_battles': 0,
        'karma': 0,
        'last_battle_at': 0,
        'username': None,
        'register_time': None,
        'insignias': None
    }
    if result:
        result = result.get(str(account_id))
    if 'hidden_profile' in result:
        user_data['is_public'] = 0
        user_data['username'] = result['name']
    elif 'statistics' not in result:
        user_data['is_enabled'] = 0
    elif 'basic' not in result['statistics']:
        user_data['username'] = result['name']
        user_data['register_time'] = int(result['created_at'])
    else:
        leveling_points = result['statistics']['basic']['leveling_points']
        if leveling_points >= 1000000:
            leveling_points = leveling_points - 1000000
        user_data['username'] = result['name']
        user_data['register_time'] = int(result['created_at'])
        user_data['insignias'] = get_insignias(result['dog_tag'])
        user_data['total_battles'] = leveling_points
        user_data['karma'] = result['statistics']['basic']['karma']
        user_data['last_battle_at'] = result['statistics']['basic']['last_battle_time']
        user_data['pve_battles'] = 0 if result['statistics']['pve'] == {} else result['statistics']['pve']['battles_count']
        user_data['pvp_battles'] = 0 if result['statistics']['pvp'] == {} else result['statistics']['pvp']['battles_count']
        user_data['ranked_battles'] = 0 if result['statistics']['rank_solo'] == {} else result['statistics']['rank_solo']['battles_count']
        if REGION == 'ru':
            rating_count = 0
            rating_count += 0 if result['statistics']['rating_solo'] == {} else result['statistics']['rating_solo']['battles_count']
            rating_count += 0 if result['statistics']['rating_div'] == {} else result['statistics']['rating_div']['battles_count']
            user_data['rating_battles'] = rating_count
    conn = db_pool.connection()
    conn.begin()
    try:
        cursor = conn.cursor()
        sql = """
            SELECT 
                username, 
                UNIX_TIMESTAMP(updated_at) 
            FROM T_user_base 
            WHERE account_id = %s;
        """
        cursor.execute(sql, [account_id])
        data = cursor.fetchone()
        # 过滤并防止脏数据污染
        if data:
            # 单独处理用户名称，部分账号有名称但无数据
            if user_data['username']:
                if user_data['register_time'] == None:
                    # 有名称但无注册时间 -> 隐藏战绩用户
                    sql = """
                        UPDATE T_user_base 
                        SET 
                            username = %s, 
                            updated_at = CURRENT_TIMESTAMP 
                        WHERE account_id = %s;
                    """
                    cursor.execute(
                        sql,[user_data['username'], account_id]
                    )
                else:
                    # 有名称和注册时间 -> 正常用户
                    sql = """
                        UPDATE T_user_base 
                        SET 
                            username = %s, 
                            register_time = FROM_UNIXTIME(%s), 
                            insignias = %s, 
                            updated_at = CURRENT_TIMESTAMP 
                        WHERE account_id = %s;
                    """
                    cursor.execute(
                        sql,[user_data['username'], user_data['register_time'], user_data['insignias'], account_id]
                    )
                # 如果用户名称和刷新前不一致，则判定用户存在修改昵称行为
                if data[1] and data[0] != user_data['username']:
                    sql = """
                        INSERT INTO T_user_action (
                            account_id, 
                            username
                        ) VALUES (
                            %s, %s
                        );
                    """
                    cursor.execute(
                        sql,[account_id, data[0]]
                    )
            if user_data['is_enabled'] == 0:
                # 账号不存在（404）
                sql = """
                    UPDATE T_user_stats 
                    SET 
                        is_enabled = 0, 
                        activity_level = 0, 
                        updated_at = CURRENT_TIMESTAMP 
                    WHERE account_id = %s;
                """
                cursor.execute(sql, [account_id])
            elif user_data['is_public'] == 0:
                # 账号隐藏战绩
                sql = """
                    UPDATE T_user_stats 
                    SET 
                        is_enabled = 1, 
                        is_public = 0, 
                        activity_level = 0, 
                        updated_at = CURRENT_TIMESTAMP 
                    WHERE account_id = %s;
                """
                cursor.execute(sql, [account_id])
            else:
                # 正常账号
                last_battle_time = user_data['last_battle_at'] if user_data['last_battle_at'] != 0 else None
                sql = """
                    UPDATE T_user_stats 
                    SET 
                        is_enabled = 1,  
                        is_public = 1, 
                        activity_level = F_user_activity_level(%s),
                        total_battles = %s, 
                        pve_battles = %s, 
                        pvp_battles = %s, 
                        ranked_battles = %s, 
                        rating_battles = %s, 
                        karma = %s, 
                        last_battle_at = FROM_UNIXTIME(%s), 
                        updated_at = CURRENT_TIMESTAMP 
                    WHERE account_id = %s;
                """
                cursor.execute(
                    sql,
                    [
                        last_battle_time, 
                        user_data['total_battles'], 
                        user_data['pve_battles'], 
                        user_data['pvp_battles'], 
                        user_data['ranked_battles'], 
                        user_data['rating_battles'], 
                        user_data['karma'], 
                        last_battle_time, 
                        account_id
                    ]
                )
            return_msg = 'Success'
        else:
            return_msg = 'Validation Error'
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()
    return return_msg

@handle_program_exception_sync
def refresh_clan(clan_id: int):
    # metrics
    now_date = now_utc_date()
    redis_client.incr(f'metrics:celery:{now_date}')
    # 先删除redis的key
    key = f"refresh_lock:clan:{clan_id}"
    redis_client.delete(key)
    url = f'{CLAN_API}/api/members/{clan_id}/'
    result = fetch_data(url)
    key = f"metrics:http_total:{now_date}"
    redis_client.incr(key)
    if isinstance(result, str):
        key = f"metrics:http_error:{now_date}"
        redis_client.incr(key)
        return result
    # 处理异常情况
    if result.get('status') != 'ok':
        return 'GameAPI Error'
    users = {}
    for user_info in result.get('items'):
        users[user_info['id']] = user_info['name']
    # 当前工会内玩家id列表
    user_ids = list(users.keys())
    if len(user_ids) > 50:
        return 'Validation Error'
    conn = db_pool.connection()
    conn.begin()
    try:
        cursor = conn.cursor()
        sql = """
            SELECT 
                member_ids, 
                UNIX_TIMESTAMP(updated_at) 
            FROM T_clan_users 
            WHERE clan_id = %s;
        """
        cursor.execute(sql, [clan_id])
        data = cursor.fetchone()
        if len(user_ids) == 0:
            sql = """
                UPDATE T_clan_users 
                SET 
                    is_enabled = 0, 
                    member_count = 0, 
                    member_ids = NULL, 
                    updated_at = CURRENT_TIMESTAMP 
                WHERE clan_id = %s;
            """
            cursor.execute(sql, [clan_id])
            sql = """
                SELECT 
                    account_id 
                FROM T_user_clan 
                WHERE clan_id = %s;
            """
            cursor.execute(sql,[clan_id])
            # 删除已不再工会内的用户
            for existing_clan_user in cursor.fetchall():
                sql = """
                    UPDATE T_user_clan 
                    SET 
                        clan_id = NULL, 
                        updated_at = CURRENT_TIMESTAMP 
                    WHERE account_id = %s;
                """
                cursor.execute(sql,[existing_clan_user[0]])
                sql = """
                    INSERT INTO T_clan_action (
                        clan_id, 
                        account_id, 
                        action_type
                    ) VALUES (
                        %s, %s, %s
                    );
                """
                cursor.execute(sql, [clan_id, existing_clan_user[0], 2])
        else:
            placeholders = ",".join(["%s"] * len(user_ids))
            sql = f"""
                SELECT account_id 
                FROM T_user_clan 
                WHERE account_id IN ({placeholders});
            """
            cursor.execute(sql, user_ids)
            existing_ids = {row[0] for row in cursor.fetchall()}
            missing_ids = set(user_ids) - existing_ids
            # 写入数据库中不存在的用户
            for account_id in missing_ids:
                sql = """
                    INSERT INTO T_user_base (
                        account_id, 
                        username,
                        updated_at 
                    ) VALUES (
                        %s, %s, CURRENT_TIMESTAMP
                    );
                """
                cursor.execute(sql, [account_id, users[account_id]])
                for table_name in USER_INIT_TABLE_LIST:
                    sql = f"""
                        INSERT INTO {table_name} (
                            account_id
                        ) VALUES (
                            %s
                        );
                    """
                    cursor.execute(sql, [account_id])
                sql = """
                    UPDATE T_user_base 
                    SET 
                        table_count = %s 
                    WHERE account_id = %s;
                """
                cursor.execute(sql, [len(USER_INIT_TABLE_LIST),account_id])
            # 删除已不再工会内的用户
            sql = """
                SELECT 
                    account_id 
                FROM T_user_clan 
                WHERE clan_id = %s;
            """
            cursor.execute(sql,[clan_id])
            for existing_clan_user in cursor.fetchall():
                if existing_clan_user[0] not in user_ids:
                    sql = """
                        UPDATE T_user_clan 
                        SET 
                            clan_id = NULL, 
                            updated_at = CURRENT_TIMESTAMP 
                        WHERE account_id = %s;
                    """
                    cursor.execute(sql,[existing_clan_user[0]])
            # 刷新工会内所有用户的记录
            sql = f"""
                UPDATE T_user_clan 
                SET 
                    clan_id = %s, 
                    updated_at = CURRENT_TIMESTAMP 
                WHERE account_id IN ({placeholders});
            """
            cursor.execute(sql, [clan_id] + user_ids)
            # 更新clan_users表
            sql = """
                UPDATE T_clan_users 
                SET 
                    is_enabled = 1, 
                    member_count = %s, 
                    member_ids = %s, 
                    updated_at = CURRENT_TIMESTAMP 
                WHERE clan_id = %s;
            """
            cursor.execute(sql, [len(user_ids), json.dumps(user_ids), clan_id])
            # 更新工会所在用户数据
            if data and data[1]:
                old_data = json.loads(data[0] if data[0] else '[]')
                added_ids = list(set(user_ids) - set(old_data))
                removed_ids = list(set(old_data) - set(user_ids))
                for added_id in added_ids:
                    sql = """
                        INSERT INTO T_clan_action (
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
                        INSERT INTO T_clan_action (
                            clan_id, 
                            account_id, 
                            action_type
                        ) VALUES (
                            %s, %s, %s
                        );
                    """
                    cursor.execute(sql, [clan_id, removed_id, 2])
        return_msg = 'Success'
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()
        conn.close()
    return return_msg