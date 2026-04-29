import random
import logging
import requests
import traceback
from tqdm import tqdm
from redis import Redis
from celery import Celery
from pymysql import Connection
from pymysql.cursors import Cursor
from datetime import datetime, timezone
from typing import Any, Iterator, Optional, Union

from logger import logger
from settings import (
    USE_TQDM,
    DATE_FMT,
    DATA_DIR,
    VORTEX_API,
    USER_INIT_TABLE_LIST,
    CLAN_INIT_TABLE_LIST
)


def _log_warning(message: str) -> None:
    """根据 USE_TQDM 配置输出警告信息"""
    if USE_TQDM:
        tqdm.write(f'{get_formatted_date()} [WARNING] {message}')
    else:
        logger.warning(message)

def _log_error(message: str) -> None:
    """根据 USE_TQDM 配置输出错误信息"""
    if USE_TQDM:
        tqdm.write(f'{get_formatted_date()} [ERROR]\n{message}')
    else:
        logger.error(message)

def get_current_iso_time() -> str:
    """获取当前 UTC 时间的 ISO 格式字符串"""
    return datetime.now(timezone.utc).isoformat(timespec='seconds')

def get_formatted_date() -> str:
    """获取当前日期格式化字符串，用于日志输出"""
    return datetime.now().strftime(DATE_FMT)

def progress_iterable(
    items: list[Any], desc: str, logger_obj: logging.Logger
) -> Iterator[Any]:
    """遍历列表，根据 USE_TQDM 配置使用进度条或日志输出进度。

    Args:
        items: 待遍历的列表。
        desc: 进度描述文本。
        logger_obj: 日志记录器。

    Yields:
        列表中的每个元素。
    """
    if USE_TQDM:
        tqdm_desc = f'{get_formatted_date()} [INFO] {desc}'
        with tqdm(items, desc=tqdm_desc, total=len(items)) as pbar:
            for item in pbar:
                pbar.set_postfix_str(str(item))
                yield item
    else:
        # total = len(items)
        for idx, item in enumerate(items, 1):
            # 不输出日志
            # logger_obj.info('%s - [%d/%d] | Current: %s', desc, idx, total, item)
            yield item

def fetch_data(url):
    """发送 GraphQL 查询到指定 URL，获取游戏版本数据

    Args:
        url: 完整的 API 地址

    Returns:
        成功时返回 JSON 解析后的字典
    """
    try:
        body = [{"query":"query Version {\n  version\n}"}]
        resp = requests.post(url,json=body,timeout=5)
        if resp.status_code == 200:
            return resp.json()
        return f'HTTP_STATUS_{resp.status_code}'
    except Exception as e:
        return f'ERROR_{type(e).__name__}'

def record_http_metrics(
    redis_client: Redis, 
    responses: list[Union[dict, str]]
) -> Optional[str]:
    """记录 HTTP 请求指标到 Redis
    
    如果有多个Error则返回首个Error的信息

    Args:
        redis_client: Redis 客户端
        responses: fetch_data 返回结果列表

    Returns:
        首个错误字符串，全部成功则返回 None
    """
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    error_count = 0
    first_error = None

    for response in responses:
        if isinstance(response, str):
            error_count += 1
            if first_error is None:
                first_error = response

    redis_client.incrby(f'metrics:http_total:{today}', len(responses))
    if error_count > 0:
        redis_client.incrby(f'metrics:http_error:{today}', error_count)

    return first_error

def get_latest_version(redis_client: Redis) -> Union[dict, str]:
    """从 API 获取最新的游戏版本信息

    Args:
        redis_client: Redis 客户端，用于记录请求指标

    Returns:
        包含 'short' 和 'full' 键的 Dict
        失败时返回 None
    """
    try:
        base_url = random.choice(VORTEX_API)
        url = f'{base_url}/api/v2/graphql/glossary/version/'
        result = fetch_data(url)
        error = record_http_metrics(redis_client, [result])
        if error:
            logger.warning(f'{error} {url}')
            return error
        version = result[0]['data']['version']
        return {
            'short': ".".join(version.split(".")[:2]),
            'full': version
        }
    except Exception as e:
        logger.error(traceback.format_exc())
        return type(e).__name__

