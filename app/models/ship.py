from app.database import MySQLManager
from app.loggers import ExceptionLogger
from app.response import JSONResponse

class ShipModel:
    @ExceptionLogger.handle_database_exception_async
    async def get_ranking_ship_ids():
        async with MySQLManager.read_only_cursor() as cur:
            result = []
            sql = """
                SELECT 
                    b.ship_id, 
                    s.battles 
                FROM T_ship_base b
                LEFT JOIN T_ship_stats_by_battles s
                  ON b.ship_id = s.ship_id
                WHERE b.is_enabled = 1 
                AND b.is_old = 0
                AND b.tier > 5;
            """
            await cur.execute(sql)
            rows = await cur.fetchall()
            for row in rows:
                if row[1] >= 1000:
                    result.append(row[0])
            return JSONResponse.get_success_response(result)
            
    @ExceptionLogger.handle_database_exception_async
    async def get_ship_info(ship_id: int):
        async with MySQLManager.read_only_cursor() as cur:
            sql = """
                SELECT
                    b.tier,
                    t.name AS type,
                    n.name AS nation,
                    r.name AS rarity,
                    b.premium, 
                    b.special, 
                    b.index_code
                FROM
                    T_ship_base b
                INNER JOIN D_ship_type t
                    ON b.type_id = t.id
                INNER JOIN D_ship_nation n
                    ON b.nation_id = n.id
                INNER JOIN D_ship_rarity r
                    ON b.rarity_id = r.id
                WHERE b.ship_id = %s;
            """
            await cur.execute(sql, [ship_id])
            row = await cur.fetchone()
            result = {
                'tier': row[0],
                'type': row[1],
                'nation': row[2],
                'rarity': row[3],
                'is_premium': True if row[4] else False,
                'is_special': True if row[5] else False,
                'index': row[6]
            } 
            return JSONResponse.get_success_response(result)

    @ExceptionLogger.handle_database_exception_async
    async def get_ranking_data_by_ids(ship_id: int, id_list: list):
        async with MySQLManager.read_only_cursor() as cur:
            sql = """
                SELECT 
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
                    END AS r_l,
                    CONCAT(ROUND(s.win_rate, 2), '%') AS win_rate,
                    CASE
                        WHEN s.win_rate < 40 THEN 1
                        WHEN s.win_rate < 45 THEN 2
                        WHEN s.win_rate < 50 THEN 3
                        WHEN s.win_rate < 52.5 THEN 4
                        WHEN s.win_rate < 55 THEN 5
                        WHEN s.win_rate < 60 THEN 6
                        WHEN s.win_rate < 67 THEN 7
                        ELSE 8
                    END AS wr_l,
                    CONCAT(ROUND(s.solo_rate, 2), '%') AS solo_rate,
                    CASE
                        WHEN s.solo_rate < 10 THEN 1
                        WHEN s.solo_rate < 30 THEN 2
                        WHEN s.solo_rate < 40 THEN 3
                        WHEN s.solo_rate < 50 THEN 4
                        WHEN s.solo_rate < 60 THEN 5
                        WHEN s.solo_rate < 70 THEN 6
                        WHEN s.solo_rate < 80 THEN 7
                        ELSE 8
                    END AS sr_l,
                    s.avg_damage,
                    s.avg_damage_level AS ad_l,
                    s.avg_frags,
                    s.avg_frags_level AS af_l,
                    s.avg_exp,
                    CONCAT(s.hit_ratio, '%') AS hit_ratio,
                    s.max_exp,
                    s.max_damage
                FROM T_ship_pvp_leaderboard s
                LEFT JOIN V_user_basic_with_clan u
                  ON s.account_id = u.account_id
                WHERE s.ship_id = %s 
                  AND s.account_id in (%s);
            """
            await cur.execute(sql,[ship_id, ','.join(id_list)])
            rows = await cur.fetchall()
            for row in rows:
                ...