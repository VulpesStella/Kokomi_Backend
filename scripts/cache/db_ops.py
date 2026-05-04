import json
import uuid
import traceback
from typing import Optional
from redis import Redis
from pymysql import Connection
from pymysql.cursors import Cursor

from logger import logger
from settings import METRIC_ID_TO_INDEX


def read_ship_record(mysql_connection: Connection) -> dict | str:
    """读取船只记录数据"""
    try:
        result = {}
        cursor: Cursor = mysql_connection.cursor()
        
        metric_ids = list(METRIC_ID_TO_INDEX.keys())
        placeholders = ','.join(['%s'] * len(metric_ids))
        sql = f"""
            SELECT 
                ship_id,
                metric_id,
                metric_value,
                users_count,
                top_user_id
            FROM T_ship_pvp_record
            WHERE metric_id IN ({placeholders});
        """
        cursor.execute(sql, metric_ids)
        
        for row in cursor.fetchall():
            ship_id = str(row[0])
            metric_id = row[1]
            
            if ship_id not in result:
                result[ship_id] = [[0, 0, None] for _ in range(len(METRIC_ID_TO_INDEX))]
            
            idx = METRIC_ID_TO_INDEX[metric_id]
            result[ship_id][idx] = [row[2], row[3], row[4]]
        
        return result
    except Exception as e:
        logger.error(traceback.format_exc())
        return type(e).__name__
    finally:
        if 'cursor' in locals():
            cursor.close()

def read_ship_data(mysql_connection: Connection) -> dict | str:
    """加载船只排行统计数据"""
    try:
        ship_info = {}
        cursor: Cursor = mysql_connection.cursor()
        sql = """
            SELECT 
                ship_id, 
                min_battles, 
                win_rate, 
                avg_damage, 
                avg_frags
            FROM V_ship_ranking_stats;
        """
        cursor.execute(sql)
        rows = cursor.fetchall()
        for row in rows:
            ship_info[str(row[0])] = [
                row[1],
                [row[2], row[3], row[4]]
            ]
        return ship_info
    except Exception as e:
        logger.error(traceback.format_exc())
        return type(e).__name__
    finally:
        if 'cursor' in locals():
            cursor.close()

def get_update_ids(mysql_connection: Connection) -> list:
    """获取需要更新的用户ID列表"""
    update_list = []
    try:
        cursor: Cursor = mysql_connection.cursor()
        sql = """
            SELECT 
                s.account_id
            FROM T_user_stats s
            LEFT JOIN T_user_pvp p 
              ON s.account_id = p.account_id
            WHERE 
                p.updated_at IS NULL
                OR (
                    s.is_enabled = 1
                    AND s.is_public = 1
                    AND s.pvp_battles <> p.battles
                );
        """
        cursor.execute(sql)
        update_list = [row[0] for row in cursor.fetchall()]
    except Exception as e:
        logger.error(traceback.format_exc())
    finally:
        if 'cursor' in locals():
            cursor.close()
    return update_list

def handle_hidden_profile(
    mysql_connection: Connection, 
    account_id: int
) -> Optional[str]:
    """处理隐藏战绩或无数据的用户"""
    try:
        cursor = mysql_connection.cursor()
        sql = """
            UPDATE T_user_pvp 
            SET 
                battles = 0, 
                win_rate = 0, 
                avg_damage = 0, 
                avg_frags = 0,  
                avg_exp = 0, 
                ship_cache = NULL, 
                updated_at = CURRENT_TIMESTAMP 
            WHERE account_id = %s;
        """
        cursor.execute(sql, [account_id])
        mysql_connection.commit()
        return None
    except Exception as e:
        mysql_connection.rollback()
        logger.error(traceback.format_exc())
        return type(e).__name__
    finally:
        if 'cursor' in locals():
            cursor.close()

def get_local_cache(cursor: Cursor, account_id: int) -> Optional[dict]:
    """获取用户本地的船只缓存数据"""
    sql = """
        SELECT 
            battles, 
            ship_cache 
        FROM T_user_pvp 
        WHERE account_id = %s;
    """
    cursor.execute(
        sql,
        [account_id]
    )
    data = cursor.fetchone()
    if data and data[0] != 0:
        return json.loads(data[1])
    return None

def get_game_version(cursor: Cursor) -> str:
    """获取当前游戏版本"""
    cursor.execute("""
        SELECT short_name 
        FROM T_game_version 
        WHERE is_latest = TRUE 
        LIMIT 1;
    """)
    return cursor.fetchone()[0]

