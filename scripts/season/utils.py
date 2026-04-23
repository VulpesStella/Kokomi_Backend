import json
import requests
import traceback
from redis import Redis
from pymysql import Connection
from pymysql.cursors import Cursor
from datetime import datetime, timezone, time

from logger import logger
from settings import (
    DATA_DIR, REGION, CLAN_BATTLE_WINDOWS, CLAN_API, CLAN_INIT_TABLE_LIST
)


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")

def fetch_data(url):
    try:
        resp = requests.get(url,timeout=5)
        if resp.status_code == 200:
            # logger.debug(f'200 {url}')
            result = resp.json()
            return result
        # logger.warning(f'Code_{resp.status_code} {url}')
        return f'HTTP_STATUS_{resp.status_code}'
    except Exception as e:
        # logger.warning(f"{type(e).__name__} {url}")
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

def read_season_data():
    file_path = DATA_DIR / f'json/clan_season.json'
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        return data

def formtime2timestamp(formtime: str):
    return int(datetime.fromisoformat(formtime).timestamp())

def is_cb_active(now_ts: int, SEASON_START: int, SEASON_FINISH: int) -> bool:
    if not (SEASON_START <= now_ts <= SEASON_FINISH):
        return False
    now = datetime.fromtimestamp(now_ts, tz=timezone.utc)
    weekday = now.weekday()
    current_time = now.time()
    for start, end, regions in CLAN_BATTLE_WINDOWS[weekday]:
        if time(start[0], start[1]) <= current_time < time(end[0], end[1] + 29):
            if REGION in regions:
                return True
    return False

def format_clan_data(data: list):
    if data != []:
        return {
            'battles_count': data[0], 
            'wins_count': data[1], 
            'public_rating': data[2], 
            'league': data[3], 
            'division': data[4], 
            'division_rating': data[5], 
            'stage_type': data[6], 
            'stage_progress': data[7]
        }
    else:
        return None

def get_clan_rank_data(redis_client: Redis, realm: str, league: int, division: int):
    clan_data_list = []
    url = f'{CLAN_API}/api/ladder/structure/?realm={realm}&league={league}&division={division}&limit=1000'
    result = fetch_data(url)
    error = verify_responses(redis_client, [result])
    if error != None:
        return error
    for temp_data in result:
        clan_data_list.append([
            temp_data['id'],
            temp_data['tag'],
            league,
            formtime2timestamp(temp_data['last_battle_at'])
        ])
    return clan_data_list

def ensure_clan_battle_table(conn: Connection, season_id: int):
    conn.begin()
    cursor: Cursor = conn.cursor()
    try:
        table_name = f"T_clan_battle_s{season_id}"
        sql = f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            -- 相关id
            id               INT          AUTO_INCREMENT,
            -- 对局相关信息和ID
            battle_time      TIMESTAMP    NOT NULL,     -- 战斗时间
            clan_id          BIGINT       NOT NULL,     -- 10位的非连续数字
            team_number      TINYINT      NOT NULL,     -- 队伍id
            -- 对局结果
            battle_result    BOOLEAN      NOT NULL,     -- 对局结果 胜利或者失败
            battle_rating    VARCHAR(5)  DEFAULT NULL, -- 对局分数 如果是晋级赛则会显示为0
            battle_stage     VARCHAR(5)  DEFAULT NULL, -- 对局结果 仅对于stage有效
            -- 对局结算的数据
            league           TINYINT      DEFAULT NULL, -- 段位 0紫金 1白金 2黄金 3白银 4青铜
            division         TINYINT      DEFAULT NULL, -- 分段 1 2 3
            division_rating  INT          DEFAULT NULL, -- 分段分数，示例：白金 1段 25分
            public_rating    INT          DEFAULT NULL, -- 工会评分 1199 - 3000
            stage_type       TINYINT      DEFAULT NULL, -- 晋级赛/保级赛 默认为Null
            stage_progress   VARCHAR(5)   DEFAULT NULL, -- 晋级赛/保级赛的当前结果
            -- 记录数据创建的时间和更新时间
            created_at       TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
            -- 因为数据不会更新，所以不需要updated_at，只需要created_at

            PRIMARY KEY (id), -- 主键

            INDEX idx_time (battle_time), -- 索引

            INDEX idx_cid (clan_id) -- 索引
        );
        """
        cursor.execute(sql)
        conn.commit()
    except Exception:
        conn.rollback()
        logger.error(f"{traceback.format_exc()}")
    finally:
        cursor.close()

def get_update_ids(conn: Connection, SEASON_ID: int, clan_data_list: list):
    update_ids = []
    conn.begin()
    cursor: Cursor = conn.cursor()
    try:
        for clan_data in clan_data_list:
            clan_id = clan_data[0]
            sql = """
                SELECT 
                    clan_id, 
                    season, 
                    UNIX_TIMESTAMP(last_battle_at) 
                FROM T_clan_stats 
                WHERE clan_id = %s;
            """
            cursor.execute(sql, [clan_data[0]])
            clan = cursor.fetchone()
            if clan is None:
                sql = """
                    INSERT INTO T_clan_base (clan_id, tag) VALUES (%s, %s);
                """
                cursor.execute(sql, [clan_id,clan_data[1]])
                for table_name in CLAN_INIT_TABLE_LIST:
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
                        table_count = %s 
                    WHERE clan_id = %s;
                """
                cursor.execute(sql, [len(CLAN_INIT_TABLE_LIST),clan_id])
                update_ids.append(clan_id)
            else:
                if clan_data[3] is None:
                    continue
                if (
                    clan[2] is None or 
                    clan[2] != clan_data[3] or 
                    clan[1] != SEASON_ID
                ):
                    update_ids.append(clan_id)
        conn.commit()
    except Exception:
        conn.rollback()
        logger.error((f"{traceback.format_exc()}"))
    finally:
        cursor.close()
    return update_ids

