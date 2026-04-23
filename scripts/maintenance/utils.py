import json
import random
import requests
import traceback
from redis import Redis
from pymysql import Connection
from pymysql.cursors import Cursor
from datetime import datetime, timezone

from logger import logger
from settings import (
    DATA_DIR,
    VORTEX_API,
    USER_INIT_TABLE_LIST,
    CLAN_INIT_TABLE_LIST
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

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

def read_version_data():
    file_path = DATA_DIR / f'json/game_version.json'
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        return data

def get_least_version(redis_client: Redis):
    base_url = random.choice(VORTEX_API)
    url = f'{base_url}/api/v2/graphql/glossary/version/'
    result = fetch_data(url)
    error = verify_responses(redis_client, [result])
    if error != None:
        return error
    try:
        version = result[0]['data']['version']
        return {
            'short': ".".join(version.split(".")[:2]),
            'full': version
        }
    except Exception as e:
        logger.error(f"{traceback.format_exc()}")
        return type(e).__name__

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
            FROM T_user_base;
        """
        cursor.execute(sql)
        data = cursor.fetchone()
        max_id = data[0] if data[0] else 0
        logger.info(f'Max id in table user_base: {max_id}')
        sql = """
            SELECT 
                account_id
            FROM T_user_base 
            WHERE table_count != %s;
        """
        cursor.execute(sql, [len(USER_INIT_TABLE_LIST)])
        verify_list = [row[0] for row in cursor.fetchall()]
        for account_id in verify_list:
            for table_name in USER_INIT_TABLE_LIST:
                sql = f"""
                    SELECT 
                        account_id 
                    FROM {table_name}
                    WHERE account_id = %s;
                """
                cursor.execute(sql, [account_id])
                result = cursor.fetchone()
                if result is None:
                    sql = f"""
                        INSERT INTO {table_name} (
                            account_id
                        ) VALUES (
                            %s
                        );
                    """
                    cursor.execute(sql, [account_id])
                    fixed_count += 1
                    sql = """
                        UPDATE T_user_base 
                        SET 
                            table_count = table_count + 1 
                        WHERE account_id = %s;
                    """
                    cursor.execute(sql, [account_id])
        # 效验clan表的完整型
        sql = """
            SELECT 
                MAX(id) 
            FROM T_clan_base;
        """
        cursor.execute(sql)
        data = cursor.fetchone()
        max_id = data[0] if data[0] else 0
        logger.info(f'Max id in table clan_base: {max_id}')
        sql = """
            SELECT 
                clan_id
            FROM T_clan_base 
            WHERE table_count != %s;
        """
        cursor.execute(sql, [len(CLAN_INIT_TABLE_LIST)])
        verify_list = [row[0] for row in cursor.fetchall()]
        for clan_id in verify_list:
            for table_name in CLAN_INIT_TABLE_LIST:
                sql = f"""
                    SELECT 
                        clan_id 
                    FROM {table_name}
                    WHERE clan_id = %s;
                """
                cursor.execute(sql, [clan_id])
                result = cursor.fetchone()
                if result is None:
                    sql = f"""
                        INSERT INTO {table_name} (
                            clan_id
                        ) VALUES (
                            %s
                        );
                    """
                    cursor.execute(sql, [clan_id])
                    fixed_count += 1
                    sql = """
                        UPDATE T_clan_base 
                        SET 
                            table_count = table_count + 1 
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

def get_user_update_ids(mysql_connection: Connection, redis_client: Redis):
    # 从数据库中批量读取并判断那些用户需要更新
    update_list = []
    cursor: Cursor = mysql_connection.cursor()
    try:
        sql = """
            SELECT 
                account_id 
            FROM V_user_update_schedule
            WHERE is_due = 1;
        """
        cursor.execute(sql)
        rows = cursor.fetchall()
        temp_update_list = []
        for row in rows:
            temp_update_list.append(row[0])
        pipe = redis_client.pipeline()
        keys = [f"refresh_lock:user:{aid}" for aid in temp_update_list]
        for key in keys:
            pipe.set(key, 1, nx=True, ex=60*60)
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
                clan_id 
            FROM V_clan_update_schedule
            WHERE is_due = 1;
        """
        cursor.execute(sql)
        rows = cursor.fetchall()
        temp_update_list = []
        for row in rows:
            temp_update_list.append(row[0])
        pipe = redis_client.pipeline()
        keys = [f"refresh_lock:clan:{cid}" for cid in temp_update_list]
        for key in keys:
            pipe.set(key, 1, nx=True, ex=60*60)
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