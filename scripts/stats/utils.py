import time
import json
from pymysql import Connection
from pymysql.cursors import Cursor
from datetime import datetime, timezone

from logger import logger
from settings import (
    DATA_DIR,
    BATCH_SIZE
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def read_version() -> str:
    file_path = DATA_DIR / f"json/game_version.json"
    with open(file_path, "r", encoding="utf-8") as f:
        version_data = json.load(f)
        return version_data['short']

def analyze_db_files():
    db_files_dir = DATA_DIR / 'db'
    db_files = list(db_files_dir.rglob("*.db"))  # 递归查找
    file_count = len(db_files)
    total_size = 0
    for f in db_files:
        try:
            total_size += f.stat().st_size
        except Exception:
            continue
    avg_size = total_size / file_count if file_count > 0 else 0
    result = {
        "update__time": int(datetime.now().timestamp()),
        "file_count": file_count,
        "total_size_bytes": total_size,
        "avg_size_bytes": int(avg_size)
    }
    output_file = DATA_DIR / "json/db_stats.json"
    with output_file.open("w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    return f'Files: {file_count}  Size: {round(total_size / 1024 / 1024, 2)}mb  Avg: {round(avg_size / 1024 / 1024, 2)}mb'

def process_region_stats(mysql_connection: Connection, game_version: str):
    now_date = now_iso()
    mysql_connection.begin()
    cursor: Cursor = mysql_connection.cursor()
    try:
        sql = """
            SELECT 
                MAX(id) 
            FROM T_user_pvp;
        """
        cursor.execute(sql)
        max_id_result = cursor.fetchone()
        max_id = max_id_result[0]
        logger.info(f'Max id in table user_cache: {max_id}')
        sql = """
            SELECT 
                ship_id 
            FROM T_ship_base
            WHERE is_enabled = 1;
        """
        cursor.execute(sql)
        rows = cursor.fetchall()
        ship_ids = [str(row[0]) for row in rows]
        server_avg_by_battles = {}
        server_avg_by_users = {}
        for offset in range(0, max_id, BATCH_SIZE):
            if offset % BATCH_SIZE == 0:
                logger.info(f'[{offset+1}/{max_id}] Processing~')
            sql = """
                SELECT 
                    ship_cache 
                FROM T_user_pvp 
                WHERE id BETWEEN %s AND %s;
            """
            cursor.execute(sql, [offset+1, offset+BATCH_SIZE])
            rows = cursor.fetchall()
            for row in rows:
                if row is None or row[0] is None:
                    continue
                pvp_cache: dict = json.loads(row[0])
                for ship_id, stats in pvp_cache.items():
                    if str(ship_id) not in ship_ids:
                        continue
                    if ship_id not in server_avg_by_battles:
                        server_avg_by_battles[ship_id] = [0] * 8
                        server_avg_by_users[ship_id] = [0] * 9
                    # 统计场次平均数据
                    target_list = server_avg_by_battles[ship_id]
                    for i in range(8):
                        target_list[i] += stats[i]
                    # 统计用户平均数据
                    if stats[0] >= 10:
                        target_list = server_avg_by_users[ship_id]
                        target_list[0] += 1         # users
                        target_list[1] += stats[0]
                        for i in range(1, 8):
                            target_list[i+1] += stats[i]/stats[0]
        now_ts = int(time.time())
        # 统计场次平均数据
        insert_values = []
        for ship_id, ship_data in server_avg_by_battles.items():
            if ship_id not in ship_ids:
                continue
            if ship_data[0] != 0:
                insert_values.append([
                    ship_id,
                    ship_data[0],
                    round(ship_data[1]/ship_data[0]*100,2),
                    round(ship_data[2]/ship_data[0],2),
                    round(ship_data[3]/ship_data[0],2),
                    round(ship_data[4]/ship_data[0],2),
                    round(ship_data[5]/ship_data[0]*100,2),
                    int(ship_data[6]/ship_data[0]*100),
                    int(ship_data[7]/ship_data[0]*1000),
                    now_ts
                ])
        sql = """
            UPDATE T_ship_stats_by_battles 
            SET
                battles = %s,
                win_rate = %s,
                avg_damage = %s,
                avg_frags = %s,
                avg_exp = %s,
                survived_rate = %s,
                avg_scouting_damage = %s,
                avg_potential_damage = %s,
                updated_at = FROM_UNIXTIME(%s)
            WHERE ship_id = %s;
        """
        cursor.executemany(sql, [
            insert_value[1:] + [insert_value[0]] for insert_value in insert_values
        ])
        sql = """
            SELECT 
                ship_id 
            FROM T_ship_stats_by_battles_archive 
            WHERE stat_date = %s;
        """
        cursor.execute(sql, now_date[:10])
        exists_ship_id = [str(row[0]) for row in cursor.fetchall()]
        update_data = []
        insert_data = []
        for row in insert_values:
            ship_id = row[0]
            if str(ship_id) in exists_ship_id:
                update_data.append([
                    game_version,
                    row[1],  # battles
                    row[2],  # win_rate
                    row[3],  # avg_damage
                    row[4],  # avg_frags
                    row[5],  # avg_exp
                    row[6],  # survived_rate
                    row[7],  # avg_scouting_damage
                    row[8],  # avg_potential_damage
                    ship_id,
                    now_date[:10]
                ])
            else:
                insert_data.append([
                    ship_id,
                    now_date[:10],
                    game_version,
                    row[1],  # battles
                    row[2],  # win_rate
                    row[3],  # avg_damage
                    row[4],  # avg_frags
                    row[5],  # avg_exp
                    row[6],  # survived_rate
                    row[7],  # avg_scouting_damage
                    row[8]   # avg_potential_damage
                ])
        if update_data != {}:
            sql = """
                UPDATE T_ship_stats_by_battles_archive
                SET 
                    game_version = %s,
                    battles = %s,
                    win_rate = %s,
                    avg_damage = %s,
                    avg_frags = %s,
                    avg_exp = %s,
                    survived_rate = %s,
                    avg_scouting_damage = %s,
                    avg_potential_damage = %s
                WHERE ship_id = %s 
                    AND stat_date = %s;
            """
            cursor.executemany(sql, update_data)
        if insert_data != {}:
            sql = """
            INSERT INTO T_ship_stats_by_battles_archive (
                ship_id,
                stat_date,
                game_version,
                battles,
                win_rate,
                avg_damage,
                avg_frags,
                avg_exp,
                survived_rate,
                avg_scouting_damage,
                avg_potential_damage
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            );
            """
            cursor.executemany(sql, insert_data)
        logger.info("Archived: T_ship_stats_by_battles")
        # 统计用户平均数据
        insert_values = []
        for ship_id, ship_data in server_avg_by_users.items():
            if ship_id not in ship_ids:
                continue
            if ship_data[0] != 0:
                insert_values.append([
                    ship_id,
                    ship_data[0],
                    ship_data[1],
                    round(ship_data[2]/ship_data[0]*100,2),
                    round(ship_data[3]/ship_data[0],2),
                    round(ship_data[4]/ship_data[0],2),
                    round(ship_data[5]/ship_data[0],2),
                    round(ship_data[6]/ship_data[0]*100,2),
                    int(ship_data[7]/ship_data[0]*100),
                    int(ship_data[8]/ship_data[0]*1000),
                    now_ts
                ])
        sql = """
            UPDATE T_ship_stats_by_users 
            SET
                users = %s,
                battles = %s,
                win_rate = %s,
                avg_damage = %s,
                avg_frags = %s,
                avg_exp = %s,
                survived_rate = %s,
                avg_scouting_damage = %s,
                avg_potential_damage = %s,
                updated_at = FROM_UNIXTIME(%s)
            WHERE ship_id = %s;
        """
        cursor.executemany(sql, [
            insert_value[1:] + [insert_value[0]] for insert_value in insert_values
        ])
        sql = """
            SELECT 
                ship_id 
            FROM T_ship_stats_by_users_archive 
            WHERE stat_date = %s;
        """
        cursor.execute(sql, now_date[:10])
        exists_ship_id = [str(row[0]) for row in cursor.fetchall()]
        update_data = []
        insert_data = []
        for row in insert_values:
            ship_id = row[0]
            if str(ship_id) in exists_ship_id:
                update_data.append([
                    game_version,
                    row[1],  # users
                    row[2],  # battles
                    row[3],  # win_rate
                    row[4],  # avg_damage
                    row[5],  # avg_frags
                    row[6],  # avg_exp
                    row[7],  # survived_rate
                    row[8],  # avg_scouting_damage
                    row[9],  # avg_potential_damage
                    ship_id,
                    now_date[:10]
                ])
            else:
                insert_data.append([
                    ship_id,
                    now_date[:10],
                    game_version,
                    row[1],  # users
                    row[2],  # battles
                    row[3],  # win_rate
                    row[4],  # avg_damage
                    row[5],  # avg_frags
                    row[6],  # avg_exp
                    row[7],  # survived_rate
                    row[8],  # avg_scouting_damage
                    row[9]   # avg_potential_damage
                ])
        if update_data != {}:
            sql = """
                UPDATE T_ship_stats_by_users_archive
                SET 
                    game_version = %s,
                    users = %s,
                    battles = %s,
                    win_rate = %s,
                    avg_damage = %s,
                    avg_frags = %s,
                    avg_exp = %s,
                    survived_rate = %s,
                    avg_scouting_damage = %s,
                    avg_potential_damage = %s
                WHERE ship_id = %s 
                    AND stat_date = %s;
            """
            cursor.executemany(sql, update_data)
        if insert_data != {}:
            sql = """
            INSERT INTO T_ship_stats_by_users_archive (
                ship_id,
                stat_date,
                game_version,
                users,
                battles,
                win_rate,
                avg_damage,
                avg_frags,
                avg_exp,
                survived_rate,
                avg_scouting_damage,
                avg_potential_damage
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            );
            """
            cursor.executemany(sql, insert_data)
        logger.info("Archived: T_ship_stats_by_users")

        mysql_connection.commit()
    finally:
        cursor.close()
    