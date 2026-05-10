from app.database import MySQLManager
from app.loggers import ExceptionLogger
from app.response import JSONResponse



class DemoClanModel:
    @ExceptionLogger.handle_database_exception_async
    async def read_base(clan_id: int):
        '''
        从数据库中获取工会的基本数据
        '''
        async with MySQLManager.read_only_cursor() as cur:
            data = {
                'clan_id': clan_id,
                'clan_tag': None,
                'league': 5,
                'is_enabled': False
            }
            sql = """
                SELECT
                    tag,
                    league
                FROM T_clan_base
                WHERE clan_id = %s;
            """
            await cur.execute(sql, [clan_id])
            row = await cur.fetchone()
            if not row:
                return JSONResponse.get_success_response({'clan_id': clan_id})
            data['clan_tag'] = row[0]
            data['league'] = row[1]

            sql = """
                SELECT
                    is_enabled,
                    member_count
                FROM T_clan_users
                WHERE clan_id = %s;
            """
            await cur.execute(sql, [clan_id])
            row = await cur.fetchone()
            data['is_enabled'] = row[0]
            data['member_count'] = row[1]

            return JSONResponse.get_success_response(data)

class ClanModel:
    @ExceptionLogger.handle_database_exception_async
    async def get_latest_season():
        async with MySQLManager.read_only_cursor() as cur:
            sql = """
                SELECT MAX(season) FROM T_clan_stats;
            """
            await cur.execute(sql)
            data = await cur.fetchone()
            return JSONResponse.get_success_response(data[0] if data else 0)

    @ExceptionLogger.handle_database_exception_async
    async def get_leaderboard_data(clan_ids: list[str]):
        """根据用户ID列表，从数据库中批量读取排行榜数据"""
        async with MySQLManager.read_only_cursor() as cur:
            placeholders = ','.join(['%s'] * len(clan_ids))
            sql = f"""
                SELECT 
                    s.clan_id,
                    b.tag,
                    s.leading_team,
                    s.battles,
                    s.win_rate,
                    CASE
                        WHEN s.battles = 0 THEN 0
                        WHEN s.win_rate < 40 THEN 1
                        WHEN s.win_rate < 45 THEN 2
                        WHEN s.win_rate < 50 THEN 3
                        WHEN s.win_rate < 52.5 THEN 4
                        WHEN s.win_rate < 55 THEN 5
                        WHEN s.win_rate < 60 THEN 6
                        WHEN s.win_rate < 67 THEN 7
                        ELSE 8
                    END,
                    s.league,
                    s.division,
                    s.public_rating, 
                    s.max_streak,
                    s.stage_type,
                    s.stage_progress,
                    UNIX_TIMESTAMP(s.last_battle_at)
                FROM T_clan_stats s
                LEFT JOIN T_clan_base b
                    ON s.clan_id = b.clan_id
                WHERE s.clan_id IN ({placeholders});
            """
            await cur.execute(sql, clan_ids)
            rows = await cur.fetchall()
            result = {}
            for row in rows:
                clan_id = str(row[0])
                result[clan_id] = {
                    'tag': row[1],
                    'leading_team': row[2],
                    'battles': row[3],
                    'win_rate': row[4],
                    'win_rate_level': row[5],
                    'league': row[6],
                    'division': row[7],
                    'rating': row[8],
                    'max_streak': row[9],
                    'stage_type': row[10],
                    'stage_progress': row[11],
                    'last_battle_at': row[12]
                }
            
            return JSONResponse.get_success_response(result)
