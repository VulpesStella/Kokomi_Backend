import traceback
from redis import Redis
from pymysql import Connection
from typing import Optional

from logger import logger
from utils import get_current_timestamp
from settings import CLAN_INIT_TABLE_LIST


def need_update(conn: Connection, tracking_key: str, tracking_type: str) -> bool:
    """检查并更新数据追踪状态，判断是否需要执行更新任务

    如果追踪记录不存在或距上次更新超过 86400 秒（24小时），
    则更新追踪时间戳并返回 True，否则返回 False

    Args:
        conn: 数据库连接
        tracking_key: 追踪键，用于标识具体的追踪对象
        tracking_type: 追踪类型，用于区分不同的更新任务

    Returns:
        是否需要执行更新，异常则默认返回需要
    """
    try:
        with conn.cursor() as cursor:
            # 检查 tracking_value
            sql = """
                SELECT 
                    CASE 
                        WHEN tracking_value IS NULL THEN TRUE
                        WHEN UNIX_TIMESTAMP(NOW()) - UNIX_TIMESTAMP(tracking_value) > 86400 THEN TRUE
                        ELSE FALSE
                    END AS need_update
                FROM T_tracking_meta 
                WHERE tracking_key = %s 
                  AND tracking_type = %s;
            """
            cursor.execute(sql, [tracking_key, tracking_type])
            result = cursor.fetchone()
            if not result[0]:
                return False
            
            # 更新 tracking_value 值
            sql = """
                UPDATE T_tracking_meta 
                SET 
                    tracking_value = NOW() 
                WHERE tracking_key = %s 
                  AND tracking_type = %s;
            """
            cursor.execute(sql, [tracking_key, tracking_type])
    except Exception:
        conn.rollback()
        logger.error(traceback.format_exc())

    return True

def read_clan_cache(conn: Connection, clan_id: int) -> Optional[tuple]:
    """读取公会统计缓存数据

    从 T_clan_stats 表获取指定公会的赛季和队伍数据

    Args:
        conn: 数据库连接
        clan_id: 公会 ID

    Returns:
        包含 season 和 team_data 的元组，查询无结果时返回 None
    """
    try:
        with conn.cursor() as cursor:
            sql = """
                SELECT 
                    season, 
                    team_data 
                FROM T_clan_stats 
                WHERE clan_id = %s;
            """
            cursor.execute(sql, [clan_id])
            return cursor.fetchone()
    except Exception:
        logger.error(traceback.format_exc())

def update_clan_cache(
    conn: Connection,
    update_params: list,
    insert_data_list: list,
) -> None:
    """更新公会统计缓存并插入对战明细

    先更新 T_clan_stats 表的公会统计数据，再批量插入对战明细到赛季分表

    Args:
        conn: 数据库连接
        update_params: 更新参数列表
        insert_data_list: 对战明细插入数据列表，为空时跳过插入
    """
    try:
        
        with conn.cursor() as cursor:
            # 更新公会统计表
            update_sql = """
                UPDATE T_clan_stats
                SET
                    season = %s,
                    leading_team = %s,
                    battles = %s,
                    win_rate = %s,
                    public_rating = %s,
                    league = %s,
                    division = %s,
                    division_rating = %s,
                    max_streak = %s,
                    stage_type = %s,
                    stage_battles = %s,
                    stage_victories = %s,
                    stage_progress = %s,
                    team_data = %s,
                    last_battle_at = FROM_UNIXTIME(%s),
                    updated_at = NOW() 
                WHERE clan_id = %s
            """
            cursor.execute(update_sql, update_params)

            # 插入对战明细
            if insert_data_list:
                season_id = update_params[0]
                insert_sql = f"""
                    INSERT INTO S_clan_battle_{season_id} (
                        battle_time, clan_id, team_number, battle_result,
                        battle_rating, battle_stage, league, division,
                        division_rating, public_rating, stage_type, stage_progress
                    ) VALUES (
                        FROM_UNIXTIME(%s),%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s
                    );
                """
                cursor.executemany(insert_sql, insert_data_list)
                # for insert_data in insert_data_list:
                #     battles_result = 'Victory' if insert_data[3] else 'Defeat'
                #     logger.debug(
                #         f"Insert a battle record: {insert_data[0]} {insert_data[1]} "
                #         f"{battles_result} {insert_data[4] if insert_data[4] else ''}"
                #         f"{insert_data[5] if insert_data[5] else ''}"
                #     )

            conn.commit()
    except Exception:
        conn.rollback()
        logger.error(traceback.format_exc())