def refresh_version(conn: Connection, redis_client: Redis) -> None:
    """每小时检查并更新数据库中的游戏版本记录

    Args:
        conn: MySQL 数据库连接
        redis_client: Redis 客户端
    """
    try:
        cursor: Cursor = conn.cursor()
        sql = """
            SELECT 
                short_name, 
                full_name,
                UNIX_TIMESTAMP(updated_at), 
                CASE 
                    WHEN UNIX_TIMESTAMP(updated_at) IS NULL THEN TRUE
                    WHEN CURRENT_TIMESTAMP - UNIX_TIMESTAMP(updated_at) > 3600 THEN TRUE
                    ELSE FALSE
                END AS is_due 
            FROM T_game_version 
            WHERE is_latest = TRUE 
            LIMIT 1;
        """
        cursor.execute(sql)
        local_version = cursor.fetchone()

        if local_version and local_version[3]:
            logger.debug('Skip to refresh version data step')
            return
        
        latest = get_latest_version(redis_client)
        if isinstance(latest, str):
            logger.info(f'Failed to obtain latest version: {latest}')
            return
        
        if not local_version or local_version[0] != latest['short']:
            # 版本有变化或首次插入
            cursor.execute("SELECT id FROM T_game_version WHERE short_name = %s;",[latest['short']])
            existing = cursor.fetchone()
            if existing:
                # 已存在该版本记录：将所有记录的 is_latest 置为 False，再将该记录更新为最新
                cursor.execute("UPDATE T_game_version SET is_latest = FALSE WHERE is_latest = TRUE;")
                sql = """
                    UPDATE T_game_version 
                    SET 
                        is_latest = TRUE, 
                        full_name = %s, 
                        updated_at = CURRENT_TIMESTAMP 
                    WHERE short_name = %s;
                """
                cursor.execute(sql, [latest['full'], latest['short']])
                action_message = (
                    f"Game Version: "
                    f"{local_version[0] if local_version else 'None'} -> {latest['short']}"
                )
            else:
                # 不存在：将所有记录的 is_latest 置为 False，插入新版本记录
                cursor.execute("UPDATE T_game_version SET is_latest = FALSE WHERE is_latest = TRUE;")
                sql = """
                    INSERT INTO T_game_version (is_latest, short_name, full_name) VALUES (TRUE, %s, %s);
                """
                cursor.execute(sql, [latest['short'], latest['full']])
                action_message = (
                    f"Game Version: "
                    f"{local_version[0] if local_version else 'None'} -> {latest['short']}"
                )
        else:
            # 版本未变，只更新 updated_at 时间戳
            sql = """
                UPDATE T_game_version 
                SET 
                    updated_at = CURRENT_TIMESTAMP 
                WHERE is_latest = TRUE;
            """
            cursor.execute(sql)
            action_message = f"Game Version: {latest['short']} -> Latest"
        
        conn.commit()
        logger.info(action_message)
    except Exception:
        conn.rollback()
        logger.error(traceback.format_exc())
    finally:
        if 'cursor' in locals():
            cursor.close()

def send_task(celery_app: Celery, task_name: str, entity_id: int, queue: str) -> bool:
    """向指定队列发送 Celery 任务。

    Args:
        celery_app: Celery 应用实例。
        task_name: 任务名称。
        entity_id: 实体 ID（用户或公会 ID）。
        queue: 目标队列名。

    Returns:
        True 表示发送成功，False 表示失败。
    """
    try:
        celery_app.send_task(
            name=task_name, 
            args=[{'uid': entity_id}], 
            queue=queue
        )
        return True
    except Exception as e:
        _log_error(f"{entity_id} | {type(e).__name__}")
        return False

def maintenance_database(conn: Connection):
    """修复用户和公会基础表中缺失的关联数据行（脏数据修复）。

    遍历 user_base / clan_base 中 table_count 与实际应拥有表数量不一致的记录，
    为缺失的表补充一行初始数据，并更新 table_count。

    Args:
        conn: 数据库连接对象。

    Returns:
        总共修复的行数。
    """
    fixed_count = 0
    cursor: Cursor = conn.cursor()
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
        broken_users = [row[0] for row in cursor.fetchall()]
        for account_id in broken_users:
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
                    sql = """
                        UPDATE T_user_base 
                        SET 
                            table_count = table_count + 1 
                        WHERE account_id = %s;
                    """
                    cursor.execute(sql, [account_id])
                    fixed_count += 1
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
                    sql = """
                        UPDATE T_clan_base 
                        SET 
                            table_count = table_count + 1 
                        WHERE clan_id = %s;
                    """
                    cursor.execute(sql, [clan_id])
                    fixed_count += 1
        conn.commit()
    except Exception:
        conn.rollback()
        logger.error((f"{traceback.format_exc()}"))
    finally:
        cursor.close()
    
    return fixed_count

