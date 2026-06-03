import sqlite3
import traceback
from sqlite3 import Cursor
from typing import Optional
from pathlib import Path
from typing_extensions import TypedDict

from logger import logger
from exception import write_exception
from utils import get_reset_date
from settings import SQLITE_DIR, CREATE_SQL

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

class UserUpdater:
    def _init_new_database(account_id: int, db_path: Path, current_timestamp: int):
        try:
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()

                # 初始化数据库
                cursor.executescript(CREATE_SQL)

                # 插入空数据
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
                conn.commit()

                # 需要更新，此时用户的daily summary表插入了两条updated_at为NULL的数据
                logger.debug(f'{account_id} | Updated - New user')
                return True
        except Exception as e:
            error_name = type(e).__name__
            logger.error(f'{account_id} | SQLite3 initialization error')
            write_exception(
                error_type="DatabaseError",
                error_name=error_name,
                error_info=traceback.format_exc()
            )

            # 删除初始化不完成的异常数据库文件
            if 'conn' in locals():
                conn.close()
            if db_path.exists():
                db_path.unlink(missing_ok=True)
                logger.warning(f"Corrupted database file deleted: {db_path}")
            # 初始化文件失败，不进行后续的更新操作
            logger.debug(f'{account_id} | Skipped - Error (1001)')
            return False
        
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
    
    @classmethod
    def main(
        cls,
        account_id: int, 
        current_timestamp: int,
        user_latest_stats: Optional[UserStats],
        user_update_time: Optional[int]
    ) -> bool:
        db_path = SQLITE_DIR / f'{account_id}.db'
        
        # 用户数据库文件不存在，执行初始化数据库文件
        if not db_path.exists():
            return cls._init_new_database(account_id, db_path, current_timestamp)
        
        # 获取当日日期
        now_date = get_reset_date(current_timestamp)
        
        try:
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()

                # 先从数据库中检测数据库是否存在now_date的daily summary的数据
                now_date_summary = cls._read_base_daily_summary(cursor, now_date)

                # 有今日数据
                if now_date_summary:
                    # 最新daily summary的updated_at为NULL
                    # 可能是用户上个更新失败或者本地测试才可能出现的情况
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
                        if now_date_summary[0] and get_reset_date(now_date_summary[4]) != now_date:
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
        except Exception as e:
            conn.rollback()
            error_name = type(e).__name__
            logger.error(f'{account_id} | Database operation error')
            write_exception(
                error_type="DatabaseError",
                error_name=error_name,
                error_info=traceback.format_exc()
            )
            return False