def ensure_clan_battle_table(conn: Connection, season_id: int) -> Optional[bool]:
    """确保当前赛季的公会战数据表已创建

    Args:
        conn: 数据库连接
        season_id: 赛季 ID

    Returns:
        是否成功创建，异常则返回None
    """
    try:
        with conn.cursor() as cursor:
            table_name = f'S_clan_battle_{season_id}'
    
            # 检查表是否存在
            sql = "SHOW TABLES LIKE %s;"
            cursor.execute(sql, [table_name])
            existing = cursor.fetchone()
            
            # 不存在则创建
            if existing and existing[0] == table_name:
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

                return True
            else:
                return False
    except Exception:
        conn.rollback()
        logger.error(traceback.format_exc())

def get_update_ids(
    conn: Connection, 
    season_id: int, 
    clan_data_list: list
) -> list:
    """比较排行榜数据与数据库记录，返回需要更新的公会 ID 列表

    同时会为新公会初始化基础表和统计表记录

    Args:
        conn: 数据库连接
        season_id: 当前赛季 ID
        clan_data_list: 排行榜公会数据

    Returns:
        需要更新的公会 ID 列表
    """
    update_ids = []
    try:
        with conn.cursor() as cursor:
            # 批量查询已存在的公会记录，避免逐条查询
            clan_ids = [d[0] for d in clan_data_list]

            placeholders = ','.join(['%s'] * len(clan_ids))
            sql = f"""
                SELECT 
                    clan_id, 
                    season, 
                    UNIX_TIMESTAMP(last_battle_at) 
                FROM T_clan_stats
                WHERE clan_id IN ({placeholders});
            """
            cursor.execute(sql, clan_ids)
            existing_map = {row[0]: row for row in cursor.fetchall()}

            for clan_data in clan_data_list:
                clan_id = clan_data[0]
                existing = existing_map.get(clan_id)

                if existing is None:
                    # 新公会：初始化基础表和统计表
                    sql = """
                        INSERT INTO T_clan_base (
                            clan_id, tag
                        ) VALUES (
                            %s, %s
                        );
                    """
                    cursor.execute(sql,[clan_id, clan_data[1]])
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
                    cursor.execute(sql, [len(CLAN_INIT_TABLE_LIST), clan_id])
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
    return update_ids

def refresh_clan_league(conn: Connection, clan_data_list: list) -> None:
    """全量刷新公会联赛字段

    先将所有公会 league 置为 5（无联赛），再根据排行榜数据更新

    Args:
        conn: 数据库连接
        clan_data_list: 排行榜公会数据
    """
    try:
        with conn.cursor() as cursor:
            sql = """
                UPDATE T_clan_base 
                SET 
                    league = 5, 
                    updated_at = NOW();
            """
            cursor.execute(sql)
            # 批量更新
            update_sql = """
                UPDATE T_clan_base
                SET 
                    tag = %s, 
                    league = %s, 
                    updated_at = NOW()
                WHERE clan_id = %s;
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
    try:
        with conn.cursor() as cursor:
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

            redis_client.set('leaderboard:clan_update_time', get_current_timestamp())
            logger.info('Clan leaderboard cache refreshed')
    except Exception:
        logger.error(traceback.format_exc())