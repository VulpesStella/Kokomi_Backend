import time
import json
import random
import sqlite3
import asyncio
import traceback
from pathlib import Path
from redis import Redis
from httpx import AsyncClient
from pymysql import Connection
from pymysql.cursors import Cursor
from datetime import datetime, timezone

from logger import logger
from utils import del_recent, del_recents, update_base, now_iso, fetch_data, verify_responses, formtimestamp
from settings import SQLITE_PATH, REGION, TIMEZOEN, VORTEX_API


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

def diff_lists(new_data, old_data):
    battles = 0
    result = []
    for new_row, old_row in zip(new_data, old_data):
        if not new_row or not old_row:
            result.append([])
            continue
        row_diff = [n - o for n, o in zip(new_row, old_row)]
        if row_diff[0] == 0:
            result.append([])
            continue
        battles += row_diff[0]
        result.append(row_diff)
    if battles == 0:
        return None
    return result

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
        logger.error((f"{now_iso()} | {traceback.format_exc()}"))
        return False
        
def responeses_processing(responses: list):
    statis_dict = {}
    if len(responses) == 4:
        type_list = [None, 'pvp_solo', 'pvp_div2', 'pvp_div3', 'rank_solo']
        none_list = [0,[],[],[],[]]
    else:
        type_list = [None, 'pvp_solo', 'pvp_div2', 'pvp_div3', 'rank_solo', 'rating_solo', 'rating_div']
        none_list = [0,[],[],[],[],[],[]]
    i = 1
    for response in responses:
        for ship_id, ship_data in response.items():
            if ship_id not in statis_dict:
                statis_dict[ship_id] = none_list.copy()
            battle_type = type_list[i]
            if ship_data[battle_type] != {}:
                statis_dict[ship_id][0] += ship_data[battle_type]['battles_count']
                statis_dict[ship_id][i] = [
                    ship_data[battle_type]['battles_count'],
                    ship_data[battle_type]['wins'],
                    ship_data[battle_type]['losses'],
                    ship_data[battle_type]['damage_dealt'],
                    ship_data[battle_type]['frags'],
                    ship_data[battle_type]['survived'],
                    max(
                        ship_data[battle_type].get('assist_damage', 0), 
                        ship_data[battle_type].get('scouting_damage', 0)
                    ),
                    ship_data[battle_type]['art_agro'],
                    ship_data[battle_type]['original_exp'],
                    ship_data[battle_type]['planes_killed'],
                    ship_data[battle_type]['hits_by_main'],
                    ship_data[battle_type]['shots_by_main']
                ]
        i += 1
    return statis_dict

