from app.core import EnvConfig
from app.database import MySQLManager
from app.loggers import ExceptionLogger
from app.response import JSONResponse
from app.utils import TimeUtils


class DemoPlayerModel:
    @ExceptionLogger.handle_database_exception_async
    async def read_base(account_id: int):
        '''
        从数据库中获取用户的基本数据
        '''
        async with MySQLManager.read_only_cursor() as cur:
            data = {
                'region': EnvConfig.REGION,
                'user_id': account_id,
                'username': None,
                'is_enabled': False,
                'is_public': False
            }
            # 读user_base库
            sql = """
                SELECT
                    username
                FROM T_user_base
                WHERE account_id = %s;
            """
            await cur.execute(sql, [account_id])
            row = await cur.fetchone()
            if not row:
                return JSONResponse.API_2016_UserNotInDB
            data['username'] = row[0]
            # 读user_stats库
            sql = """
                SELECT
                    is_enabled,
                    is_public,
                    activity_level
                FROM T_user_stats
                WHERE account_id = %s;
            """
            await cur.execute(sql, [account_id])
            row = await cur.fetchone()
            if row:
                data['is_enabled'] = row[0]
                data['is_public'] = row[1]
            if not data['is_enabled'] or not data['is_public']:
                return JSONResponse.get_success_response(data)
            data['activity_level'] = row[2]
            # 读user_config库
            sql = """
                SELECT
                    user_level,
                    storage_limit,
                    query_count,
                    UNIX_TIMESTAMP(last_query_at)
                FROM T_user_config
                WHERE account_id = %s;
            """
            await cur.execute(sql, [account_id])
            row = await cur.fetchone()
            if row:
                data['user_level'] = row[0]
                data['storage_limit'] = row[1]
                data['query_count'] = row[2]
                data['last_query_time'] = TimeUtils.fromtimestamp(row[3])
            # 读user_clan库
            sql = """
                SELECT
                    clan_id
                FROM T_user_clan
                WHERE account_id = %s;
            """
            await cur.execute(sql, [account_id])
            row = await cur.fetchone()
            if row:
                data['clan_id'] = row[0]
            return JSONResponse.get_success_response(data)

class PlayerModel:
    @ExceptionLogger.handle_database_exception_async
    async def record_query(account_id: int):
        """记录一次用户查询"""
        async with MySQLManager.auto_transaction_cursor() as cur:
            sql = """
                UPDATE T_user_config
                SET
                    query_count = query_count + 1,
                    last_query_at = NOW()
                WHERE account_id = %s;
            """
            await cur.execute(sql, [account_id])
            return JSONResponse.API_1000_Success

    @ExceptionLogger.handle_database_exception_async
    async def get_leaderboard_data(ship_id: int, account_ids: list[str]):
        """根据用户ID列表，从数据库中批量读取排行榜数据"""
        async with MySQLManager.read_only_cursor() as cur:
            placeholders = ','.join(['%s'] * len(account_ids))
            sql = f"""
                SELECT 
                    s.account_id,
                    u.clan_id,
                    u.clan_tag,
                    u.league,
                    u.username,
                    s.battles,
                    s.rating,
                    CASE
                        WHEN s.rating < 750 THEN 1
                        WHEN s.rating < 1100 THEN 2
                        WHEN s.rating < 1350 THEN 3
                        WHEN s.rating < 1550 THEN 4
                        WHEN s.rating < 1750 THEN 5
                        WHEN s.rating < 2100 THEN 6
                        WHEN s.rating < 2450 THEN 7
                        ELSE 8
                    END AS rating_level,
                    ROUND(s.win_rate, 2) AS win_rate,
                    CASE
                        WHEN s.win_rate < 40 THEN 1
                        WHEN s.win_rate < 45 THEN 2
                        WHEN s.win_rate < 50 THEN 3
                        WHEN s.win_rate < 52.5 THEN 4
                        WHEN s.win_rate < 55 THEN 5
                        WHEN s.win_rate < 60 THEN 6
                        WHEN s.win_rate < 67 THEN 7
                        ELSE 8
                    END AS win_rate_level,
                    ROUND(s.solo_rate, 2) AS solo_rate,
                    CASE
                        WHEN s.solo_rate < 10 THEN 1
                        WHEN s.solo_rate < 30 THEN 2
                        WHEN s.solo_rate < 40 THEN 3
                        WHEN s.solo_rate < 50 THEN 4
                        WHEN s.solo_rate < 60 THEN 5
                        WHEN s.solo_rate < 70 THEN 6
                        WHEN s.solo_rate < 80 THEN 7
                        ELSE 8
                    END AS solo_rate_level,
                    s.avg_damage,
                    s.avg_damage_level AS avg_damage_level,
                    s.avg_frags,
                    s.avg_frags_level AS avg_frags_level,
                    s.avg_exp,
                    ROUND(s.hit_ratio, 2) AS hit_ratio,
                    s.max_exp,
                    s.max_damage
                FROM T_ship_pvp_leaderboard s
                LEFT JOIN V_user_basic_with_clan u
                    ON s.account_id = u.account_id
                WHERE s.account_id IN ({placeholders})
                  AND s.ship_id = %s;
            """
            await cur.execute(sql, account_ids + [ship_id])
            rows = await cur.fetchall()
            result = {}
            for row in rows:
                account_id = str(row[0])
                result[account_id] = {
                    'clan_id': row[1],
                    'clan_tag': row[2],
                    'league': row[3],
                    'username': row[4],
                    'battles': row[5],
                    'rating': row[6],
                    'rating_level': row[7],
                    'win_rate': row[8],
                    'win_rate_level': row[9],
                    'solo_rate': row[10],
                    'solo_rate_level': row[11],
                    'avg_damage': row[12],
                    'avg_damage_level': row[13],
                    'avg_frags': row[14],
                    'avg_frags_level': row[15],
                    'avg_exp': row[16],
                    'hit_ratio': row[17],
                    'max_exp': row[18],
                    'max_damage': row[19]
                }
            
            return JSONResponse.get_success_response(result)