from aiomysql.connection import Connection
from aiomysql.cursors import Cursor

from app.database import MysqlConnection
from app.loggers import ExceptionLogger
from app.response import JSONResponse
from app.constants import Limits


class RecentModel:
    @ExceptionLogger.handle_database_exception_async
    async def recent_enable(account_id: int):
        '''
        启用recent功能
        '''
        try:
            conn: Connection = await MysqlConnection.get_connection()
            await conn.begin()
            cur: Cursor = await conn.cursor()

            sql = """
                SELECT 
                    enable_recent, 
                    enable_daily, 
                    recent_limit
                FROM recent 
                WHERE account_id = %s;
            """
            await cur.execute(sql,[account_id])
            data = await cur.fetchone()
            if data is None:
                sql = """
                    INSERT INTO recent (
                        account_id, 
                        enable_recent, 
                        recent_limit
                    ) VALUE (
                        %s,%s,%s
                    );
                """
                await cur.execute(sql,[account_id,1,Limits.DefaultRecentLimit])
                result = Limits.DefaultRecentLimit
            else:
                if data[0] == 0:
                    sql = """
                        UPDATE recent 
                        SET 
                            enable_recent = 1, 
                            recent_limit = %s
                        WHERE account_id = %s;
                    """
                    await cur.execute(sql,[Limits.DefaultRecentLimit,account_id])
                    result = Limits.DefaultRecentLimit
                else:
                    result = data[2]
            
            await conn.commit()
            return JSONResponse.get_success_response(result)
        except Exception as e:
            await conn.rollback()
            raise e
        finally:
            await cur.close()
            await MysqlConnection.release_connection(conn)

    @ExceptionLogger.handle_database_exception_async
    async def recent_close(account_id: int):
        '''
        删除recent功能
        '''
        try:
            conn: Connection = await MysqlConnection.get_connection()
            await conn.begin()
            cur: Cursor = await conn.cursor()

            sql = """
                UPDATE recent 
                SET 
                    enable_recent = 0, 
                    enable_dailt = 0
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
    async def daily_enable(account_id: int):
        '''
        启用recent(pro)功能
        '''
        try:
            conn: Connection = await MysqlConnection.get_connection()
            await conn.begin()
            cur: Cursor = await conn.cursor()

            sql = """
                SELECT 
                    enable_recent, 
                    enable_daily, 
                    recent_limit 
                FROM recent 
                WHERE account_id = %s;
            """
            await cur.execute(sql,[account_id])
            data = await cur.fetchone()
            if data is None:
                sql = """
                    INSERT INTO recent (
                        account_id, 
                        enable_recent, 
                        enable_daily, 
                        recent_limit 
                    ) VALUE (
                        %s,%s,%s,%s
                    );
                """
                await cur.execute(sql,[account_id,1,1,Limits.DefaultRecentProLimit])
            else:
                if data[0] == 0 or data[1] == 0:
                    if data[1] < Limits.DefaultRecentProLimit:
                        sql = """
                            UPDATE recent 
                            SET 
                                enable_recent = 1, 
                                enable_daily = 1, 
                                recent_limit = %s 
                            WHERE account_id = %s;
                        """
                        await cur.execute(sql,[Limits.DefaultRecentLimit,account_id])
                    else:
                        sql = """
                            UPDATE recent 
                            SET 
                                enable_recent = 1, 
                                enable_daily = 1 
                            WHERE account_id = %s;
                        """
                        await cur.execute(sql,[account_id])
                
            await conn.commit()
            return JSONResponse.get_success_response(1)
        except Exception as e:
            await conn.rollback()
            raise e
        finally:
            await cur.close()
            await MysqlConnection.release_connection(conn)

    @ExceptionLogger.handle_database_exception_async
    async def daily_close(account_id: int):
        '''
        删除recent(pro)功能
        '''
        try:
            conn: Connection = await MysqlConnection.get_connection()
            await conn.begin()
            cur: Cursor = await conn.cursor()

            sql = """
                UPDATE recent 
                SET 
                    enable_daily = 0 
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