async def get_recent_data(
    mysql_connection: Connection, 
    redis_client: Redis, 
    async_client: AsyncClient, 
    account_id: int, 
    enable_daily: bool,
    ac: str
):
    # 对于新用户的更新逻辑
    base_url = random.choice(VORTEX_API)
    if REGION == 'ru':
        urls = [
            f'{base_url}/api/accounts/{account_id}/' + (f'?ac={ac}' if ac else ''),
            f'{base_url}/api/accounts/{account_id}/ships/pvp_solo/' + (f'?ac={ac}' if ac else ''),
            f'{base_url}/api/accounts/{account_id}/ships/pvp_div2/' + (f'?ac={ac}' if ac else ''),
            f'{base_url}/api/accounts/{account_id}/ships/pvp_div3/' + (f'?ac={ac}' if ac else ''),
            f'{base_url}/api/accounts/{account_id}/ships/rank_solo/' + (f'?ac={ac}' if ac else ''),
            f'{base_url}/api/accounts/{account_id}/ships/rating_solo/' + (f'?ac={ac}' if ac else ''),
            f'{base_url}/api/accounts/{account_id}/ships/rating_div/' + (f'?ac={ac}' if ac else '')
        ]
    else:
        urls = [
            f'{base_url}/api/accounts/{account_id}/' + (f'?ac={ac}' if ac else ''),
            f'{base_url}/api/accounts/{account_id}/ships/pvp_solo/' + (f'?ac={ac}' if ac else ''),
            f'{base_url}/api/accounts/{account_id}/ships/pvp_div2/' + (f'?ac={ac}' if ac else ''),
            f'{base_url}/api/accounts/{account_id}/ships/pvp_div3/' + (f'?ac={ac}' if ac else ''),
            f'{base_url}/api/accounts/{account_id}/ships/rank_solo/' + (f'?ac={ac}' if ac else '')
        ]
    tasks = [fetch_data(async_client, url) for url in urls]
    responses = await asyncio.gather(*tasks)
    error = verify_responses(redis_client, responses)
    if error != None:
        return error
    user_basic = responses[0]
    update_base(mysql_connection, account_id, user_basic)
    if user_basic:
        user_basic = user_basic[str(account_id)]
    if 'hidden_profile' in user_basic:
        if enable_daily:
            del_recents(mysql_connection, account_id)
        return 'HiddenProfile'
    elif (
        user_basic == None or
        'statistics' not in user_basic or 
        'basic' not in user_basic['statistics'] or 
        user_basic['statistics']['basic']['leveling_points'] == 0
    ):
        # 用户数据不存在删除recent
        del_recent(mysql_connection, account_id)
        return 'DeleteRecent'
    else:
        lbt = user_basic['statistics']['basic']['last_battle_time']
        if int(time.time()) - lbt >= 360*24*60*60:
            # 用户长期不活跃删除recent
            del_recent(mysql_connection, account_id)
            return 'DeleteRecent'
        if enable_daily:
            if int(time.time()) - lbt >= 90*24*60*60:
                # 用户长期不活跃删除recents
                del_recents(mysql_connection, account_id)
                return 'DeleteRecents'
        leveling_points = user_basic['statistics']['basic']['leveling_points']
        karma = user_basic['statistics']['basic']['karma']
        if user_basic['statistics']['pvp'] == {}:
            pvp_count = 0
            win_rate = 0
            avg_damage = 0
            avg_frags = 0
        else:
            pvp_count = user_basic['statistics']['pvp']['battles_count']
            win_rate = round(user_basic['statistics']['pvp']['wins']/pvp_count*100,4)
            avg_damage = round(user_basic['statistics']['pvp']['damage_dealt']/pvp_count,4)
            avg_frags = round(user_basic['statistics']['pvp']['frags']/pvp_count,4)
        if REGION == 'ru':
            statis_dict = responeses_processing([
                responses[1][str(account_id)]['statistics'],
                responses[2][str(account_id)]['statistics'],
                responses[3][str(account_id)]['statistics'],
                responses[4][str(account_id)]['statistics'],
                responses[5][str(account_id)]['statistics'],
                responses[6][str(account_id)]['statistics']
            ])
        else:
            statis_dict = responeses_processing([
                responses[1][str(account_id)]['statistics'],
                responses[2][str(account_id)]['statistics'],
                responses[3][str(account_id)]['statistics'],
                responses[4][str(account_id)]['statistics']
            ])
        return [leveling_points,karma,pvp_count,win_rate,avg_damage,avg_frags,statis_dict]

