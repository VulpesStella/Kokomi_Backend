from aiomysql.connection import Connection
from aiomysql.cursors import Cursor

from app.database import MysqlConnection
from app.loggers import ExceptionLogger
from app.response import JSONResponse


class ClanModel:
    @ExceptionLogger.handle_database_exception_async
    async def get_clan_tag_batch():
        '''
        读取所有工会的基本数据
        '''
        try:
            conn: Connection = await MysqlConnection.get_connection()
            await conn.begin()
            cur: Cursor = await conn.cursor()

            sql = """
                SELECT 
                    clan_id, 
                    tag, 
                    league
                FROM clan_base;
            """
            await cur.execute(
                sql
            )
            data = {}
            rows = await cur.fetchall()
            for row in rows:
                data[row[0]] = [row[1], row[2]]

            await conn.commit()
            return JSONResponse.get_success_response(data)
        except Exception as e:
            await conn.rollback()
            raise e
        finally:
            await cur.close()
            await MysqlConnection.release_connection(conn)