def get_user_update_ids(mysql_connection: Connection, redis_client: Redis):
    """查询需要更新的用户 ID，并通过 Redis 分布式锁去重

    Args:
        conn: 数据库连接
        redis_client: Redis 客户端

    Returns:
        成功获取锁的用户 ID 列表
    """
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
        if not rows:
            return []

        all_ids = [row[0] for row in rows]
        pipe = redis_client.pipeline()
        keys = [f"refresh_lock:user:{aid}" for aid in all_ids]
        for key in keys:
            pipe.set(key, 1, nx=True, ex=3600)
        # 批量执行
        results = pipe.execute()
        # 根据结果过滤未重复的用户
        update_list = [
            all_ids[i] for i, r in enumerate(results) if r
        ]
    except Exception:
        logger.error((f"{traceback.format_exc()}"))
    finally:
        cursor.close()
    
    return update_list

def get_clan_update_ids(mysql_connection: Connection, redis_client: Redis):
    """查询需要更新的工会 ID，并通过 Redis 分布式锁去重

    Args:
        conn: 数据库连接
        redis_client: Redis 客户端

    Returns:
        成功获取锁的工会 ID 列表
    """
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
        if not rows:
            return []

        all_ids = [row[0] for row in rows]
        pipe = redis_client.pipeline()
        keys = [f"refresh_lock:clan:{cid}" for cid in all_ids]
        for key in keys:
            pipe.set(key, 1, nx=True, ex=3600)
        # 批量执行
        results = pipe.execute()
        # 根据结果过滤未重复的用户
        update_list = [
            all_ids[i] for i, r in enumerate(results) if r
        ]
    except Exception:
        logger.error((f"{traceback.format_exc()}"))
    finally:
        cursor.close()

    return update_list

def _archive_if_needed(
    cursor: Cursor, 
    today: str, 
    game_version: str, 
    tracking_key: str,
    source_table: str, 
    archive_table: str, 
    columns: list[str]
):
    """检查是否需要归档，如需要则按 ship_id 分别执行 INSERT 或 UPDATE

    步骤：
    1. 检查源表整体是否有变化（通过上次归档时间比较）
    2. 读取源表全量数据
    3. 读取归档表中当天+当前版本已有的 ship_id
    4. 已存在 → UPDATE，不存在 → INSERT
    5. 更新跟踪时间
    """

    # 1. 快速检查：源表整体是否有变化
    sql = """
        SELECT 
            UNIX_TIMESTAMP(tracking_value) 
        FROM T_tracking_meta 
        WHERE tracking_key = %s 
          AND tracking_type = 'archive_time';
    """
    cursor.execute(sql, [tracking_key])
    row = cursor.fetchone()
    last_archive_time = row[0] if row and row[0] else None

    cursor.execute(f"SELECT UNIX_TIMESTAMP(MAX(updated_at)) FROM {source_table};")
    current_updated = cursor.fetchone()[0]
    if current_updated is None:
        return
    # 上次归档时间和源表的刷新时间一致则跳过更新
    if last_archive_time and str(current_updated) == str(last_archive_time):
        return

    logger.debug(f'{source_table} changed: {last_archive_time} -> {current_updated}')

    # 2. 读取源表全量数据
    col_names = ', '.join(columns)
    cursor.execute(f"SELECT ship_id, {col_names} FROM {source_table}")
    source_rows = cursor.fetchall()

    # 3. 读取归档表当天+当前版本已有的 ship_id
    sql = f"""
        SELECT ship_id 
        FROM {archive_table}
        WHERE stat_date = %s 
          AND game_version = %s;
    """
    cursor.execute(sql, (today, game_version))
    existing_ids = {row[0] for row in cursor.fetchall()}

    # 4. 收集 INSERT 和 UPDATE 列表
    insert_list = []
    update_list = []

    for source_row in source_rows:
        if source_row[0] in existing_ids:
            update_list.append(source_row)
        else:
            insert_list.append(source_row)

    # 5. 执行 INSERT
    if insert_list:
        placeholders = ', '.join(['%s'] * len(columns))
        insert_sql = f"""
            INSERT INTO {archive_table} 
            (ship_id, stat_date, game_version, {col_names})
            VALUES (%s, %s, %s, {placeholders})
        """
        for row in insert_list:
            cursor.execute(insert_sql, (row[0], today, game_version, *row[1:]))

    # 6. 执行 UPDATE
    if update_list:
        set_clause = ', '.join([f'{col} = %s' for col in columns])
        update_sql = f"""
            UPDATE {archive_table} 
            SET {set_clause}
            WHERE ship_id = %s AND stat_date = %s AND game_version = %s
        """
        for row in update_list:
            cursor.execute(update_sql, (*row[1:], row[0], today, game_version))
    if insert_list or update_list:
        logger.debug(f'Total: {len(insert_list)} inserted, {len(update_list)} updated')

    # 7. 更新跟踪时间
    sql = """
        UPDATE T_tracking_meta 
        SET 
            tracking_value = FROM_UNIXTIME(%s) 
        WHERE tracking_key = %s 
          AND tracking_type = 'archive_time';
    """
    cursor.execute(sql, [current_updated, tracking_key])

    logger.info(f'Table archived: {archive_table}')

