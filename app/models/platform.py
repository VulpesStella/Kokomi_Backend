from aiomysql.connection import Connection
from aiomysql.cursors import Cursor

from app.database import MysqlConnection
from app.loggers import ExceptionLogger
from app.response import JSONResponse


class PlatformModel:
    '''数据库管理相关的操作'''
    @ExceptionLogger.handle_database_exception_async
    async def get_overview():
        try:
            conn: Connection = await MysqlConnection.get_connection()
            await conn.begin()
            cur: Cursor = await conn.cursor()

            result = {
                'user': 0,
                'clan': 0,
                'recent': 0,
                'recents': 0
            }
            sql = """
                SELECT 
                    COUNT(*) 
                FROM user_base;
            """
            await cur.execute(sql)
            row = await cur.fetchone()
            result['user'] = row[0]
            sql = """
                SELECT 
                    COUNT(*) 
                FROM clan_base;
            """
            await cur.execute(sql)
            row = await cur.fetchone()
            result['clan'] = row[0]
            sql = """
                SELECT 
                    account_id,  
                    enable_recent, 
                    enable_daily
                FROM recent;
            """
            await cur.execute(sql)
            rows = cur.fetchall()
            for row in rows:
                if row[1] == 1:
                    result['recent'] += 1
                if row[2] == 1:
                    result['recents'] += 1
            
            await conn.commit()
            return JSONResponse.get_success_response(result)
        except Exception as e:
            await conn.rollback()
            raise e
        finally:
            await cur.close()
            await MysqlConnection.release_connection(conn)