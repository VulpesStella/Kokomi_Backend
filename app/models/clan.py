from aiomysql.connection import Connection
from aiomysql.cursors import Cursor

from app.database import MysqlConnection
from app.loggers import ExceptionLogger
from app.response import JSONResponse
from app.utils import TimeUtils


class ClanModel:
    @ExceptionLogger.handle_database_exception_async
    async def read_base(clan_id: int):
        '''
        从数据库中获取工会的基本数据
        '''
        try:
            conn: Connection = await MysqlConnection.get_connection()
            await conn.begin()
            cur: Cursor = await conn.cursor()

            data = {
                'uid': clan_id,
                'base': None,
                'users': None
            }
            # 读clan_base库
            sql = """
                SELECT 
                    tag, 
                    league, 
                    touch_at
                FROM clan_base 
                WHERE clan_id = %s;
            """
            await cur.execute(sql, [clan_id])
            row = await cur.fetchone()
            if not row:
                await conn.commit()
                return JSONResponse.get_success_response(data)
            data['base'] = {
                'tag': row[0],
                'league': row[1],
                'last_touch_time': TimeUtils.fromtimestamp(row[2])
            }
            # 读clan_users库
            sql = """
                SELECT 
                    is_enabled, 
                    member_count, 
                    member_ids, 
                    touch_at
                FROM clan_users 
                WHERE clan_id = %s;
            """
            await cur.execute(sql, [clan_id])
            row = await cur.fetchone()
            data['users'] = {
                'is_enabled': row[0],
                'member_count': row[1],
                'member_ids': row[2],
                'last_touch_time': TimeUtils.fromtimestamp(row[3])
            }

            await conn.commit()
            return JSONResponse.get_success_response(data)
        except Exception as e:
            await conn.rollback()
            raise e
        finally:
            await cur.close()
            await MysqlConnection.release_connection(conn)

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