def regresh_clan_league(conn: Connection, clan_data_list: list):
    refresh_count = 0
    conn.begin()
    cursor: Cursor = conn.cursor()
    try:
        for clan_data in clan_data_list:
            sql = """
                UPDATE T_clan_base 
                SET 
                    tag = %s, 
                    league = %s,
                    updated_at = CURRENT_TIMESTAMP 
                WHERE clan_id = %s;
            """
            cursor.execute(sql, [clan_data[1], clan_data[2], clan_data[0]])
            refresh_count += 1
        conn.commit()
    except Exception:
        conn.rollback()
        logger.error((f"{traceback.format_exc()}"))
    finally:
        cursor.close()
    return refresh_count

def update_clan_season(redis_client: Redis, conn: Connection, SEASON_ID: int, clan_id: int):
    url = f'{CLAN_API}/api/clanbase/{clan_id}/claninfo/'
    result = fetch_data(url)
    error = verify_responses(redis_client, [result])
    if error != None:
        return error
    if REGION == 'ru':
        ladder_name = 'mk_ladder'
    else:
        ladder_name = 'wows_ladder'
    leading_team_number = result['clanview'][ladder_name]['leading_team_number']
    last_battle_at = result['clanview'][ladder_name]['last_battle_at']
    clan_result = {
        'clan_id': clan_id,
        'leading_team_number': leading_team_number,
        'battles_count': result['clanview'][ladder_name]['battles_count'],
        'wins_count': result['clanview'][ladder_name]['wins_count'],
        'public_rating': result['clanview'][ladder_name]['public_rating'], 
        'league': result['clanview'][ladder_name]['league'], 
        'division': result['clanview'][ladder_name]['division'], 
        'division_rating': result['clanview'][ladder_name]['division_rating'], 
        'longest_winning_streak': result['clanview'][ladder_name]['longest_winning_streak'],
        'stage_type': None,
        'stage_battles': 0,
        'stage_victories': 0,
        'stage_progress': None,
        'last_battle_time': formtime2timestamp(last_battle_at),
        'team_data': {
            1: [],
            2: []
        }
    }
    for team_data in result['clanview'][ladder_name]['ratings']:
        if team_data['season_number'] != SEASON_ID:
            continue
        team_number = team_data['team_number']
        team_result = [
            team_data['battles_count'],
            team_data['wins_count'],
            team_data['public_rating'],
            team_data['league'],
            team_data['division'],
            team_data['division_rating'],
            None,
            None
        ]
        if team_data['stage']:
            if team_data['stage']['type'] == 'promotion':
                team_result[6] = 1
            else:
                team_result[6] = 2
            stage_battles = 0
            stage_victories = 0
            stage_progress = ''
            for progress in team_data['stage']['progress']:
                stage_battles += 1
                if progress == 'victory':
                    stage_victories += 1
                    stage_progress += '★'
                else:
                    stage_progress += '☆'
            team_result[7] = stage_progress
            if team_number == leading_team_number:
                clan_result['stage_type'] = team_result[6]
                clan_result['stage_battles'] = stage_battles
                clan_result['stage_victories'] = stage_victories
                clan_result['stage_progress'] = stage_progress
        if team_result[0] > 0:
            clan_result['team_data'][team_number] = team_result
    cursor: Cursor = conn.cursor()
    try:
        result = None
        last_battle_time = clan_result['last_battle_time']
        team_data_1 = clan_result['team_data'][1]
        team_data_2 = clan_result['team_data'][2]
        sql = """
            SELECT 
                season, 
                team_data 
            FROM T_clan_stats 
            WHERE clan_id = %s;
        """
        cursor.execute(sql, [clan_id])
        clan = cursor.fetchone()
        insert_data_list = []
        if clan and clan[0] == SEASON_ID:
            original_team_data = json.loads(clan[1]) 
            old_team_data = {
                1: format_clan_data(original_team_data[0]),
                2: format_clan_data(original_team_data[1])
            }
            new_team_data = {
                1: format_clan_data(team_data_1),
                2: format_clan_data(team_data_2)
            }
            for team_number in [1, 2]:
                if new_team_data[team_number] == None:
                    continue
                if old_team_data[team_number]:
                    battles = new_team_data[team_number]['battles_count'] - old_team_data[team_number]['battles_count']
                    wins = new_team_data[team_number]['wins_count'] - old_team_data[team_number]['wins_count']
                    if battles > 1 or battles <= 0:
                        continue
                    battle_time = last_battle_time
                    if battles == 1:
                        temp_list = None
                        temp_list = [battle_time, clan_id, team_number]
                        if wins == 1:
                            temp_list.append(1)
                        else:
                            temp_list.append(0)
                        battle_rating = new_team_data[team_number]['public_rating'] - old_team_data[team_number]['public_rating']
                        if battle_rating > 0:
                            temp_list.append('+'+str(battle_rating))
                        elif battle_rating < 0:
                            temp_list.append(str(battle_rating))
                        else:
                            temp_list.append(None)
                        if (
                            new_team_data[team_number]['stage_type'] and 
                            new_team_data[team_number]['stage_progress'] != None and 
                            new_team_data[team_number]['stage_progress'] != ''
                        ):
                            stage_progress = new_team_data[team_number]['stage_progress']
                            temp_list.append('+' + stage_progress[-1])
                        else:
                            temp_list.append(None)
                        temp_list += [
                            new_team_data[team_number]['league'],
                            new_team_data[team_number]['division'],
                            new_team_data[team_number]['division_rating'],
                            new_team_data[team_number]['public_rating'],
                            new_team_data[team_number]['stage_type'],
                            new_team_data[team_number]['stage_progress']
                        ]
                        insert_data_list.append(temp_list)
                else:
                    battles = new_team_data[team_number]['battles_count']
                    wins = new_team_data[team_number]['wins_count']
                    if battles > 1 and battles <= 0:
                        continue
                    battle_time = last_battle_time
                    if battles == 1:
                        temp_list = None
                        temp_list = [battle_time, clan_id, team_number]
                        if wins == 1:
                            temp_list.append(1)
                        else:
                            temp_list.append(0)
                        temp_list += [
                            None, None,
                            new_team_data[team_number]['league'],
                            new_team_data[team_number]['division'],
                            new_team_data[team_number]['division_rating'],
                            new_team_data[team_number]['public_rating'],
                            new_team_data[team_number]['stage_type'],
                            str(new_team_data[team_number]['stage_progress']) if new_team_data[team_number]['stage_progress'] else None
                        ]
                        insert_data_list.append(temp_list)
        sql = """
            UPDATE T_clan_stats 
            SET 
                season = %s, 
                leading_team_number = %s,
                battles_count = %s, 
                wins_count = %s,
                public_rating = %s, 
                league = %s, 
                division = %s, 
                division_rating = %s, 
                longest_winning_streak = %s, 
                stage_type = %s,
                stage_battles = %s,
                stage_victories = %s,
                stage_progress = %s, 
                team_data = %s, 
                last_battle_at = FROM_UNIXTIME(%s)
            WHERE clan_id = %s;
        """
        cursor.execute(sql,[
            SEASON_ID,
            clan_result['leading_team_number'],
            clan_result['battles_count'],
            clan_result['wins_count'],
            clan_result['public_rating'],
            clan_result['league'],
            clan_result['division'],
            clan_result['division_rating'],
            clan_result['longest_winning_streak'],
            clan_result['stage_type'],
            clan_result['stage_battles'],
            clan_result['stage_victories'],
            clan_result['stage_progress'],
            json.dumps([team_data_1,team_data_2]),
            clan_result['last_battle_time'],
            clan_id
        ])
        for insert_data in insert_data_list:
            sql = f"""
                INSERT INTO T_clan_battle_s{SEASON_ID} (
                    battle_time, 
                    clan_id, 
                    team_number, 
                    battle_result, 
                    battle_rating, 
                    battle_stage, 
                    league, 
                    division, 
                    division_rating, 
                    public_rating, 
                    stage_type, 
                    stage_progress
                ) VALUES (
                    FROM_UNIXTIME(%s),%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s
                );
            """
            cursor.execute(sql, insert_data)
        conn.commit()
        return f'Success +{len(insert_data_list)}'
    except Exception as e:
        conn.rollback()
        logger.error((f"{traceback.format_exc()}"))
        return type(e).__name__
    finally:
        cursor.close()