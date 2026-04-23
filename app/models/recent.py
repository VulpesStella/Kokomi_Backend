from aiomysql.connection import Connection
from aiomysql.cursors import Cursor

from app.database import MysqlConnection
from app.loggers import ExceptionLogger
from app.response import JSONResponse
from app.constants import Limits


class RecentModel:
    @ExceptionLogger.handle_database_exception_async
    async def test_recent_enable(account_id: int):
        '''
        启用recent功能
        '''
        try:
            conn: Connection = await MysqlConnection.get_connection()
            await conn.begin()
            cur: Cursor = await conn.cursor()

            sql = """
                SELECT 
                    user_level, 
                    storage_limit 
                FROM T_user_config 
                WHERE account_id = %s;
            """
            await cur.execute(sql,[account_id])
            data = await cur.fetchone()
            if data is None:
                await conn.commit()
                return JSONResponse.API_2016_UserNotInDB
            else:
                if data[0] == 0:
                    sql = """
                        UPDATE T_user_config 
                        SET 
                            user_level = 1, 
                            storage_limit = %s
                        WHERE account_id = %s;
                    """
                    await cur.execute(sql,[Limits.DefaultRecentLimit,account_id])
            
            await conn.commit()
            return JSONResponse.API_1000_Success
        except Exception as e:
            await conn.rollback()
            raise e
        finally:
            await cur.close()
            await MysqlConnection.release_connection(conn)

    @ExceptionLogger.handle_database_exception_async
    async def test_recent_close(account_id: int):
        '''
        删除recent功能
        '''
        try:
            conn: Connection = await MysqlConnection.get_connection()
            await conn.begin()
            cur: Cursor = await conn.cursor()

            sql = """
                SELECT 
                    user_level, 
                    storage_limit 
                FROM T_user_config 
                WHERE account_id = %s;
            """
            await cur.execute(sql,[account_id])
            data = await cur.fetchone()
            if data is None:
                await conn.commit()
                return JSONResponse.API_2016_UserNotInDB
            else:
                sql = """
                    UPDATE T_user_config 
                    SET 
                        user_level = 0, 
                        storage_limit = 0 
                    WHERE account_id = %s;
                """
                await cur.execute(sql,[account_id])
            
            await conn.commit()
            return JSONResponse.API_1000_Success
        except Exception as e:
            await conn.rollback()
            raise e
        finally:
            await cur.close()
            await MysqlConnection.release_connection(conn)
    
    @ExceptionLogger.handle_database_exception_async
    async def test_daily_enable(account_id: int):
        '''
        启用recent(pro)功能
        '''
        try:
            conn: Connection = await MysqlConnection.get_connection()
            await conn.begin()
            cur: Cursor = await conn.cursor()

            sql = """
                SELECT 
                    user_level, 
                    storage_limit 
                FROM T_user_config 
                WHERE account_id = %s;
            """
            await cur.execute(sql,[account_id])
            data = await cur.fetchone()
            if data is None:
                await conn.commit()
                return JSONResponse.API_2016_UserNotInDB
            else:
                if data[0] != 2:
                    sql = """
                        UPDATE T_user_config 
                        SET 
                            user_level = 2, 
                            storage_limit = %s
                        WHERE account_id = %s;
                    """
                    await cur.execute(sql,[Limits.DefaultRecentLimit,account_id])
                
            await conn.commit()
            return JSONResponse.get_success_response(1)
        except Exception as e:
            await conn.rollback()
            raise e
        finally:
            await cur.close()
            await MysqlConnection.release_connection(conn)

    @ExceptionLogger.handle_database_exception_async
    async def test_daily_close(account_id: int):
        '''
        删除recent(pro)功能
        '''
        try:
            conn: Connection = await MysqlConnection.get_connection()
            await conn.begin()
            cur: Cursor = await conn.cursor()

            sql = """
                SELECT 
                    user_level, 
                    storage_limit 
                FROM T_user_config 
                WHERE account_id = %s;
            """
            await cur.execute(sql,[account_id])
            data = await cur.fetchone()
            if data is None:
                await conn.commit()
                return JSONResponse.API_2016_UserNotInDB
            else:
                if data[0] == 2:
                    sql = """
                        UPDATE T_user_config 
                        SET 
                            user_level = 1, 
                            storage_limit = %s
                        WHERE account_id = %s;
                    """
                    await cur.execute(sql,[Limits.DefaultRecentLimit,account_id])
            
            await conn.commit()
            return JSONResponse.API_1000_Success
        except Exception as e:
            await conn.rollback()
            raise e
        finally:
            await cur.close()
            await MysqlConnection.release_connection(conn)