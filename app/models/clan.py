from app.database import MySQLManager
from app.loggers import ExceptionLogger
from app.response import JSONResponse
from app.utils import TimeUtils


class ClanModel:
    CLAN_RANKING_CTE = """
        WITH ranked AS (
            SELECT
                RANK() OVER (
                    ORDER BY
                        (s.public_rating + s.stage_battles * 0.1 + s.stage_victories * 0.01) DESC,
                        s.clan_id ASC
                ) AS rank,
                s.clan_id,
                b.tag AS clan_tag,
                s.leading_team_number AS team,
                s.battles_count AS battles,
                CASE
                    WHEN s.battles_count = 0 THEN 0
                    ELSE ROUND(s.wins_count / s.battles_count * 100, 2)
                END AS win_rate,
                CASE
                    WHEN s.battles_count = 0 THEN 0
                    WHEN (s.wins_count / s.battles_count * 100) < 40 THEN 1
                    WHEN (s.wins_count / s.battles_count * 100) < 45 THEN 2
                    WHEN (s.wins_count / s.battles_count * 100) < 50 THEN 3
                    WHEN (s.wins_count / s.battles_count * 100) < 52.5 THEN 4
                    WHEN (s.wins_count / s.battles_count * 100) < 55 THEN 5
                    WHEN (s.wins_count / s.battles_count * 100) < 60 THEN 6
                    WHEN (s.wins_count / s.battles_count * 100) < 67 THEN 7
                    ELSE 8
                END AS win_rate_level,
                s.league,
                s.division,
                s.public_rating AS rating,
                s.longest_winning_streak,
                s.stage_type,
                s.stage_progress,
                UNIX_TIMESTAMP(s.last_battle_at) AS last_battle_at
            FROM T_clan_stats s
            LEFT JOIN T_clan_base b
                ON s.clan_id = b.clan_id
            WHERE s.season = %s AND s.battles_count > 0
        )
    """

    @staticmethod
    def _format_ranking_rows(rows: list[tuple]) -> list[dict]:
        result = []
        for row in rows:
            result.append({
                'rank': row[0],
                'clan': {
                    'id': row[1],
                    'tag': row[2] or '',
                    'league': row[6],
                    'division': row[7]
                },
                'team': row[3],
                'battles': row[4],
                'win_rate': row[5],
                'rating': row[8],
                'level': {
                    'win_rate': row[9]
                },
                'longest_winning_streak': row[10],
                'stage': {
                    'type': row[11],
                    'progress': row[12]
                },
                'last_battle_at': row[13]
            })
        return result

    @ExceptionLogger.handle_database_exception_async
    async def test_read_base(clan_id: int):
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

            sql = """
                SELECT
                    UNIX_TIMESTAMP(next_update_time)
                FROM V_clan_update_schedule
                WHERE clan_id = %s;
            """
            await cur.execute(sql, [clan_id])
            row = await cur.fetchone()
            data['next_update'] = TimeUtils.calu_time_diff(row[0])

            return JSONResponse.get_success_response(data)

    @ExceptionLogger.handle_database_exception_async
    async def fetch_clan_leaderboard_page(season_id: int, page: int, page_size: int):
        offset = (page - 1) * page_size
        sql = ClanModel.CLAN_RANKING_CTE + """
            SELECT
                rank,
                clan_id,
                clan_tag,
                team,
                battles,
                win_rate,
                league,
                division,
                rating,
                win_rate_level,
                longest_winning_streak,
                stage_type,
                stage_progress,
                last_battle_at
            FROM ranked
            ORDER BY rank
            LIMIT %s OFFSET %s;
        """

        async with MySQLManager.read_only_cursor() as cur:
            await cur.execute(sql, [season_id, page_size, offset])
            rows = await cur.fetchall()
            return JSONResponse.get_success_response(
                ClanModel._format_ranking_rows(rows)
            )

    @ExceptionLogger.handle_database_exception_async
    async def fetch_clan_leaderboard_rank(season_id: int, clan_id: int):
        sql = ClanModel.CLAN_RANKING_CTE + """
            SELECT
                rank,
                clan_id,
                clan_tag,
                team,
                battles,
                win_rate,
                league,
                division,
                rating,
                win_rate_level,
                longest_winning_streak,
                stage_type,
                stage_progress,
                last_battle_at
            FROM ranked
            WHERE clan_id = %s
            LIMIT 1;
        """

        async with MySQLManager.read_only_cursor() as cur:
            await cur.execute(sql, [season_id, clan_id])
            row = await cur.fetchone()
            if not row:
                return JSONResponse.get_success_response(None)
            return JSONResponse.get_success_response(
                ClanModel._format_ranking_rows([row])[0]
            )
