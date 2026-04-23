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
            cur: Cursor = await conn.cursor()

            data = {
                'clan_id': clan_id,
                'clan_tag': None,
                'league': 5,
                'is_enabled': False
            }
            # 读clan_base库
            sql = """
                SELECT 
                    tag, 
                    league
                FROM T_clan_base 
                WHERE clan_id = %s;
            """
            await cur.execute(sql, [clan_id])
            row = await cur.fetchone()
            if not row:
                return JSONResponse.get_success_response({'clan_id': clan_id})
            data['clan_tag'] = row[0]
            data['league'] = row[1]
            # 读clan_users库
            sql = """
                SELECT 
                    is_enabled, 
                    member_count 
                FROM T_clan_users 
                WHERE clan_id = %s;
            """
            await cur.execute(sql, [clan_id])
            row = await cur.fetchone()
            data['is_enabled'] = row[0]
            data['member_count'] = row[1]
            sql = """
                SELECT 
                    UNIX_TIMESTAMP(next_update_time) 
                FROM V_clan_update_schedule 
                WHERE clan_id = %s;
            """
            await cur.execute(sql, [clan_id])
            row = await cur.fetchone()
            data['next_update'] = TimeUtils.calu_time_diff(row[0])

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
