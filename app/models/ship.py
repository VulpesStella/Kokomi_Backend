from app.database import MySQLManager
from app.loggers import ExceptionLogger
from app.response import JSONResponse
from app.core import EnvConfig


METRIC_IDS = [3, 4, 5, 7, 8, 9]

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
    async def get_ship_info(language: str):
        async with MySQLManager.read_only_cursor() as cur:
            result = {}
            language_field = {
                'zh_sg': 'zh_sg',
                'zh_cn': 'zh_cn',
                'en': 'en_short',
                'ja': 'ja',
                'ru': 'ru'
            }.get(language, 'en')
            sql = f"""
                SELECT
                    b.ship_id, 
                    b.tier,
                    t.name AS type,
                    n.name AS nation,
                    b.index_code,
                    a.{language_field} 
                FROM
                    T_ship_base b
                INNER JOIN D_ship_type t
                    ON b.type_id = t.id
                INNER JOIN D_ship_nation n
                    ON b.nation_id = n.id
                INNER JOIN T_ship_name a
                    ON b.ship_id = a.ship_id;
            """
            await cur.execute(sql)
            for row in await cur.fetchall():
                result[row[0]] = {
                    'tier': row[1],
                    'type': row[2],
                    'nation': row[3],
                    'index': row[4],
                    'name': row[5]
                } 
            return JSONResponse.success(result)
    
    @ExceptionLogger.handle_database_exception_async
    async def get_ship_info_by_id(ship_id: int, language: str):
        async with MySQLManager.read_only_cursor() as cur:
            language_field = {
                'zh_sg': 'zh_sg',
                'zh_cn': 'zh_cn',
                'en': 'en_short',
                'ja': 'ja',
                'ru': 'ru'
            }.get(language, 'en_short')
            sql = f"""
                SELECT
                    b.tier,
                    t.name AS type,
                    n.name AS nation,
                    r.name AS rarity,
                    b.premium, 
                    b.special, 
                    b.index_code,
                    a.{language_field} 
                FROM
                    T_ship_base b
                INNER JOIN D_ship_type t
                    ON b.type_id = t.id
                INNER JOIN D_ship_nation n
                    ON b.nation_id = n.id
                LEFT JOIN D_ship_rarity r
                    ON b.rarity_id = r.id
                LEFT JOIN T_ship_name a
                    ON b.ship_id = a.ship_id
                WHERE b.ship_id = %s;
            """
            await cur.execute(sql, [ship_id])
            row = await cur.fetchone()
            result = {
                'id': ship_id,
                'tier': row[0],
                'type': row[1],
                'nation': row[2],
                'rarity': row[3],
                'is_premium': True if row[4] else False,
                'is_special': True if row[5] else False,
                'index': row[6],
                'name': row[7]
            } 
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

    # @ExceptionLogger.handle_database_exception_async
    # async def del_ships(ship_ids: list):
    #     async with MySQLManager.auto_transaction_cursor as cur:
    #         sql = """
    #             UPDATE T_ship_base 
    #             SET is_enabled = 0 
    #             WHERE ship_id = %s;
    #         """
    #         await cur.executemany(sql, ship_ids)

    #         return JSONResponse.API_1000_Success
        
    # @ExceptionLogger.handle_database_exception_async
    # async def update_ships(update_list: list):
    #     insert = 0
    #     update = 0
    #     constant = EnvConfig.get_constants()

    #     async with MySQLManager.auto_transaction_cursor as cur:
    #         for ship in update_list:
    #             ship_id = ship['ship_id']
    #             sql = """
    #                 SELECT ship_id 
    #                 FROM T_ship_base 
    #                 WHERE ship_id = %s;
    #             """
    #             await cur.execute(sql, [ship_id])
    #             existing = await cur.fetchone()
    #             if existing:
    #                 sql = """
    #                     UPDATE T_ship_base 
    #                     SET 
    #                         is_old = %s, 
    #                         rarity_id = %s, 
    #                         premium = %s, 
    #                         special = %s 
    #                     WHERE ship_id = %s;
    #                 """
    #                 cur.execute(sql, [
    #                     ship['is_old'], ship['rarity_id'], ship['premium'],
    #                     ship['special'], ship_id
    #                 ])

    #                 sql = """
    #                     UPDATE T_ship_name
    #                     SET 
    #                         zh_cn = %s, 
    #                         zh_sg = %s, 
    #                         zh_tw = %s, 
    #                         en_short = %s, 
    #                         en_full = %s, 
    #                         ja = %s, 
    #                         ru = %s, 
    #                         verify = %s 
    #                     WHERE ship_id = %s;
    #                 """
    #                 cur.execute(sql, [
    #                     ship['zh_cn'], ship['zh_sg'], ship['zh_tw'],
    #                     ship['en_short'], ship['en_full'], ship['ja'],
    #                     ship['ru'], ship['verify'], ship_id
    #                 ])

    #                 update += 1
    #             else:
    #                 sql = """
    #                     INSERT INTO T_ship_base (
    #                         ship_id, is_enabled, is_old, tier, type_id,
    #                         nation_id, rarity_id, premium, special, index_code
    #                     ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
    #                 """
    #                 cur.execute(sql, [
    #                     ship['ship_id'], True, ship['is_old'], ship['tier'], ship['type_id'],
    #                     ship['nation_id'], ship['rarity_id'], ship['premium'], ship['special'],
    #                     ship['index_code']
    #                 ])

    #                 # 名称表
    #                 sql = """
    #                     INSERT INTO T_ship_name (
    #                         ship_id, zh_cn, zh_sg, zh_tw, en_short, en_full, ja, ru, verify
    #                     ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
    #                 """
    #                 cur.execute(sql, [
    #                     ship['ship_id'], ship['zh_cn'], ship['zh_sg'], ship['zh_tw'],
    #                     ship['en_short'], ship['en_full'], ship['ja'], ship['ru'], ship['verify']
    #                 ])

    #                 # 统计表
    #                 for table_name in constant.SHIP_INIT_TABLE_LIST:
    #                     sql = f"""
    #                         INSERT INTO {table_name} (ship_id) VALUES (%s);
    #                     """
    #                     cur.execute(sql, [ship['ship_id']])

    #                 # PvP 极值记录
    #                 for metric_id in METRIC_IDS:
    #                     sql = """
    #                         INSERT INTO T_ship_pvp_record
    #                         (ship_id, metric_id)
    #                         VALUES (%s, %s);
    #                     """
    #                     cur.execute(sql, [ship['ship_id'], metric_id])

    #                 insert += 1