class UserRecentUpdater:
    def _ship_snapshot_encode(data: list):
        parts = []
        for item in data:
            if item is None:
                parts.append('')
            else:
                parts.append(str(item).replace(' ', ''))
        return ';'.join(parts)
    
    def _ship_snapshot_decode(data: str):
        fields = data.split(';')
        result = []
        for f in fields:
            if f == '':
                result.append(None)
            else:
                result.append(eval(f))
        return result

    def _ship_map_encode(data: dict):
        parts = []
        for key, value in data.items():
            parts.append(str(key) + ':' + str(value))
        return ','.join(parts)

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

    def _calc_recent_diff(ship_id: int, new_list: list, old_list: list) -> list:
        modes = ['pvp_solo', 'pvp_div2', 'pvp_div3', 'rank_solo']
        params = []

        for idx, mode in enumerate(modes):
            new_data = new_list[idx]
            old_data = old_list[idx]

            # 只有两者都存在时才计算差值
            if new_data is None:
                continue

            if old_data is None:
                old_data = [0] * 12

            # 计算各字段差值（新 - 旧）
            delta_battles = new_data[0] - old_data[0]
            if delta_battles <= 0 or delta_battles >= 3:
                continue

            delta_wins = new_data[1] - old_data[1]
            delta_losses = new_data[2] - old_data[2]
            delta_damage = new_data[3] - old_data[3]
            delta_frags = new_data[4] - old_data[4]
            delta_original_exp = new_data[8] - old_data[8]
            delta_scouting_damage = new_data[6] - old_data[6]
            delta_art_agro = new_data[7] - old_data[7]
            delta_planes_killed = new_data[9] - old_data[9]
            delta_survived = new_data[5] - old_data[5]

            delta_hits = new_data[10] - old_data[10]
            delta_shots = new_data[11] - old_data[11]
            hit_rate = round(delta_hits / delta_shots * 100, 2) if delta_shots != 0 else 0.0

            params.append((
                ship_id, mode,
                delta_battles, delta_wins, delta_losses, delta_damage,
                delta_frags, delta_original_exp, delta_scouting_damage,
                delta_art_agro, delta_planes_killed, delta_survived, hit_rate
            ))

        return params

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

    def _read_daily_snapshot(cursor: Cursor, ship_id: int, snapshot_date: int):
        sql = """
            SELECT snapshot_data 
            FROM ship_daily_snapshot 
            WHERE ship_id = ? 
              AND snapshot_date = ?;
        """
        cursor.execute(sql, [ship_id, snapshot_date])
        return cursor.fetchone()

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

    def _refresh_snapshot_index(cursor: Cursor, existing: bool, snapshot_date: int, ship_count: int, ship_map: dict):
        if existing:
            sql = """
                UPDATE daily_snapshot_index 
                SET 
                    ship_count = ?, 
                    ship_map = ?
                WHERE snapshot_date = ?;
            """
            cursor.execute(sql, [ship_count, ship_map, snapshot_date])
        else:
            sql = """
                INSERT INTO daily_snapshot_index (
                    snapshot_date, ship_count, ship_map
                ) VALUES (
                    ?,?,?
                );
            """
            cursor.execute(sql, [snapshot_date, ship_count, ship_map])

    def _refresh_latest_cache(cursor: Cursor, params: dict):
        if len(params['insert']) > 0:
            sql = """
                INSERT INTO ship_latest_cache (
                    ship_id, battles, snapshot_date
                ) VALUES (
                    ?,?,?
                );
            """
            cursor.executemany(sql, params['insert'])
        
        if len(params['update']) > 0:
            sql = """
                UPDATE ship_latest_cache 
                SET 
                    battles = ?, 
                    snapshot_date = ?, 
                    updated_at = CURRENT_TIMESTAMP 
                WHERE ship_id = ?;
            """
            cursor.executemany(sql, params['update'])

    def _refresh_daily_snapshot(cursor: Cursor, params: dict):
        if len(params['insert']) > 0:
            sql = """
                INSERT INTO ship_daily_snapshot (
                    ship_id, snapshot_date, snapshot_data
                ) VALUES (
                    ?,?,?
                );
            """
            cursor.executemany(sql, params['insert'])
        
        if len(params['update']) > 0:
            sql = """
                UPDATE ship_daily_snapshot 
                SET 
                    snapshot_data = ?, 
                    updated_at = CURRENT_TIMESTAMP 
                WHERE ship_id = ? 
                    AND snapshot_date = ?;
            """
            cursor.executemany(sql, params['update'])

    def _insert_user_recent_stats(cursor: Cursor, rows: list):
        if len(rows) > 0:
            sql = """
                INSERT INTO user_recent_stats (
                    ship_id, mode, battles, wins, losses, damage, frags,
                    original_exp, scouting_damage, art_agro, planes_killed,
                    survived, hit_rate
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """
            cursor.executemany(sql, rows)

    @classmethod
    async def main(
        cls, 
        account_id: int,
        user_level: int,
        user_limit: int,
        responses: list,
        current_timestamp: int,
        update_timestamp: int
    ) -> str:
        basic_data = responses[0].get(str(account_id))

        # 如果非隐藏战绩则刷新数据
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
                try:
                    cursor = conn.cursor()
                    cursor.execute("BEGIN IMMEDIATE")
                    # 读取当前日期下的update_at值
                    now_date_summary = cls._read_base_daily_summary(cursor, now_date)
                    # update_at值为空则更新两行
                    if now_date_summary[4] is None:
                        yesterday = get_reset_date(current_timestamp - 86400)
                        cls._update_daily_summary(cursor, yesterday, user_latest_stats, None, update_timestamp)
                        cls._update_daily_summary(cursor, now_date, user_latest_stats, None, update_timestamp)
                    else:
                        cls._update_daily_summary(cursor, now_date, user_latest_stats, None, update_timestamp)
                    cursor.execute("COMMIT")

                    logger.debug(f'{account_id} | No data / Hidden (2003)')
                except Exception as e:
                    cursor.execute("ROLLBACK")
                    error_name = type(e).__name__
                    logger.error(f'{account_id} | Database operation error: {error_name}')
                    write_exception(
                        error_type="DatabaseError",
                        error_name=error_name,
                        error_info=traceback.format_exc()
                    )
                finally:
                    cursor.close()

                return 

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
            
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            # 本地数据库中船只的缓存数据
            local_date_summary = cls._read_base_daily_summary(cursor, now_date)
            local_dict = cls._read_latest_cache(cursor)
            
            # 处理船只数据
            latest_dict = cls._process_responeses([
                responses[1][str(account_id)]['statistics'],
                responses[2][str(account_id)]['statistics'],
                responses[3][str(account_id)]['statistics'],
                responses[4][str(account_id)]['statistics']
            ])
            
            # 新用户，没有本地数据和updated_at数据
            if local_date_summary[4] is None and local_dict == {}:
                yesterday = get_reset_date(current_timestamp-86400)
                for ship_id, ship_data in latest_dict.items():
                    latest_ship_cache['insert'].append([
                        ship_id, ship_data['battles'], yesterday
                    ])
                    latest_shapshot['insert'].append([
                        ship_id, yesterday, cls._ship_snapshot_encode(ship_data['values'])
                    ])
                    latest_ship_count += 1
                    latest_ship_map[ship_id] = yesterday

                with sqlite3.connect(db_path) as conn:
                    cursor = conn.cursor()
                    try:
                        cursor.execute("BEGIN IMMEDIATE")
                        cls._update_daily_summary(cursor, yesterday, user_latest_stats, yesterday, update_timestamp)
                        cls._update_daily_summary(cursor, now_date, user_latest_stats, yesterday, update_timestamp)
                        cls._refresh_snapshot_index(cursor, False, yesterday, latest_ship_count, cls._ship_map_encode(latest_ship_map))
                        cls._refresh_latest_cache(cursor, latest_ship_cache)
                        cls._refresh_daily_snapshot(cursor, latest_shapshot)
                        cursor.execute("COMMIT")
                        
                        logger.debug(f'{account_id} | New user (2004)')

                    except Exception as e:
                        cursor.execute("ROLLBACK")
                        error_name = type(e).__name__
                        logger.error(f'{account_id} | Database operation error: {error_name}')
                        write_exception(
                            error_type="DatabaseError",
                            error_name=error_name,
                            error_info=traceback.format_exc()
                        )
                    finally:
                        cursor.close()

                    return

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
                            ship_id, yesterday, cls._ship_snapshot_encode(ship_data['values'])
                        ])
                        latest_ship_count += 1
                        latest_ship_map[ship_id] = yesterday
                    elif ship_data['battles'] != local_dict[ship_id][0]:
                        changed_rows += 1
                        latest_ship_cache['insert'].append([
                            int(ship_id), ship_data['battles'], yesterday
                        ])
                        latest_shapshot['insert'].append([
                            ship_id, yesterday, cls._ship_snapshot_encode(ship_data['values'])
                        ])
                        latest_ship_count += 1
                        latest_ship_map[ship_id] = now_date
                    else:
                        # 本地数据和最新数据间没有修改
                        latest_ship_count += 1
                        latest_ship_map[ship_id] = local_dict[ship_id][1]
                
                # 没有数据改变
                if changed_rows == 0:
                    try:
                        cursor.execute("BEGIN IMMEDIATE")
                        cls._update_daily_summary(cursor, yesterday, user_latest_stats, yesterday, update_timestamp)
                        cls._update_daily_summary(cursor, now_date, user_latest_stats, yesterday, update_timestamp)
                        cls._refresh_snapshot_index(cursor, False, yesterday, latest_ship_count, cls._ship_map_encode(latest_ship_map))
                        cursor.execute("COMMIT")

                        logger.debug(f'{account_id} | Fix database / No changed (2005)')
                    except Exception as e:
                        cursor.execute("ROLLBACK")
                        error_name = type(e).__name__
                        logger.error(f'{account_id} | Database operation error: {error_name}')
                        write_exception(
                            error_type="DatabaseError",
                            error_name=error_name,
                            error_info=traceback.format_exc()
                        )
                    finally:
                        cursor.close()
                        
                    return 
                
                # 有数据改变
                try:
                    cursor.execute("BEGIN IMMEDIATE")
                    cls._update_daily_summary(cursor, yesterday, user_latest_stats, yesterday, update_timestamp)
                    cls._update_daily_summary(cursor, now_date, user_latest_stats, yesterday, update_timestamp)
                    cls._refresh_snapshot_index(cursor, False, yesterday, latest_ship_count, cls._ship_map_encode(latest_ship_map))
                    cls._refresh_latest_cache(cursor, latest_ship_cache)
                    cls._refresh_daily_snapshot(cursor, latest_shapshot)
                    cursor.execute("COMMIT")
                except Exception as e:
                    cursor.execute("ROLLBACK")
                    error_name = type(e).__name__
                    logger.error(f'{account_id} | Database operation error: {error_name}')
                    write_exception(
                        error_type="DatabaseError",
                        error_name=error_name,
                        error_info=traceback.format_exc()
                    )
                    return 
                logger.debug(f'{account_id} | Fix database / Changed (2006)')
                return
            
            # 正常用户
            changed_rows = 0
            changed_list = {}
            insert_recent_list = []

            if (
                user_level == 2 and 
                current_timestamp - local_date_summary[4] <= 7200
            ):
                is_pro = True
            else:
                is_pro = False

            for ship_id, ship_data in latest_dict.items():
                if ship_id not in local_dict:
                    changed_rows += 1
                    latest_ship_cache['insert'].append([
                        ship_id, ship_data['battles'], now_date
                    ])
                    latest_shapshot['insert'].append([
                        ship_id, now_date, cls._ship_snapshot_encode(ship_data['values'])
                    ])

                    # 处理pro权限用户
                    if is_pro:
                        changed_list[ship_id] = [ship_data['values'], [None]*4]

                    latest_ship_count += 1
                    latest_ship_map[ship_id] = now_date
                elif ship_data['battles'] != local_dict[ship_id][0]:
                    changed_rows += 1
                    latest_ship_cache['update'].append([
                        ship_data['battles'], now_date, int(ship_id)
                    ])
                    if local_dict[ship_id][1] == now_date:
                        latest_shapshot['update'].append([
                            now_date, cls._ship_snapshot_encode(ship_data['values']), ship_id
                        ])
                    else:
                        latest_shapshot['insert'].append([
                            ship_id, now_date, cls._ship_snapshot_encode(ship_data['values'])
                        ])
                        
                    # 处理pro权限用户
                    if is_pro and ship_data['battles'] > local_dict[ship_id][0]:
                        local_snapshot = cls._read_daily_snapshot(cursor, ship_id, local_dict[ship_id][1])
                        if local_snapshot:
                            local_snapshot = cls._ship_snapshot_decode(local_snapshot[0])
                            changed_list[ship_id] = [ship_data['values'], local_snapshot]

                    latest_ship_count += 1
                    latest_ship_map[ship_id] = now_date
                else:
                    # 本地数据和最新数据间没有修改
                    latest_ship_count += 1
                    latest_ship_map[ship_id] = local_dict[ship_id][1]
        
            if changed_list != {}:
                for ship_id, ship_data in changed_list.items():
                    diff_params = cls._calc_recent_diff(ship_id, ship_data[0], ship_data[1])
                    insert_recent_list = diff_params

            try:
                cursor.execute("BEGIN IMMEDIATE")
                cls._update_daily_summary(cursor, now_date, user_latest_stats, now_date, update_timestamp)
                cls._refresh_snapshot_index(cursor, local_date_summary[3] == str(now_date), now_date, latest_ship_count, cls._ship_map_encode(latest_ship_map))
                cls._refresh_latest_cache(cursor, latest_ship_cache)
                cls._refresh_daily_snapshot(cursor, latest_shapshot)
                cls._insert_user_recent_stats(cursor, insert_recent_list)
                cursor.execute("COMMIT")
            except Exception as e:
                cursor.execute("ROLLBACK")
                error_name = type(e).__name__
                logger.error(f'{account_id} | Database operation error: {error_name}')
                write_exception(
                    error_type="DatabaseError",
                    error_name=error_name,
                    error_info=traceback.format_exc()
                )

        if changed_rows == 0:
            logger.debug(f'{account_id} | Success / No changed (2007)')
        else:
            logger.debug(f'{account_id} | Success / Changed (2008)')