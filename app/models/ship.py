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
                    b.index_code,
                    a.zh_sg, 
                    a.zh_cn, 
                    a.zh_tw, 
                    a.en_short, 
                    a.en_full, 
                    a.ja, 
                    a.ru 
                FROM
                    T_ship_base b
                INNER JOIN D_ship_type t
                    ON b.type_id = t.id
                INNER JOIN D_ship_nation n
                    ON b.nation_id = n.id
                INNER JOIN D_ship_rarity r
                    ON b.rarity_id = r.id
                INNER JOIN T_ship_name a
                    ON b.ship_id = a.ship_id
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
                'index': row[6][:6],
                'name': {
                    'zh': {
                        'sg': row[7],
                        'cn': row[8],
                        'tw': row[9]
                    },
                    'en': {
                        'short': row[10],
                        'full': row[11]
                    },
                    'ja': row[12],
                    'ru': row[13]
                }
            } 
            return JSONResponse.get_success_response(result)