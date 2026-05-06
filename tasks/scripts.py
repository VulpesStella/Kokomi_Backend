import os
import random
import requests
from datetime import datetime, timezone

from .exception import handle_program_exception_sync
from .middlewares import redis_client, db_pool
from .syncer import UserStatsSyncer, ClanUsersSyncer
from .settings import (
    REGION, 
    VORTEX_API, 
    CLAN_API, 
    USER_INIT_TABLE_LIST
)


os.environ['NO_PROXY'] = '127.0.0.1,localhost'

def now_utc_date() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")[0:10]

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
    ac = redis_client.get(redis_key)
    base_url = random.choice(VORTEX_API)
    url = f'{base_url}/api/accounts/{account_id}/' + (f'?ac={ac}' if ac else '')
    response = fetch_data(url)
    key = f"metrics:http_total:{now_date}"
    redis_client.incr(key)
    if isinstance(response, str):
        key = f"metrics:http_error:{now_date}"
        redis_client.incr(key)
        return response  
    # 处理异常情况
    if response.get('status') != 'ok':
        return 'GameAPI Error'
    response = response.get('data', {})
    conn = db_pool.connection()
    result = UserStatsSyncer.refresh(conn, account_id, response)
    return result if isinstance(result, str) else 'Success'

@handle_program_exception_sync
def refresh_clan(clan_id: int):
    # metrics
    now_date = now_utc_date()
    redis_client.incr(f'metrics:celery:{now_date}')
    # 先删除redis的key
    key = f"refresh_lock:clan:{clan_id}"
    redis_client.delete(key)
    url = f'{CLAN_API}/api/members/{clan_id}/'
    response = fetch_data(url)
    key = f"metrics:http_total:{now_date}"
    redis_client.incr(key)
    if isinstance(response, str):
        key = f"metrics:http_error:{now_date}"
        redis_client.incr(key)
        return response
    # 处理异常情况
    if response.get('status') != 'ok':
        return 'GameAPI Error'
    conn = db_pool.connection()
    result = ClanUsersSyncer.refresh(conn, clan_id, response)
    return result if isinstance(result, str) else 'Success'
    # users = {}
    # for user_info in result.get('items'):
    #     users[user_info['id']] = user_info['name']
    # # 当前工会内玩家id列表
    # user_ids = list(users.keys())
    # conn = db_pool.connection()
    # try:
    #     cursor = conn.cursor()
    #     sql = """
    #         SELECT 
    #             member_ids, 
    #             UNIX_TIMESTAMP(updated_at) 
    #         FROM T_clan_users 
    #         WHERE clan_id = %s;
    #     """
    #     cursor.execute(sql, [clan_id])
    #     data = cursor.fetchone()
    #     if len(user_ids) == 0:
    #         sql = """
    #             UPDATE T_clan_users 
    #             SET 
    #                 is_enabled = 0, 
    #                 member_count = 0, 
    #                 member_ids = NULL, 
    #                 updated_at = CURRENT_TIMESTAMP 
    #             WHERE clan_id = %s;
    #         """
    #         cursor.execute(sql, [clan_id])
    #         sql = """
    #             SELECT 
    #                 account_id 
    #             FROM T_user_clan 
    #             WHERE clan_id = %s;
    #         """
    #         cursor.execute(sql,[clan_id])
    #         # 删除已不再工会内的用户
    #         for existing_clan_user in cursor.fetchall():
    #             sql = """
    #                 UPDATE T_user_clan 
    #                 SET 
    #                     clan_id = NULL, 
    #                     updated_at = CURRENT_TIMESTAMP 
    #                 WHERE account_id = %s;
    #             """
    #             cursor.execute(sql,[existing_clan_user[0]])
    #             sql = """
    #                 INSERT INTO T_clan_action (
    #                     clan_id, 
    #                     account_id, 
    #                     action_type
    #                 ) VALUES (
    #                     %s, %s, %s
    #                 );
    #             """
    #             cursor.execute(sql, [clan_id, existing_clan_user[0], 2])
    #     else:
    #         placeholders = ",".join(["%s"] * len(user_ids))
    #         sql = f"""
    #             SELECT account_id 
    #             FROM T_user_clan 
    #             WHERE account_id IN ({placeholders});
    #         """
    #         cursor.execute(sql, user_ids)
    #         existing_ids = {row[0] for row in cursor.fetchall()}
    #         missing_ids = set(user_ids) - existing_ids
    #         # 写入数据库中不存在的用户
    #         for account_id in missing_ids:
    #             sql = """
    #                 INSERT INTO T_user_base (
    #                     account_id, 
    #                     username,
    #                     updated_at 
    #                 ) VALUES (
    #                     %s, %s, CURRENT_TIMESTAMP
    #                 );
    #             """
    #             cursor.execute(sql, [account_id, users[account_id]])
    #             for table_name in USER_INIT_TABLE_LIST:
    #                 sql = f"""
    #                     INSERT INTO {table_name} (
    #                         account_id
    #                     ) VALUES (
    #                         %s
    #                     );
    #                 """
    #                 cursor.execute(sql, [account_id])
    #             sql = """
    #                 UPDATE T_user_base 
    #                 SET 
    #                     table_count = %s 
    #                 WHERE account_id = %s;
    #             """
    #             cursor.execute(sql, [len(USER_INIT_TABLE_LIST),account_id])
    #         # 删除已不再工会内的用户
    #         sql = """
    #             SELECT 
    #                 account_id 
    #             FROM T_user_clan 
    #             WHERE clan_id = %s;
    #         """
    #         cursor.execute(sql,[clan_id])
    #         for existing_clan_user in cursor.fetchall():
    #             if existing_clan_user[0] not in user_ids:
    #                 sql = """
    #                     UPDATE T_user_clan 
    #                     SET 
    #                         clan_id = NULL, 
    #                         updated_at = CURRENT_TIMESTAMP 
    #                     WHERE account_id = %s;
    #                 """
    #                 cursor.execute(sql,[existing_clan_user[0]])
    #         # 刷新工会内所有用户的记录
    #         sql = f"""
    #             UPDATE T_user_clan 
    #             SET 
    #                 clan_id = %s, 
    #                 updated_at = CURRENT_TIMESTAMP 
    #             WHERE account_id IN ({placeholders});
    #         """
    #         cursor.execute(sql, [clan_id] + user_ids)
    #         # 更新clan_users表
    #         sql = """
    #             UPDATE T_clan_users 
    #             SET 
    #                 is_enabled = 1, 
    #                 member_count = %s, 
    #                 member_ids = %s, 
    #                 updated_at = CURRENT_TIMESTAMP 
    #             WHERE clan_id = %s;
    #         """
    #         cursor.execute(sql, [len(user_ids), json.dumps(user_ids), clan_id])
    #         # 更新工会所在用户数据
    #         if data and data[1]:
    #             old_data = json.loads(data[0] if data[0] else '[]')
    #             added_ids = list(set(user_ids) - set(old_data))
    #             removed_ids = list(set(old_data) - set(user_ids))
    #             for added_id in added_ids:
    #                 sql = """
    #                     INSERT INTO T_clan_action (
    #                         clan_id, 
    #                         account_id, 
    #                         action_type
    #                     ) VALUES (
    #                         %s, %s, %s
    #                     );
    #                 """
    #                 cursor.execute(sql, [clan_id, added_id, 1])
    #             for removed_id in removed_ids:
    #                 sql = """
    #                     INSERT INTO T_clan_action (
    #                         clan_id, 
    #                         account_id, 
    #                         action_type
    #                     ) VALUES (
    #                         %s, %s, %s
    #                     );
    #                 """
    #                 cursor.execute(sql, [clan_id, removed_id, 2])
    #     return_msg = 'Success'
    #     conn.commit()
    # except Exception as e:
    #     conn.rollback()
    #     raise e
    # finally:
    #     cursor.close()
    #     conn.close()
    # return return_msg