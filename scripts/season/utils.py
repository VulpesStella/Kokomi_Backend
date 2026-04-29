import json
import logging
import requests
import traceback
from tqdm import tqdm
from redis import Redis
from pymysql import Connection
from pymysql.cursors import Cursor
from datetime import datetime, timezone, time
from typing import Any, Iterator, Optional, Union

from logger import logger
from settings import (
    REGION, 
    DATE_FMT,
    USE_TQDM,
    DATA_DIR, 
    CLAN_API, 
    CLAN_BATTLE_WINDOWS, 
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

def formtime_to_timestamp(formtime: str) -> int:
    """将 ISO 格式时间字符串转换为 Unix 时间戳"""
    return int(datetime.fromisoformat(formtime).timestamp())

def progress_iterable(
    items: list[Any], desc: str, logger_obj: logging.Logger
) -> Iterator[Any]:
    """遍历列表，根据 USE_TQDM 配置使用进度条或日志输出进度

    Args:
        items: 待遍历的列表
        desc: 进度描述文本
        logger_obj: 日志记录器

    Yields:
        列表中的每个元素
    """
    if USE_TQDM:
        tqdm_desc = f'{get_formatted_date()} [INFO] {desc}'
        with tqdm(items, desc=tqdm_desc, total=len(items)) as pbar:
            for item in pbar:
                pbar.set_postfix_str(str(item))
                yield item
    else:
        total = len(items)
        for idx, item in enumerate(items, 1):
            logger_obj.info('%s - [%d/%d] | Current: %s', desc, idx, total, item)
            yield item

def fetch_data(url: str) -> Union[dict, str]:
    """发送 GET 请求并解析 JSON 响应

    Args:
        url: 请求地址

    Returns:
        成功时返回解析后的 dict，失败时返回错误标识字符串（如 'HTTP_STATUS_404'）
    """
    try:
        resp = requests.get(url, timeout=5)
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

def read_season_data():
    """从本地 JSON 文件读取当前赛季配置数据"""
    # 俄服clan battle在s28后被rating战所替代
    # SEASON_ID, SEASON_FINISH, SEASON_START = 28, 1739944800, 1744005600
    file_path = DATA_DIR / f'json/clan_season.json'
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        return data

def is_cb_active(now_ts: int, season_start: int, season_finish: int) -> bool:
    """判断当前时间是否处于公会战活跃窗口内

    Args:
        now_ts: 当前 Unix 时间戳
        season_start: 赛季开始时间戳
        season_finish: 赛季结束时间戳

    Returns:
        是否在活跃窗口内
    """
    if not (season_start <= now_ts <= season_finish):
        return False

    now = datetime.fromtimestamp(now_ts, tz=timezone.utc)
    weekday = now.weekday()
    current_time = now.time()

    for start, end, regions in CLAN_BATTLE_WINDOWS[weekday]:
        if time(start[0], start[1]) <= current_time < time(end[0], end[1] + 29):
            if REGION in regions:
                return True
    return False

def format_clan_data(data: list) -> Optional[dict]:
    """将公会队伍数据库中的原始数据列表格式化为结构化字典

    Args:
        data: 原始数据列表，长度应为 8

    Returns:
        格式化后的字典，输入为空列表时返回 None
    """
    if not data:
        return None
    return {
        'battles_count': data[0],
        'wins_count': data[1],
        'public_rating': data[2],
        'league': data[3],
        'division': data[4],
        'division_rating': data[5],
        'stage_type': data[6],
        'stage_progress': data[7],
    }

def get_clan_rank_data(
    redis_client: Redis, 
    realm: str, 
    league: str, 
    division: str
) -> Optional[list]:
    """获取指定联赛和分段的公会排行榜数据

    Args:
        redis_client: Redis 客户端
        realm: 服务器区域
        league: 联赛等级
        division: 分段

    Returns:
        公会数据列表，每项为 [clan_id, tag, league, last_battle_timestamp]
        请求失败时返回 None。
    """
    clan_data_list = []
    try:
        url = (
            f'{CLAN_API}/api/ladder/structure/'
            f'?realm={realm}&league={league}&division={division}&limit=1000'
        )
        result = fetch_data(url)
        error = record_http_metrics(redis_client, [result])
        if error is not None:
            _log_warning(f'{error} {url}')
            return None
        for temp_data in result:
            clan_data_list.append([
                temp_data['id'],
                temp_data['tag'],
                league,
                formtime_to_timestamp(temp_data['last_battle_at'])
            ])
    except Exception:
        _log_error(traceback.format_exc())
        return None
    
    return clan_data_list

def ensure_clan_battle_table(conn: Connection, season_id: int) -> bool:
    """确保当前赛季的公会战数据表已创建

    Args:
        conn: 数据库连接
        season_id: 赛季 ID

    Returns:
        是否成功创建（或已存在）
    """
    is_created = False
    cursor: Cursor = conn.cursor()
    try:
        table_name = f'T_clan_battle_s{season_id}'
        sql = f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            id               INT          AUTO_INCREMENT,
            battle_time      TIMESTAMP    NOT NULL,
            clan_id          BIGINT       NOT NULL,
            team_number      TINYINT      NOT NULL,
            battle_result    BOOLEAN      NOT NULL,
            battle_rating    VARCHAR(5)  DEFAULT NULL,
            battle_stage     VARCHAR(5)  DEFAULT NULL,
            league           TINYINT      DEFAULT NULL,
            division         TINYINT      DEFAULT NULL,
            division_rating  INT          DEFAULT NULL,
            public_rating    INT          DEFAULT NULL,
            stage_type       TINYINT      DEFAULT NULL,
            stage_progress   VARCHAR(5)   DEFAULT NULL,
            created_at       TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (id),
            INDEX idx_time (battle_time),
            INDEX idx_cid (clan_id)
        );
        """
        cursor.execute(sql)
        conn.commit()
        is_created = True
    except Exception:
        conn.rollback()
        logger.error(traceback.format_exc())
    finally:
        cursor.close()
    return is_created

def get_update_ids(
    conn: Connection, season_id: int, clan_data_list: list
) -> list:
    """比较排行榜数据与数据库记录，返回需要更新的公会 ID 列表

    同时会为新公会初始化基础表和统计表记录

    Args:
        conn: 数据库连接
        season_id: 当前赛季 ID
        clan_data_list: 排行榜公会数据

    Returns:
        需要更新的公会 ID 列表。
    """
    update_ids = []
    cursor: Cursor = conn.cursor()
    try:
        # 批量查询已存在的公会记录，避免逐条查询
        clan_ids = [d[0] for d in clan_data_list]

        placeholders = ','.join(['%s'] * len(clan_ids))
        cursor.execute(
            f"""SELECT clan_id, season, UNIX_TIMESTAMP(last_battle_at) 
                FROM T_clan_stats
                WHERE clan_id IN ({placeholders})""",
            clan_ids,
        )
        existing_map = {row[0]: row for row in cursor.fetchall()}

        for clan_data in clan_data_list:
            clan_id = clan_data[0]
            existing = existing_map.get(clan_id)

            if existing is None:
                # 新公会：初始化基础表和统计表
                cursor.execute(
                    'INSERT INTO T_clan_base (clan_id, tag) VALUES (%s, %s)',
                    [clan_id, clan_data[1]],
                )
                for table_name in CLAN_INIT_TABLE_LIST:
                    cursor.execute(
                        f'INSERT INTO {table_name} (clan_id) VALUES (%s)',
                        [clan_id],
                    )
                cursor.execute(
                    'UPDATE T_clan_base SET table_count = %s WHERE clan_id = %s',
                    [len(CLAN_INIT_TABLE_LIST), clan_id],
                )
                update_ids.append(clan_id)
            else:
                # 已有公会：比较 last_battle_at 和赛季是否变化
                if clan_data[3] is None:
                    continue
                if (
                    existing[2] is None
                    or existing[2] != clan_data[3]
                    or existing[1] != season_id
                ):
                    # 判断需要更新的条件
                    # 1. 数据库中没有 last_battle_at 记录（首次统计到该工会）
                    # 2. last_battle_at 时间戳不同（有新战斗发生）
                    # 3. 赛季 ID 不同（新赛季首次获取数据）
                    update_ids.append(clan_id)

        conn.commit()
    except Exception:
        conn.rollback()
        logger.error(traceback.format_exc())
    finally:
        cursor.close()
    return update_ids

def refresh_clan_league(conn: Connection, clan_data_list: list) -> None:
    """全量刷新公会联赛字段

    先将所有公会 league 置为 5（无联赛），再根据排行榜数据更新

    Args:
        conn: 数据库连接
        clan_data_list: 排行榜公会数据
    """
    cursor: Cursor = conn.cursor()
    try:
        cursor.execute(
            'UPDATE T_clan_base SET league = 5, updated_at = CURRENT_TIMESTAMP'
        )
        # 批量更新
        update_sql = """
            UPDATE T_clan_base
            SET 
                tag = %s, 
                league = %s, 
                updated_at = CURRENT_TIMESTAMP
            WHERE clan_id = %s
        """
        update_params = [
            [d[1], d[2], d[0]] for d in clan_data_list
        ]
        cursor.executemany(update_sql, update_params)
        conn.commit()
        logger.info('Clan league refreshed: %d', len(clan_data_list))
    except Exception:
        conn.rollback()
        logger.error(traceback.format_exc())
    finally:
        cursor.close()

def refresh_clan_cache(
    redis_client: Redis, conn: Connection, season_id: int
) -> None:
    """全量刷新 Redis 中的公会排行榜缓存

    Args:
        redis_client: Redis 客户端
        conn: 数据库连接
        season_id: 当前赛季 ID
        now_ts: 当前时间戳，用于记录缓存更新时间
    """
    cursor: Cursor = conn.cursor()
    try:
        sql = """
            SELECT 
                clan_id, 
                public_rating, 
                stage_battles, 
                stage_victories
            FROM T_clan_stats
            WHERE season = %s;
        """
        cursor.execute(sql, [season_id])
        rows = cursor.fetchall()

        result = {}
        for row in rows:
            # Rating = 公开评分 + 晋级赛场次*0.1 + 晋级赛胜场*0.01
            result[row[0]] = round(row[1] + row[2] * 0.1 + row[3] * 0.01, 2)

        key = 'leaderboard:clan'
        pipe = redis_client.pipeline()
        pipe.delete(key)
        if result:
            pipe.zadd(key, {str(k): float(v) for k, v in result.items()})
        pipe.execute()
        redis_client.set('leaderboard:clan_update_time', int(datetime.now().timestamp()))
        logger.info('Clan leaderboard cache refreshed')
    except Exception:
        logger.error(traceback.format_exc())
    finally:
        cursor.close()

def _build_clan_result(raw_data: dict, clan_id: int, season_id: int) -> dict:
    """从 API 原始响应构建标准化的公会结果字典"""
    ladder_name = 'mk_ladder' if REGION == 'ru' else 'wows_ladder'
    ladder = raw_data['clanview'][ladder_name]

    clan_result = {
        'clan_id': clan_id,
        'leading_team_number': ladder['leading_team_number'],
        'battles_count': ladder['battles_count'],
        'wins_count': ladder['wins_count'],
        'public_rating': ladder['public_rating'],
        'league': ladder['league'],
        'division': ladder['division'],
        'division_rating': ladder['division_rating'],
        'longest_winning_streak': ladder['longest_winning_streak'],
        'stage_type': None,
        'stage_battles': 0,
        'stage_victories': 0,
        'stage_progress': None,
        'last_battle_time': formtime_to_timestamp(ladder['last_battle_at']),
        'team_data': {1: [], 2: []},
    }

    leading_team = clan_result['leading_team_number']

    for team_data in ladder['ratings']:
        if team_data['season_number'] != season_id:
            continue

        team_number = team_data['team_number']
        team_result = [
            team_data['battles_count'],
            team_data['wins_count'],
            team_data['public_rating'],
            team_data['league'],
            team_data['division'],
            team_data['division_rating'],
            None,  # stage_type
            None,  # stage_progress
        ]

        if team_data.get('stage'):
            stage = team_data['stage']
            team_result[6] = 1 if stage['type'] == 'promotion' else 2

            stage_battles = 0
            stage_victories = 0
            stage_progress_parts = []
            for progress in stage['progress']:
                stage_battles += 1
                if progress == 'victory':
                    stage_victories += 1
                    stage_progress_parts.append('\u2605')  # ★
                else:
                    stage_progress_parts.append('\u2606')  # ☆

            team_result[7] = ''.join(stage_progress_parts)

            if team_number == leading_team:
                clan_result['stage_type'] = team_result[6]
                clan_result['stage_battles'] = stage_battles
                clan_result['stage_victories'] = stage_victories
                clan_result['stage_progress'] = team_result[7]

        if team_result[0] > 0:
            clan_result['team_data'][team_number] = team_result

    return clan_result

def _build_insert_data(
    new_team_data: dict,
    old_team_data: dict,
    clan_id: int,
    last_battle_time: int,
) -> list[list]:
    """对比新旧队伍数据，生成需要插入的对战记录列表

    Args:
        new_team_data: 新队伍数据 {1: dict|None, 2: dict|None}
        old_team_data: 旧队伍数据 {1: dict|None, 2: dict|None}
        clan_id: 公会 ID
        last_battle_time: 最后战斗时间戳

    Returns:
        待插入的对战记录列表。
    """
    insert_data_list = []

    for team_number in [1, 2]:
        new_data = new_team_data.get(team_number)
        if new_data is None:
            continue

        old_data = old_team_data.get(team_number)

        if old_data is not None:
            battles_diff = new_data['battles_count'] - old_data['battles_count']
            wins_diff = new_data['wins_count'] - old_data['wins_count']
        else:
            battles_diff = new_data['battles_count']
            wins_diff = new_data['wins_count']

        # 只处理恰好 1 场新战斗的情况
        if battles_diff != 1:
            continue

        temp_list = [last_battle_time, clan_id, team_number]

        # 战斗结果
        temp_list.append(1 if wins_diff == 1 else 0)

        # 战斗评分变化
        if old_data is not None:
            rating_diff = new_data['public_rating'] - old_data['public_rating']
        else:
            rating_diff = new_data['public_rating']
        if rating_diff > 0:
            temp_list.append(f'+{rating_diff}')
        elif rating_diff < 0:
            temp_list.append(str(rating_diff))
        else:
            temp_list.append(None)

        # 晋级赛阶段标识
        if (
            new_data.get('stage_type')
            and new_data.get('stage_progress')
        ):
            temp_list.append('+' + new_data['stage_progress'][-1])
        else:
            temp_list.append(None)

        temp_list.extend([
            new_data['league'],
            new_data['division'],
            new_data['division_rating'],
            new_data['public_rating'],
            new_data['stage_type'],
            new_data['stage_progress'],
        ])

        insert_data_list.append(temp_list)

    return insert_data_list

def update_clan_season(
    redis_client: Redis, 
    conn: Connection, 
    season_id: int, 
    clan_id: int
) -> None:
    """更新单个公会的赛季数据，并同步更新 Redis 排行榜缓存

    Args:
        redis_client: Redis 客户端
        conn: 数据库连接
        season_id: 当前赛季 ID
        clan_id: 公会 ID
    """
    try:
        # 1. 请求公会详情
        url = f'{CLAN_API}/api/clanbase/{clan_id}/claninfo/'
        result = fetch_data(url)
        error = record_http_metrics(redis_client, [result])
        if error is not None:
            _log_warning(f'{error} {url}')
            return

        # 2. 解析并构建标准化数据
        clan_result = _build_clan_result(result, clan_id, season_id)
        team_data_1 = clan_result['team_data'][1]
        team_data_2 = clan_result['team_data'][2]

        # 3. 数据库操作
        cursor: Cursor = conn.cursor()
        try:
            cursor.execute(
                'SELECT season, team_data FROM T_clan_stats WHERE clan_id = %s',
                [clan_id],
            )
            clan = cursor.fetchone()

            insert_data_list = []

            if clan and clan[0] == season_id:
                # 已有本赛季记录：对比新旧数据
                original_team_data = json.loads(clan[1])
                old_team_data = {
                    1: format_clan_data(original_team_data[0]),
                    2: format_clan_data(original_team_data[1]),
                }
                new_team_data = {
                    1: format_clan_data(team_data_1),
                    2: format_clan_data(team_data_2),
                }
                insert_data_list = _build_insert_data(
                    new_team_data, old_team_data,
                    clan_id, clan_result['last_battle_time'],
                )
            else:
                # 新赛季或新公会：使用空旧数据
                new_team_data = {
                    1: format_clan_data(team_data_1),
                    2: format_clan_data(team_data_2),
                }
                empty_old = {1: None, 2: None}
                insert_data_list = _build_insert_data(
                    new_team_data, empty_old,
                    clan_id, clan_result['last_battle_time'],
                )

            # 更新公会统计表
            update_sql = """
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
                    last_battle_at = FROM_UNIXTIME(%s),
                    updated_at = CURRENT_TIMESTAMP
                WHERE clan_id = %s
            """
            cursor.execute(update_sql, [
                season_id,
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
                json.dumps([team_data_1, team_data_2]),
                clan_result['last_battle_time'],
                clan_id,
            ])

            # 插入对战明细
            if insert_data_list:
                insert_sql = f"""
                    INSERT INTO T_clan_battle_s{season_id} (
                        battle_time, clan_id, team_number, battle_result,
                        battle_rating, battle_stage, league, division,
                        division_rating, public_rating, stage_type, stage_progress
                    ) VALUES (
                        FROM_UNIXTIME(%s),%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s
                    )
                """
                cursor.executemany(insert_sql, insert_data_list)

            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()

        # 4. 更新 Redis 排行榜缓存
        clan_rating = round(
            clan_result['public_rating']
            + clan_result['stage_battles'] * 0.1
            + clan_result['stage_victories'] * 0.01,
            2,
        )
        redis_client.zadd(
            'leaderboard:clan', {str(clan_id): float(clan_rating)}
        )

    except Exception:
        _log_error(traceback.format_exc())