async def update_user_recent(
    mysql_connection: Connection,
    redis_client: Redis,
    async_client: AsyncClient,
    account_id: int, 
    enable_daily: bool
):
    # 先检测db文件是否存在，不存在则创建
    db_path = SQLITE_PATH / f'{account_id}.db'
    if init_db_if_needed(db_path) is False:
        return 'SQLite3InitializationError'
    redis_key = f"token:ac:{account_id}"
    result = redis_client.get(redis_key)
    if result:
        ac = json.loads(result)
    else:
        ac = None
    # 获取当前和昨天的user表数据
    date_1 = formtimestamp(0)
    date_2 = formtimestamp(1)
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
                pvp_count,
                win_rate, 
                avg_damage, 
                avg_frags, 
                table_name 
            FROM users 
            WHERE date = ?;
        """, [date_2])
        date2_data = cursor.fetchone()    # 昨日数据
        # 新用户，直接写数据库
        if date2_data is None:
            recent_data = await get_recent_data(mysql_connection, redis_client, async_client, account_id, enable_daily, ac)
            # 处理异常
            if isinstance(recent_data, str):
                if recents_data == 'HiddenProfile':
                    # 用户隐藏战绩
                    cursor.execute("""
                        INSERT INTO users (
                            date,is_public,leveling_points,
                            karma,pvp_count,win_rate,avg_damage,
                            avg_frags,table_name
                        ) VALUES (
                            ?,?,?,?,?,?,?,?,?
                        );
                    """,[date_2,0,0,0,0,0,0,0,None])
                    cursor.execute("""
                        INSERT INTO users (
                            date,is_public,leveling_points,
                            karma,pvp_count,win_rate,avg_damage,
                            avg_frags,table_name
                        ) VALUES (
                            ?,?,?,?,?,?,?,?,?
                        );
                    """,[date_1,0,0,0,0,0,0,0,None])
                    conn.commit()
                return recent_data
            leveling_points = recent_data[0]
            karma = recent_data[1]
            pvp_count = recent_data[2]
            win_rate = recent_data[3]
            avg_damage = recent_data[4]
            avg_frags = recent_data[5]
            statis_dict = recent_data[6]
            total_battles = 0
            cache_data = {}
            for ship_id, ship_data in statis_dict.items():
                if ship_data[0] == 0:
                    continue
                total_battles = ship_data[0]
                cache_data[ship_id] = f'{date_2}_{ship_data[0]}'
                cursor.execute("""
                    INSERT OR REPLACE INTO ships (
                        ship_id,
                        date,
                        cache
                    ) VALUES (
                        ?, ?, ?
                    );
                """, [ship_id, date_2, json.dumps(ship_data[1:])])
            cursor.execute("""
                INSERT INTO users (
                    date,is_public,leveling_points,
                    karma,pvp_count,win_rate,avg_damage,
                    avg_frags,table_name
                ) VALUES (
                    ?,?,?,?,?,?,?,?,?
                );
            """,[date_2,1,leveling_points,karma,pvp_count,win_rate,avg_damage,avg_frags,date_1])
            cursor.execute("""
                INSERT INTO users (
                    date,is_public,leveling_points,
                    karma,pvp_count,win_rate,avg_damage,
                    avg_frags,table_name
                ) VALUES (
                    ?,?,?,?,?,?,?,?,?
                );
            """,[date_1,1,leveling_points,karma,pvp_count,win_rate,avg_damage,avg_frags,date_1])
            cursor.execute("""
                INSERT INTO cache (
                    date,total_battles,cache 
                ) VALUES (
                    ?,?,?
                );
            """,[date_1,total_battles, json.dumps(cache_data)])
            conn.commit()
            return 'NewAccount'
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
        date1_data = cursor.fetchone()    # 今日数据
        # 今日日期下没有数据条目，先复制昨日数据条目
        if date1_data is None:
            cursor.execute("""
                INSERT INTO users (
                    date,is_public,leveling_points,karma,
                    pvp_count,win_rate,avg_damage,
                    avg_frags,table_name
                ) VALUES (
                    ?,?,?,?,?,?,?,?
                );
            """,[date_1,date2_data[0],date2_data[1],date2_data[2],date2_data[3],date2_data[4],date2_data[5],date2_data[6],date2_data[7]])
        recent_data = await get_recent_data(mysql_connection, redis_client, async_client, account_id, enable_daily, ac)
        # 处理异常和隐藏战绩
        if isinstance(recent_data, str):
            if recents_data == 'HiddenProfile':
                # 用户隐藏战绩
                cursor.execute("""
                    INSERT INTO users (
                        date,is_public,leveling_points,
                        karma,pvp_count,win_rate,avg_damage,
                        avg_frags,table_name
                    ) VALUES (
                        ?,?,?,?,?,?,?,?,?
                    );
                """,[date_1,0,0,0,0,0,0,0,None])
                conn.commit()
            return recent_data
        leveling_points = recent_data[0]
        karma = recent_data[1]
        pvp_count = recent_data[2]
        win_rate = recent_data[3]
        avg_damage = recent_data[4]
        avg_frags = recent_data[5]
        statis_dict = recent_data[6]
        total_battles = 0
        new_data = {}
        for ship_id, ship_data in statis_dict.items():
            if ship_data[0] == 0:
                continue
            total_battles = ship_data[0]
            new_data[ship_id] = f'{date_1}_{ship_data[0]}'
        # 过去两天都隐藏数据，直接写数据库
        if date1_data[0] == 0 and date2_data[0] == 0:
            total_battles = 0
            cache_data = {}
            for ship_id, ship_data in statis_dict.items():
                if ship_data[0] == 0:
                    continue
                total_battles = ship_data[0]
                cache_data[ship_id] = f'{date_1}_{ship_data[0]}'
                cursor.execute("""
                    INSERT OR REPLACE INTO ships (
                        ship_id,
                        date,
                        cache
                    ) VALUES (
                        ?, ?, ?
                    );
                """, [ship_id, date_2, ship_data[1:]])
            cursor.execute("""
                INSERT INTO users (
                    date,is_public,leveling_points,
                    karma,pvp_count,win_rate,avg_damage,
                    avg_frags,table_name
                ) VALUES (
                    ?,?,?,?,?,?,?,?,?
                );
            """,[date_2,1,leveling_points,karma,pvp_count,win_rate,avg_damage,avg_frags,date_2])
            cursor.execute("""
                INSERT INTO users (
                    date,is_public,leveling_points,
                    karma,pvp_count,win_rate,avg_damage,
                    avg_frags,table_name
                ) VALUES (
                    ?,?,?,?,?,?,?,?,?
                );
            """,[date_1,1,leveling_points,karma,pvp_count,win_rate,avg_damage,avg_frags,date_2])
            cursor.execute("""
                INSERT INTO cache (
                    date,total_battles,cache 
                ) VALUES (
                    ?,?,?
                );
            """,[date_2,total_battles, json.dumps(cache_data)])
            conn.commit()
            return 'FullUpdate'
        # 今日或昨日有数据
        if date1_data[0] == 0 and date2_data[0] == 1:
            old_table_name = date2_data[7]
        else:
            old_table_name = date1_data[7]
        cursor.execute("""
            SELECT 
                total_battles, 
                cache 
            FROM cache 
            WHERE date = ?;
        """, [old_table_name])
        old_data = cursor.fetchone()
        old_total_battles = old_data[0]
        old_battles = json.loads(old_data[1])
        changed_ship_ids = []
        # 没有数据更改
        new_battles = {}
        if total_battles == old_total_battles and old_battles == new_data:
            sql = """
                REPLACE INTO users (
                    date,is_public,leveling_points,
                    karma,pvp_count,win_rate,avg_damage,
                    avg_frags,table_name
                ) VALUES (
                    ?,?,?,?,?,?,?,?,?
                );
            """
            cursor.execute(sql, [
                date_1,1,leveling_points,karma,pvp_count,win_rate,avg_damage,avg_frags,old_table_name
            ])
            return 'NoChanged'
        for ship_id, ship_data in new_data.items():
            if ship_id not in old_battles:
                changed_ship_ids.append(ship_id)
                new_battles[ship_id] = ship_data
            if old_battles[ship_id] != ship_data:
                changed_ship_ids.append(ship_id)
                new_battles[ship_id] = ship_data
            new_battles[ship_id] = old_battles[ship_id]
        # 对于启用recents用户计算数据
        if enable_daily and date1_data[0] == 1:
            recents_data = {}
            redis_key = f"recent:{account_id}:{int(time.time())}"
            for ship_id in changed_ship_ids:
                if ship_id not in old_battles:
                    if statis_dict[ship_id][0] > 0:
                        recents_data[ship_id] = statis_dict[ship_id][1:]
                else:
                    old_ship_table_name = old_battles[ship_id].split('_')[0]
                    sql = """
                        SELECT 
                            cache 
                        FROM ships 
                        WHERE ship_id = ? 
                        AND date = ?;
                    """
                    cursor.execute(sql, [ship_id, old_ship_table_name])
                    old_data = json.loads(cursor.fetchone())
                    temp_data = diff_lists(statis_dict[ship_id][1:],old_data)
                    if temp_data:
                        recents_data[ship_id] = temp_data
            if recents_data != {}:
                redis_client.set(redis_key, json.dumps(recents_data), 7*24*60*60)
        # 将新数据写入数据库
        cursor.execute("""
            REPLACE INTO cache (
                date,total_battles,cache 
            ) VALUES (
                ?,?,?
            );
        """,[date_1,total_battles, json.dumps(new_battles)])
        cursor.execute("""
            REPLACE INTO users (
                date,is_public,leveling_points,
                karma,pvp_count,win_rate,avg_damage,
                avg_frags,table_name
            ) VALUES (
                ?,?,?,?,?,?,?,?,?
            );
        """,[date_1,1,leveling_points,karma,pvp_count,win_rate,avg_damage,avg_frags,date_1])
        ships_cache = []
        for ship_id in changed_ship_ids:
            ships_cache.append([ship_id,date_1,json.dumps(statis_dict[ship_id][1:],separators=(",", ":"))])
        for ship_cache in ships_cache:
            cursor.execute("""
                INSERT OR REPLACE INTO ships (
                    ship_id,
                    date,
                    cache
                ) VALUES (
                    ?,?,?
                );
            """, ship_cache)
        conn.commit()
        return 'ChangedUpdate'
    except Exception as e:
        conn.rollback()
        logger.error((f"{traceback.format_exc()}"))
        return type(e).__name__
    finally:
        conn.close()
    