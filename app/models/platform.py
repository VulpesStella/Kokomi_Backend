from app.database import MySQLManager
from app.loggers import ExceptionLogger
from app.response import JSONResponse


class PlatformModel:
    '''数据库管理相关的操作'''
    # @ExceptionLogger.handle_database_exception_async
    # async def get_overview():
    #     async with MySQLManager.read_only_cursor() as cur:
    #         result = {
    #             'db_metrics': {
    #                 'user': 0,
    #                 'clan': 0,
                        
    #             },
    #             'user_config': 0
    #         }
    #         sql = """
    #             SELECT 
    #                 COUNT(*) 
    #             FROM user_base;
    #         """
    #         await cur.execute(sql)
    #         row = await cur.fetchone()
    #         result['user'] = row[0]
    #         sql = """
    #             SELECT 
    #                 COUNT(*) 
    #             FROM clan_base;
    #         """
    #         await cur.execute(sql)
    #         row = await cur.fetchone()
    #         result['clan'] = row[0]
    #         sql = """
    #             SELECT 
    #                 account_id,  
    #                 enable_recent, 
    #                 enable_daily
    #             FROM recent;
    #         """
    #         await cur.execute(sql)
    #         rows = cur.fetchall()
    #         for row in rows:
    #             if row[1] == 1:
    #                 result['recent'] += 1
    #             if row[2] == 1:
    #                 result['recents'] += 1
    #         return JSONResponse.get_success_response(result)