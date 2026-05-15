import json
import sqlite3
import traceback
from redis import Redis
from httpx import AsyncClient
from pymysql import Connection
from sqlite3 import Cursor
from typing import Optional
from typing_extensions import TypedDict

from logger import logger
from syncer import UserStatsSyncer
from api import fetch_user_recent_data
from utils import get_reset_date
from settings import SQLITE_DIR, CREATE_SQL

class UserConfig(TypedDict):
    level: int
    limit: int

class UserStats(TypedDict):
    is_public: bool
    total_battles: int
    pve_battles: int
    pvp_battles: int
    ranked_battles: int
    karma: int

HIDDEN_USER_STATS = UserStats(
    is_public=0,
    total_battles=0,
    pve_battles=0,
    pvp_battles=0,
    ranked_battles=0,
    karma=0
)

class UserRecentUpdater:
    def _process_responeses(responses: list):
        statis_dict = {}
        type_list = ['pvp_solo', 'pvp_div2', 'pvp_div3', 'rank_solo']
        for i in range(4):
            for ship_id, ship_data in responses[i].items():
                battle_type = type_list[i]
                if ship_data[battle_type] == {}:
                    continue
                if ship_data[battle_type]['battles_count'] == 0:
                    continue
                if ship_id not in statis_dict:
                    statis_dict[ship_id] = {
                        'battles': 0,
                        'values': [
                            None, None, None, None
                        ]
                    }
                statis_dict[ship_id]['battles'] += ship_data[battle_type]['battles_count']
                statis_dict[ship_id]['values'][i] = [
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
        return statis_dict

    def _init_null_data(cursor: Cursor, current_timestamp: int):
        sql = """
            INSERT INTO user_daily_summary (
                snapshot_date,
                is_public,
                total_battles,
                pve_battles,
                pvp_battles,
                ranked_battles,
                karma,
                index_table
            ) VALUES (
                ?,1,0,0,0,0,0,NULL
            );
        """
        cursor.execute(sql, [get_reset_date(current_timestamp - 86400)])
        cursor.execute(sql, [get_reset_date(current_timestamp)])

    def _read_base_daily_summary(cursor: Cursor, now_date: int):
        sql = """
            SELECT 
                is_public, 
                pvp_battles, 
                ranked_battles, 
                index_table, 
                updated_at
            FROM user_daily_summary 
            WHERE snapshot_date = ?;
        """
        cursor.execute(sql, [now_date])
        return cursor.fetchone()

    def _read_full_daily_summary(cursor: Cursor, snapshot_date: int):
        sql = """
            SELECT 
                is_public, 
                total_battles, 
                pve_battles, 
                pvp_battles, 
                ranked_battles, 
                karma, 
                index_table, 
                updated_at
            FROM user_daily_summary 
            WHERE snapshot_date = ?;
        """
        cursor.execute(sql, [snapshot_date])
        data = cursor.fetchone()
        if data:
            return list(data)
        else:
            return
    
    def _copy_daily_summary(cursor: Cursor, now_date: int, daily_summary: list | tuple):
        sql = """
            INSERT INTO user_daily_summary (
                snapshot_date,
                is_public,
                total_battles,
                pve_battles,
                pvp_battles,
                ranked_battles,
                karma,
                index_table, 
                updated_at  
            ) VALUES (
                ?,?,?,?,?,?,?,?,?
            );
        """
        cursor.execute(sql, [now_date] + daily_summary)

    def _update_daily_summary(
        cursor: Cursor, 
        snapshot_date: int, 
        summary_data: UserStats, 
        index_table: Optional[str], 
        update_time: int
    ):
        sql = """
            UPDATE user_daily_summary 
            SET
                is_public = ?,
                total_battles = ?,
                pve_battles = ?, 
                pvp_battles = ?, 
                ranked_battles = ?, 
                karma = ?, 
                index_table = ?,
                updated_at = ?
            WHERE snapshot_date = ?;
        """
        cursor.execute(sql, [
            summary_data['is_public'],
            summary_data['total_battles'],
            summary_data['pve_battles'],
            summary_data['pvp_battles'],
            summary_data['ranked_battles'],
            summary_data['karma'],
            index_table,
            update_time,
            snapshot_date
        ])

    def _insert_snapshot_index(cursor, snapshot_date: int, ship_count: int, ship_map: dict):
        sql = """
            INSERT INTO daily_snapshot_index (
                snapshot_date, ship_count, ship_map
            ) VALUES (
                ?,?,?
            );
        """
        cursor.execute(sql, [snapshot_date, ship_count, json.dumps(ship_map)])

    def _insert_latest_cache_many(cursor: Cursor, rows: list):
        sql = """
            INSERT INTO ship_latest_cache (
                ship_id, battles, snapshot_date
            ) VALUES (
                ?,?,?
            );
        """
        cursor.executemany(sql, rows)

    def _insert_daily_snapshot_many(cursor: Cursor, rows: list):
        sql = """
            INSERT INTO ship_daily_snapshot (
                ship_id, snapshot_date, snapshot_data
            ) VALUES (
                ?,?,?
            );
        """
        cursor.executemany(sql, rows)

    def _update_latest_cache_many(cursor: Cursor, rows: list):
        sql = """
            UPDATE ship_latest_cache 
            SET 
                battles = ?, 
                snapshot_date = ?, 
                updated_at = CURRENT_TIMESTAMP 
            WHERE ship_id = ?;
        """
        cursor.executemany(sql, rows)

    def _update_daily_snapshot_many(cursor: Cursor, rows: list):
        sql = """
            UPDATE ship_daily_snapshot 
            SET 
                snapshot_data = ?, 
                updated_at = CURRENT_TIMESTAMP 
            WHERE ship_id = ? 
                AND snapshot_date = ?;
        """
        cursor.executemany(sql, rows)

    def _read_latest_cache(cursor: Cursor):
        sql = """
            SELECT 
                ship_id, 
                battles, 
                snapshot_date
            FROM ship_latest_cache;
        """
        cursor.execute(sql)
        data = {}
        for row in cursor.fetchall():
            data[str(row[0])] = [row[1], row[2]]
        return data
    
    @classmethod
    def need_update(
        cls,
        account_id: int, 
        current_timestamp: int,
        user_latest_stats: Optional[UserStats],
        user_update_time: Optional[int]
    ) -> bool:
        db_path = SQLITE_DIR / f'{account_id}.db'
        
        # 用户数据库文件不存在
        if not db_path.exists():
            try:
                with sqlite3.connect(db_path) as conn:
                    cursor = conn.cursor()
                    # 初始化数据库
                    cursor.executescript(CREATE_SQL)
                    # 插入空数据
                    cls._init_null_data(cursor, current_timestamp)
                    conn.commit()
                    # 需要更新，此时用户的daily summary表插入了两条updated_at为NULL的数据
                    logger.debug(f'{account_id} | Updated - New user')
                    return True
            except Exception:
                logger.error(f'{account_id} | SQLite3 initialization error')
                logger.error(traceback.format_exc())
                if 'conn' in locals():
                    conn.close()
                if db_path.exists():
                    logger.warning(f"Corrupted database file deleted: {db_path}")
                    db_path.unlink(missing_ok=True)
                # 初始化文件失败，不进行后续的更新操作
                logger.debug(f'{account_id} | Skipped - Error (1001)')
                return False
        
        now_date = get_reset_date(current_timestamp)
        
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            # 先从数据库中检测数据库是否存在now_date的daily summary的数据
            now_date_summary = cls._read_base_daily_summary(cursor, now_date)
            # 有今日数据
            if now_date_summary:
                # 最新daily summary的updated_at为NULL
                # 可能是用户上个更新失败或者本地测试
                if now_date_summary[4] is None:
                    logger.debug(f'{account_id} | Updated - Latest record `updated_at` is NULL (1002)')
                    return True
                # 主数据库中不存在该用户的数据，仅可能在本地测试时或者Admin主动注册服务存在此情况
                # 生产环境下需要先效验后才可注册本服务，故主数据库一定存在该用户数据
                if not user_latest_stats:
                    logger.debug(f'{account_id} | Updated - User latest stats is NULL (1003)')
                    return True
                # 用户当前隐藏战绩，不需要更新
                if not user_latest_stats['is_public']:
                    # 如果今日有更新数据则保留今日数据
                    # 如果有数据但是非今日更新的数据则将本日daily summary置为隐藏
                    if now_date_summary[0] and now_date_summary[3] != now_date:
                        cls._update_daily_summary(cursor, now_date, HIDDEN_USER_STATS, None, user_update_time)
                        conn.commit()
                    logger.debug(f'{account_id} | Skipped - Hidden profile (1004)')
                    return False
                # 没有pvp或ranked场次的修改
                if (
                    now_date_summary[1] == user_latest_stats['pvp_battles'] and 
                    now_date_summary[2] == user_latest_stats['ranked_battles']
                ):
                    # 仅更新基本数据（total_battles, karma等）
                    if user_update_time > now_date_summary[4]:
                        cls._update_daily_summary(cursor, now_date, user_latest_stats, now_date_summary[3], user_update_time)
                        conn.commit()
                    logger.debug(f'{account_id} | Skipped - No changed (1005)')
                    return False
                # 更新条件：
                # 1. 用户没有隐藏战绩
                # 2. pvp/rank场次存在更改（存在战斗数据）
                logger.debug(f'{account_id} | Updated - Changed (1006)')
                return True
            
            yesterday = get_reset_date(current_timestamp-86400)
            # 用户没有今日数据，先尝试从读取昨日的daily summary数据
            last_daily_summary = cls._read_full_daily_summary(cursor, yesterday)
            
            if last_daily_summary is None:
                # 没有读取到昨日的数据，说明数据库存在数据缺失的情况
                # 如果缺失的数据超过2天则必须通过修复脚本修复
                # 按新用户的情况处理数据
                cls._init_null_data(cursor, current_timestamp)
                conn.commit()
                logger.debug(f'{account_id} | Updated - Lose yesterday record (1007)')
                return True
            
            # 有昨日数据，先将昨日数据复制到今日
            cls._copy_daily_summary(cursor, now_date, last_daily_summary)
            conn.commit()

            # 更新出现异常，导致昨日daily summary的updated_at为NULL
            # 按新用户的情况处理数据
            if last_daily_summary[7] is None:
                logger.debug(f'{account_id} | Updated - Yesterday record `updated_at` is NULL (1008)')
                return True
            
            # 用户当前隐藏战绩，不需要更新
            if not user_latest_stats['is_public']:
                cls._update_daily_summary(cursor, now_date, HIDDEN_USER_STATS, None, user_update_time)
                conn.commit()
                logger.debug(f'{account_id} | Skipped - Hidden profile (1009)')
                return False

            # 没有pvp或ranked场次的修改
            if (
                last_daily_summary[3] == user_latest_stats['pvp_battles'] and 
                last_daily_summary[4] == user_latest_stats['ranked_battles']
            ):
                # 仅更新基本数据（total_battles, karma等）
                if user_update_time > last_daily_summary[7]:
                    cls._update_daily_summary(cursor, now_date, user_latest_stats, last_daily_summary[6], user_update_time)
                    conn.commit()
                logger.debug(f'{account_id} | Skipped - No changed (1010)')
                return False
            # 更新条件：
            # 1. 用户没有隐藏战绩
            # 2. pvp/rank场次存在更改（存在战斗数据）
            logger.debug(f'{account_id} | Updated - Changed (1011)')
            return True

    @classmethod
    async def main(
        cls, 
        mysql_connection: Connection,
        redis_client: Redis,
        async_client: AsyncClient,
        account_id: int,
        user_config: UserConfig,
        current_timestamp: int
    ) -> str:
        # 从接口读取数据
        responses = await fetch_user_recent_data(async_client, redis_client, account_id)
        if not responses:
            logger.error(f'{account_id} | Failed to obtain data (2001)')
            return
            
        basic_data = responses[0]
        
        # 刷新用户基础信息
        update_timestamp = UserStatsSyncer.refresh(mysql_connection, account_id, basic_data)
        if update_timestamp is None:
            logger.error(f'{account_id} | Refresh failed (2002)')
            return
        
        logger.debug(f'{account_id} | Refresh success')

        if basic_data:
            basic_data = basic_data.get(str(account_id))

        if 'hidden_profile' not in basic_data:
            statistics = basic_data.get('statistics', {})
            user_info = statistics.get('basic', {})
            leveling_points = user_info.get('leveling_points', 0)
            if leveling_points >= 1000000:
                leveling_points = leveling_points - 1000000
            user_latest_stats = UserStats(
                is_public=1,
                total_battles=leveling_points,
                pve_battles=statistics.get('pve', {}).get('battles_count', 0),
                pvp_battles=statistics.get('pvp', {}).get('battles_count', 0),
                ranked_battles=statistics.get('rank_solo', {}).get('battles_count', 0),
                karma=user_info.get('karma', 0)
            )
        else:
            user_latest_stats = HIDDEN_USER_STATS

        db_path = SQLITE_DIR / f'{account_id}.db'
        now_date = get_reset_date(current_timestamp)
        
        # 无随机或排位数据情况，只需要更新daily summary表
        if user_latest_stats['pvp_battles'] + user_latest_stats['ranked_battles'] == 0:
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                now_date_summary = cls._read_base_daily_summary(cursor, now_date)
                if now_date_summary[4] is None:
                    yesterday = get_reset_date(current_timestamp - 86400)
                    cls._update_daily_summary(cursor, yesterday, user_latest_stats, None, update_timestamp)
                    cls._update_daily_summary(cursor, now_date, user_latest_stats, None, update_timestamp)
                else:
                    cls._update_daily_summary(cursor, now_date, user_latest_stats, None, update_timestamp)
                conn.commit()
            logger.debug(f'{account_id} | No data / Hidden (2003)')
            return
        else:
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                # 本地数据库中船只的缓存数据
                local_date_summary = cls._read_base_daily_summary(cursor, now_date)
                local_dict = cls._read_latest_cache(cursor)
            
        latest_dict = cls._process_responeses([
            responses[1][str(account_id)]['statistics'],
            responses[2][str(account_id)]['statistics'],
            responses[3][str(account_id)]['statistics'],
            responses[4][str(account_id)]['statistics']
        ])

        latest_ship_count = 0
        latest_ship_map = {}
        latest_ship_cache = {
            'insert': [],
            'update': []
        }
        latest_shapshot = {
            'insert': [],
            'update': []
        }
        
        # 新用户，没有本地数据和updated_at数据
        if local_date_summary[4] is None and local_dict == {}:
            yesterday = get_reset_date(current_timestamp-86400)
            for ship_id, ship_data in latest_dict.items():
                latest_ship_cache['insert'].append([
                    ship_id, ship_data['battles'], yesterday
                ])
                latest_shapshot['insert'].append([
                    ship_id, yesterday, json.dumps(ship_data['values'])
                ])
                latest_ship_count += 1
                latest_ship_map[ship_id] = yesterday

            with sqlite3.connect(db_path) as conn:
                try:
                    cursor = conn.cursor()
                    cursor.execute("BEGIN IMMEDIATE")
                    cls._update_daily_summary(cursor, yesterday, user_latest_stats, yesterday, update_timestamp)
                    cls._update_daily_summary(cursor, now_date, user_latest_stats, yesterday, update_timestamp)
                    cls._insert_snapshot_index(cursor, yesterday, latest_ship_count, latest_ship_map)
                    if len(latest_ship_cache['insert']) > 0:
                        cls._insert_latest_cache_many(cursor, latest_ship_cache['insert'])
                    if len(latest_shapshot['insert']) > 0:
                        cls._insert_daily_snapshot_many(cursor, latest_shapshot['insert'])
                    cursor.execute("COMMIT")
                except Exception:
                    cursor.execute("ROLLBACK")
                    logger.error(traceback.format_exc())
            logger.debug(f'{account_id} | New user (2004)')

        # 用户有本地缓存数据，但是没有今日数据的updated_at
        # 可能是异常导致的数据存在缺失
        if local_date_summary[4] is None:
            changed_rows = 0
            yesterday = get_reset_date(current_timestamp-86400)
            for ship_id, ship_data in latest_dict.items():
                if ship_id not in local_dict:
                    changed_rows += 1
                    latest_ship_cache['insert'].append([
                        ship_id, ship_data['battles'], yesterday
                    ])
                    latest_shapshot['insert'].append([
                        ship_id, yesterday, json.dumps(ship_data['values'])
                    ])
                    latest_ship_count += 1
                    latest_ship_map[ship_id] = yesterday
                elif ship_data['battles'] != local_dict[ship_id][0]:
                    changed_rows += 1
                    latest_ship_cache['insert'].append([
                        int(ship_id), ship_data['battles'], yesterday
                    ])
                    latest_shapshot['insert'].append([
                        ship_id, yesterday, json.dumps(ship_data['values'])
                    ])
                    latest_ship_count += 1
                    latest_ship_map[ship_id] = now_date
                else:
                    # 本地数据和最新数据间没有修改
                    latest_ship_count += 1
                    latest_ship_map[ship_id] = local_dict[ship_id][1]
            if changed_rows == 0:
                with sqlite3.connect(db_path) as conn:
                    try:
                        cursor = conn.cursor()
                        cursor.execute("BEGIN IMMEDIATE")
                        cls._update_daily_summary(cursor, yesterday, user_latest_stats, yesterday, update_timestamp)
                        cls._update_daily_summary(cursor, now_date, user_latest_stats, yesterday, update_timestamp)
                        cls._insert_snapshot_index(cursor, yesterday, latest_ship_count, latest_ship_map)
                        cursor.execute("COMMIT")
                    except Exception:
                        cursor.execute("ROLLBACK")
                        logger.error(traceback.format_exc())
                logger.debug(f'{account_id} | Fix database / No changed (2005)')
            else:
                with sqlite3.connect(db_path) as conn:
                    try:
                        cursor = conn.cursor()
                        cursor.execute("BEGIN IMMEDIATE")
                        cls._update_daily_summary(cursor, yesterday, user_latest_stats, yesterday, update_timestamp)
                        cls._update_daily_summary(cursor, now_date, user_latest_stats, yesterday, update_timestamp)
                        cls._insert_snapshot_index(cursor, yesterday, latest_ship_count, latest_ship_map)
                        if len(latest_ship_cache['insert']) > 0:
                            cls._insert_latest_cache_many(cursor, latest_ship_cache['insert'])
                        if len(latest_ship_cache['update']) > 0:
                            cls._update_latest_cache_many(cursor, latest_ship_cache['update'])
                        if len(latest_shapshot['insert']) > 0:
                            cls._insert_daily_snapshot_many(cursor, latest_shapshot['insert'])
                        if len(latest_shapshot['update']) > 0:
                            cls._update_daily_snapshot_many(cursor, latest_shapshot['update'])
                        cursor.execute("COMMIT")
                    except Exception:
                        cursor.execute("ROLLBACK")
                        logger.error(traceback.format_exc())
                logger.debug(f'{account_id} | Fix database / Changed (2006)')
        else:
            changed_rows = 0
            for ship_id, ship_data in latest_dict.items():
                if ship_id not in local_dict:
                    changed_rows += 1
                    latest_ship_cache['insert'].append([
                        ship_id, ship_data['battles'], now_date
                    ])
                    latest_shapshot['insert'].append([
                        ship_id, now_date, json.dumps(ship_data['values'])
                    ])
                    latest_ship_count += 1
                    latest_ship_map[ship_id] = now_date
                elif ship_data['battles'] != local_dict[ship_id][0]:
                    changed_rows += 1
                    latest_ship_cache['insert'].append([
                        int(ship_id), ship_data['battles'], now_date
                    ])
                    latest_shapshot['insert'].append([
                        ship_id, now_date, json.dumps(ship_data['values'])
                    ])
                    latest_ship_count += 1
                    latest_ship_map[ship_id] = now_date
                else:
                    # 本地数据和最新数据间没有修改
                    latest_ship_count += 1
                    latest_ship_map[ship_id] = local_dict[ship_id][1]
            if changed_rows == 0:
                with sqlite3.connect(db_path) as conn:
                    try:
                        cursor = conn.cursor()
                        cursor.execute("BEGIN IMMEDIATE")
                        cls._update_daily_summary(cursor, now_date, user_latest_stats, now_date, update_timestamp)
                        cls._insert_snapshot_index(cursor, now_date, latest_ship_count, latest_ship_map)
                        cursor.execute("COMMIT")
                    except Exception:
                        cursor.execute("ROLLBACK")
                        logger.error(traceback.format_exc())
                logger.debug(f'{account_id} | Success / No changed (2007)')
            else:
                with sqlite3.connect(db_path) as conn:
                    try:
                        cursor = conn.cursor()
                        cursor.execute("BEGIN IMMEDIATE")
                        cls._update_daily_summary(cursor, now_date, user_latest_stats, now_date, update_timestamp)
                        cls._update_daily_summary(cursor, now_date, user_latest_stats, now_date, update_timestamp)
                        cls._insert_snapshot_index(cursor, now_date, latest_ship_count, latest_ship_map)
                        if len(latest_ship_cache['insert']) > 0:
                            cls._insert_latest_cache_many(cursor, latest_ship_cache['insert'])
                        if len(latest_ship_cache['update']) > 0:
                            cls._update_latest_cache_many(cursor, latest_ship_cache['update'])
                        if len(latest_shapshot['insert']) > 0:
                            cls._insert_daily_snapshot_many(cursor, latest_shapshot['insert'])
                        if len(latest_shapshot['update']) > 0:
                            cls._update_daily_snapshot_many(cursor, latest_shapshot['update'])
                        cursor.execute("COMMIT")
                    except Exception:
                        cursor.execute("ROLLBACK")
                        logger.error(traceback.format_exc())
                logger.debug(f'{account_id} | Success / Changed (2008)')


