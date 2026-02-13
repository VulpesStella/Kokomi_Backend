import time
import json
import requests
import traceback
from redis import Redis
from pymysql import Connection
from pymysql.cursors import Cursor
from datetime import datetime

from logger import logger
from settings import BATCH_SIZE


CLAN_API_URL_LIST = {
    1: 'https://clans.worldofwarships.asia',
    2: 'https://clans.worldofwarships.eu',
    3: 'https://clans.worldofwarships.com',
    4: 'https://clans.korabli.su',
    5: 'https://clans.wowsgame.cn'
}

def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")

def get_region(region_id: int):
    region_dict = {1: 'asia',2: 'eu',3: 'na',4: 'ru',5: 'cn'}
    return region_dict[region_id]

def fetch_data(url):
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            logger.debug(f'200 {url}')
            result = resp.json()
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

def get_clan_users(redis_client: Redis, region_id: int, clan_id: int):
    base_url = CLAN_API_URL_LIST.get(region_id)
    url = f'{base_url}/api/members/{clan_id}/'
    result = fetch_data(url)
    error = verify_responses(get_region(region_id), redis_client, [result])
    if error != None:
        return error
    return result

def get_update_ids(conn: Connection):
    # 从数据库中批量读取并判断哪些需要更新
    update_list = []
    cursor: Cursor = conn.cursor()
    try:
        sql = """
            SELECT 
                MAX(id) 
            FROM clan_users;
        """
        cursor.execute(sql)
        data = cursor.fetchone()
        max_id = data[0] if data else 0
        logger.info(f'Max ID: {max_id}')
        now_ts = int(time.time())
        UPDATE_INTERVAL = 6*60*60
        for offset in range(0, max_id, BATCH_SIZE):
            sql = """
                SELECT 
                    id, 
                    is_enabled, 
                    UNIX_TIMESTAMP(touch_at) AS touch_at 
                FROM clan_users 
                WHERE id BETWEEN %s AND %s;
            """
            cursor.execute(sql, [offset+1, offset+BATCH_SIZE])
            rows = cursor.fetchall()
            for row in rows:
                if row[2] and row[1] == 0:
                    continue
                if row[2] and (now_ts - row[2] < UPDATE_INTERVAL):
                    continue
                update_list.append(row[0])
    except Exception:
        logger.error((f"{traceback.format_exc()}"))
    finally:
        cursor.close()
    return update_list

def update_clan_users(conn: Connection, redis_client: Redis, record_id: int):
    conn.begin()
    cursor: Cursor = conn.cursor()
    try:
        sql = """
            SELECT 
                b.region_id, 
                b.clan_id, 
                u.member_ids, 
                UNIX_TIMESTAMP(u.touch_at) 
            FROM clan_users AS u 
            LEFT JOIN clan_base AS b 
              ON b.clan_id = u.clan_id 
            WHERE u.id = %s;
        """
        cursor.execute(sql, [record_id])
        data = cursor.fetchone()
        # 获取到空数据，直接进入下一个循环
        # 但理论上不会获取到
        if data is None:
            conn.commit()
            return 'NoData'
        region_id = data[0]
        clan_id = data[1]
        result = get_clan_users(redis_client, region_id, clan_id)
        if isinstance(result, str):
            return f'{region_id}-{clan_id} | {result}'
        users = {}
        for user_info in result.get('items'):
            users[user_info['id']] = user_info['name']
        # 当前工会内玩家id列表
        user_ids = list(users.keys())
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
            conn.commit()
            return f'{region_id}-{clan_id} | Inactive'
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
                    region_id, 
                    account_id, 
                    username
                ) VALUES (
                    %s, %s, %s
                );
            """
            cursor.execute(sql, [region_id, account_id, f'User_{account_id}'])
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
            sql = """
                UPDATE user_base 
                SET 
                    username = %s, 
                    touch_at = CURRENT_TIMESTAMP 
                WHERE region_id = %s 
                AND account_id = %s;
            """
            cursor.execute(sql,[users[account_id], region_id, account_id])
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
        added = '-'
        removed = '-'
        # 更新工会所在用户数据
        if data[3]:
            old_data = json.loads(data[2] if data[2] else '[]')
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
            added = len(added_ids)
            removed = len(removed_ids)
        conn.commit()
        return f'{region_id}-{clan_id} | Members: {len(user_ids)}  Added: {added}  Removed: {removed}'
    except Exception as e:
        conn.rollback()
        logger.error((f"{traceback.format_exc()}"))
        return type(e).__name__
    finally:
        cursor.close()