def archive_statistics(conn: Connection) -> None:
    """归档用户和工会的统计数据到相应的归档表。
    
    Args:
        conn: 数据库连接
    """
    try:
        cursor: Cursor = conn.cursor()
        today = get_current_iso_time()[:10]
        
        # 归档基础表中的用户和工会数量
        for base_table in ['user_base', 'clan_base']:
            # 查询当前数据行数
            sql = f"SELECT COUNT(*) FROM T_{base_table};"
            cursor.execute(sql)
            user_count = cursor.fetchone()[0]
        
            # 查询今天是否已有用户统计记录
            sql = f"SELECT row_count FROM ARCH_{base_table} WHERE stat_date = %s;"
            cursor.execute(sql, [today])
            user_result = cursor.fetchone()
        
            # 处理用户统计
            if user_result is None:
                # 没有记录，插入新记录
                sql = f"INSERT INTO ARCH_{base_table} (stat_date, row_count) VALUES (%s, %s);"
                cursor.execute(sql, [today, user_count])
            elif user_result[0] != user_count:
                # 有记录但数据有变化，更新
                sql = f"UPDATE ARCH_{base_table} SET row_count = %s WHERE stat_date = %s;"
                cursor.execute(sql, [user_count, today])

            logger.info(f'Table archived: T_{base_table}')
        
        # 获取当前游戏版本号
        sql = """
            SELECT short_name 
            FROM T_game_version 
            WHERE is_latest = TRUE 
            LIMIT 1;
        """
        cursor.execute(sql)
        version_row = cursor.fetchone()
        if not version_row:
            logger.warning('No active game version found, skip archive')
            return
        game_version = version_row[0]

        # 归档 T_ship_stats_by_users
        _archive_if_needed(
            cursor=cursor,
            today=today,
            game_version=game_version,
            tracking_key='ship_users',
            source_table='T_ship_stats_by_users',
            archive_table='ARCH_ship_stats_by_users',
            columns=['users', 'battles', 'win_rate', 'avg_damage', 'avg_frags', 
                     'avg_exp', 'survived_rate', 'avg_scouting_damage', 'avg_potential_damage']
        )

        # 归档 T_ship_stats_by_battles
        _archive_if_needed(
            cursor=cursor,
            today=today,
            game_version=game_version,
            tracking_key='ship_battles',
            source_table='T_ship_stats_by_battles',
            archive_table='ARCH_ship_stats_by_battles',
            columns=['battles', 'win_rate', 'avg_damage', 'avg_frags', 
                     'avg_exp', 'survived_rate', 'avg_scouting_damage', 'avg_potential_damage']
        )

        conn.commit()
    except Exception:
        conn.rollback()
        logger.error(traceback.format_exc())
    finally:
        if 'cursor' in locals():
            cursor.close()