def update_user_pvp(
    cursor: Cursor, 
    account_id: int, 
    overall: dict, 
    ship_pvp_cache: dict
) -> None:
    """更新用户PVP总体数据"""
    sql = """
        UPDATE T_user_pvp 
        SET 
            battles = %s, 
            win_rate = %s, 
            avg_damage = %s, 
            avg_frags = %s, 
            avg_exp = %s, 
            ship_cache = %s, 
            updated_at = CURRENT_TIMESTAMP 
        WHERE account_id = %s;
    """
    cursor.execute(sql, [
        overall['battles_count'],
        overall['win_rate'],
        overall['avg_damage'],
        overall['avg_frags'],
        overall['avg_exp'],
        json.dumps(ship_pvp_cache),
        account_id
    ])

def update_user_pvp_record(
    cursor: Cursor, 
    account_id: int, 
    record: list
) -> None:
    """更新用户PVP最高记录"""
    sql = """
        UPDATE T_user_pvp_record 
        SET 
            max_exp = %s, 
            max_exp_id = %s, 
            max_damage = %s, 
            max_damage_id = %s, 
            max_frags = %s, 
            max_frags_id = %s, 
            max_planes_killed = %s, 
            max_planes_killed_id = %s, 
            max_scouting_damage = %s, 
            max_scouting_damage_id = %s, 
            max_potential_damage = %s, 
            max_potential_damage_id = %s, 
            updated_at = CURRENT_TIMESTAMP 
        WHERE account_id = %s;
    """
    cursor.execute(sql, record + [account_id])

def upsert_ship_pvp_record(
    cursor: Cursor, 
    updated_record: list
) -> None:
    """批量插入或更新船只PVP记录"""
    if not updated_record:
        return
    
    sql = """
        INSERT INTO T_ship_pvp_record (ship_id, metric_id, metric_value, users_count, top_user_id)
        VALUES (%s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            metric_value = VALUES(metric_value),
            users_count = VALUES(users_count),
            top_user_id = VALUES(top_user_id)
    """
    cursor.executemany(sql, updated_record)
    logger.debug(f'Updated {len(updated_record)} rows ship record data')

def upsert_leaderboard(
    cursor: Cursor, 
    ship_ranking_cache: dict, 
    account_id: int
) -> None:
    """批量插入或更新船只排行榜数据"""
    if not ship_ranking_cache:
        return
    
    values_to_insert = []
    for ship_id, data in ship_ranking_cache.items():
        values_to_insert.append((
            account_id,
            ship_id,
            data[0],     # battles
            data[1],     # rating
            data[2],     # win_rate
            data[3],     # solo_rate
            data[4],     # avg_damage
            data[5],     # avg_damage_level
            data[6],     # avg_frags
            data[7],     # avg_frags_level
            data[8],     # avg_exp
            data[9],     # hit_ratio
            data[10],    # max_exp
            data[11]     # max_damage
        ))
    
    sql = """
        INSERT INTO T_ship_pvp_leaderboard (
            account_id, ship_id, battles, rating, win_rate, solo_rate, 
            avg_damage, avg_damage_level, avg_frags, avg_frags_level, avg_exp, hit_ratio, 
            max_exp, max_damage, updated_at
        )
        VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP
        )
        ON DUPLICATE KEY UPDATE 
            rating = VALUES(rating),
            battles = VALUES(battles),
            win_rate = VALUES(win_rate),
            solo_rate = VALUES(solo_rate),
            avg_damage = VALUES(avg_damage),
            avg_damage_level = VALUES(avg_damage_level),
            avg_frags = VALUES(avg_frags),
            avg_frags_level = VALUES(avg_frags_level),
            avg_exp = VALUES(avg_exp),
            hit_ratio = VALUES(hit_ratio),
            max_exp = VALUES(max_exp),
            max_damage = VALUES(max_damage),
            updated_at = CURRENT_TIMESTAMP;
    """
    cursor.executemany(sql, values_to_insert)

def insert_recent_diff_data(
    cursor: Cursor, 
    diff_data: dict, 
    account_id: int
) -> None:
    """插入船只近期数据变化记录，返回插入条数"""
    if not diff_data:
        return
    
    game_version = get_game_version(cursor)
    sql = """
        INSERT INTO STAGING_ship_recent_data 
            (uuid, game_version, account_id, payload)
        VALUES (%s, %s, %s, %s)
    """
    cursor.execute(sql, [str(uuid.uuid4()), game_version, account_id, json.dumps(diff_data)])
    return

def update_redis_leaderboard(
    redis_client: Redis, 
    ship_ranking_cache: dict, 
    account_id: int
) -> None:
    """更新Redis中的排行榜数据"""
    if not ship_ranking_cache:
        return
    
    pipe = redis_client.pipeline()
    for ship_id, values in ship_ranking_cache.items():
        key = f"leaderboard:ship:{ship_id}"
        pipe.zadd(key, {str(account_id): values[1]})
    pipe.execute()