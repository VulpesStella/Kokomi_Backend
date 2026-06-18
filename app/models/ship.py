from app.database import MySQLManager
from app.loggers import ExceptionLogger
from app.response import JSONResponse


class ShipModel:
    @ExceptionLogger.handle_database_exception_async
    async def get_ranking_ship_ids():
        async with MySQLManager.read_only_cursor() as cur:
            result = {}
            sql = """
                SELECT 
                    ship_id, 
                    min_battles 
                FROM V_ship_ranking_stats;
            """
            await cur.execute(sql)
            rows = await cur.fetchall()
            for row in rows:
                result[row[0]] = row[1]
            return JSONResponse.success(result)
        
    @ExceptionLogger.handle_database_exception_async
    async def get_ranking_ship_stats():
        async with MySQLManager.read_only_cursor() as cur:
            result = {}
            sql = """
                SELECT 
                    ship_id, 
                    min_battles,
                    stats_battles, 
                    win_rate, 
                    avg_damage, 
                    avg_frags 
                FROM V_ship_ranking_stats;
            """
            await cur.execute(sql)
            rows = await cur.fetchall()
            for row in rows:
                if row[2] < 1000:
                    continue
                result[row[0]] = [row[1], [row[3], row[4], row[5]]]
            return JSONResponse.success(result)
            
    @ExceptionLogger.handle_database_exception_async
    async def get_ship_base():
        async with MySQLManager.read_only_cursor() as cur:
            sql = """
                SELECT
                    b.ship_id, 
                    b.is_old,
                    b.tier,
                    t.name,
                    n.name
                FROM
                    T_ship_base b
                INNER JOIN D_ship_type t
                    ON b.type_id = t.id
                INNER JOIN D_ship_nation n
                    ON b.nation_id = n.id
                WHERE b.is_enabled = 1;
            """
            await cur.execute(sql)
            rows = await cur.fetchall()

            result = {} 
            for row in rows:
                result[str(row[0])] = [
                    row[1],
                    row[2],
                    row[3],
                    row[4]
                ]
            return JSONResponse.success(result)

    @ExceptionLogger.handle_database_exception_async
    async def get_ship_stats():
        async with MySQLManager.read_only_cursor() as cur:
            sql = """
                SELECT 
                    b.ship_id, 
                    s.battles,
                    s.win_rate, 
                    s.avg_damage, 
                    s.avg_frags
                FROM T_ship_base b
                LEFT JOIN T_ship_stats_by_battles s 
                  ON b.ship_id = s.ship_id
                WHERE b.is_enabled = 1; 
            """
            await cur.execute(sql)
            rows = await cur.fetchall()

            result = {}
            for row in rows:
                if row[1] and row[1] >= 1000:
                    result[str(row[0])] = [
                        row[2],
                        row[3],
                        row[4]
                    ]
        
        return JSONResponse.success(result)
        
    @ExceptionLogger.handle_database_exception_async
    async def get_all_ship_stats():
        async with MySQLManager.read_only_cursor() as cur:
            result = {}
            sql = """
                SELECT 
                    ship_id, 
                    battles, 
                    win_rate,
                    avg_damage, 
                    avg_frags 
                FROM T_ship_stats_by_battles;
            """
            await cur.execute(sql)
            rows = await cur.fetchall()
            for row in rows:
                if row[1] > 0:
                    result[row[0]] = [row[1], row[2], row[3], row[4]]
            return JSONResponse.success(result)