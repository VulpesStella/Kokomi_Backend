from aiomysql.connection import Connection
from aiomysql.cursors import Cursor

from app.core import EnvConfig
from app.database import MysqlConnection
from app.loggers import ExceptionLogger
from app.response import JSONResponse
from app.schemas import UserBasicData, ClanBasicData
from app.utils import GameUtils, TimeUtils


class PlatyerModel:
    @ExceptionLogger.handle_database_exception_async
    async def check_base(account_id: int, username: str = None):
        '''
        检查该uid是否存在于数据库中，确保事务正常
        '''
        
        try:
            conn: Connection = await MysqlConnection.get_connection()
            await conn.begin()
            cur: Cursor = await conn.cursor()

            sql = """
                SELECT 
                    table_count
                FROM T_user_base 
                WHERE account_id = %s;
            """
            await cur.execute(
                sql,[account_id]
            )
            result = await cur.fetchone()
            if result is None:
                default_name = GameUtils.get_user_default_name(account_id)
                sql = """
                    INSERT INTO user_base (
                        account_id, 
                        username
                    ) VALUES (
                        %s, %s
                    );
                """
                await cur.execute(
                    sql,[account_id, default_name]
                )
                sql = """
                    INSERT INTO user_stats (
                        account_id
                    ) VALUES (
                        %s
                    );
                """
                await cur.execute(
                    sql,[account_id]
                )
                sql = """
                    INSERT INTO user_clan (
                        account_id
                    ) VALUES (
                        %s
                    );
                """
                await cur.execute(
                    sql,[account_id]
                )
                sql = """
                    INSERT INTO user_cache (
                        account_id
                    ) VALUES (
                        %s
                    );
                """
                await cur.execute(
                    sql,[account_id]
                )
                result = [default_name, None]
                if username:
                    sql = """
                        UPDATE user_base 
                        SET 
                            username = %s
                        WHERE account_id = %s;
                    """
                    await cur.execute(
                        sql,[username, account_id]
                    )

            await conn.commit()
            return JSONResponse.API_1000_Success
        except Exception as e:
            await conn.rollback()
            raise e
        finally:
            await cur.close()
            await MysqlConnection.release_connection(conn)

    @ExceptionLogger.handle_database_exception_async
    async def read_base(account_id: int):
        '''
        从数据库中获取用户的基本数据
        '''
        try:
            conn: Connection = await MysqlConnection.get_connection()
            cur: Cursor = await conn.cursor()

            data = {
                'account_id': account_id,
                'username': None,
                'is_enabled': False,
                'is_public': False
            }
            # 读user_base库
            sql = """
                SELECT
                    username
                FROM T_user_base
                WHERE account_id = %s;
            """
            await cur.execute(sql, [account_id])
            row = await cur.fetchone()
            if not row:
                return JSONResponse.get_success_response({'account_id': account_id})
            data['username'] = row[0]
            # 读user_stats库
            sql = """
                SELECT
                    is_enabled,
                    is_public
                FROM T_user_stats
                WHERE account_id = %s;
            """
            await cur.execute(sql, [account_id])
            row = await cur.fetchone()
            if row:
                data['is_enabled'] = row[0]
                data['is_public'] = row[1]
            if not data['is_enabled'] or not data['is_public']:
                return JSONResponse.get_success_response(data)
            sql = """
                SELECT 
                    UNIX_TIMESTAMP(next_update_time) 
                FROM V_user_update_schedule 
                WHERE account_id = %s;
            """
            await cur.execute(sql, [account_id])
            row = await cur.fetchone()
            data['next_update'] = TimeUtils.calu_time_diff(row[0])
            # 读user_config库
            sql = """
                SELECT
                    user_level,
                    storage_limit,
                    query_count,
                    UNIX_TIMESTAMP(last_query_at)
                FROM T_user_config
                WHERE account_id = %s;
            """
            await cur.execute(sql, [account_id])
            row = await cur.fetchone()
            if row:
                data['user_level'] = row[0]
                data['storage_limit'] = row[1]
                data['query_count'] = row[2]
                data['last_query_time'] = TimeUtils.fromtimestamp(row[3])
            # 读user_clan库
            sql = """
                SELECT
                    clan_id
                FROM T_user_clan
                WHERE account_id = %s;
            """
            await cur.execute(sql, [account_id])
            row = await cur.fetchone()
            if row:
                data['clan_id'] = row[0]
            return JSONResponse.get_success_response(data)
        except Exception as e:
            raise e
        finally:
            await cur.close()
            await MysqlConnection.release_connection(conn)

    @ExceptionLogger.handle_database_exception_async
    async def get_user_name(account_id: int):
        '''
        从数据库中获取用户的基本数据，如果玩家或者工会的缓存数据不存在则返回none
        '''
        try:
            conn: Connection = await MysqlConnection.get_connection()
            await conn.begin()
            cur: Cursor = await conn.cursor()

            result = {
                'base': None,
                'clan': None
            }
            # 从数据库中读取缓存数据
            sql = """
                SELECT 
                    b.username, 
                    UNIX_TIMESTAMP(b.register_time), 
                    b.insignias,
                    c.clan_id 
                FROM user_base as b 
                LEFT JOIN user_clan as c 
                  ON b.account_id = c.account_id 
                WHERE b.account_id = %s;
            """
            await cur.execute(
                sql, account_id
            )
            row = await cur.fetchone()
            if row is None:
                result = None
            elif row[3] is None:
                result['base'] = {
                    'id': account_id,
                    'username': row[0],
                    'register_time': row[1],
                    'insignias': row[2]
                }
            else:
                clan_id = row[3]
                result['base'] = {
                    'id': account_id,
                    'username': row[0],
                    'register_time': row[1],
                    'insignias': row[2]
                }
                sql = """
                    SELECT 
                        tag, 
                        league 
                    FROM clan_base 
                    WHERE clan_id = %s;
                """
                await cur.execute(
                    sql, clan_id
                )
                row = await cur.fetchone()
                if row:
                    result['clan'] = {
                        'id': clan_id,
                        'tag': row[0],
                        'league': row[1]
                    }
                else:
                    result = None

            await conn.commit()
            return JSONResponse.get_success_response(result)
        except Exception as e:
            await conn.rollback()
            raise e
        finally:
            await cur.close()
            await MysqlConnection.release_connection(conn)

    @ExceptionLogger.handle_database_exception_async
    async def get_user_name_batch(account_ids: list):
        '''
        从数据库中获取用户的基本数据，如果玩家或者工会的缓存数据不存在则返回none

        用户数据为空或者隐藏战绩也返回none

        参数：
            account_id: 用户id
            region_id: 服务器id
        '''
        try:
            conn: Connection = await MysqlConnection.get_connection()
            await conn.begin()
            cur: Cursor = await conn.cursor()

            placeholders = ",".join(["%s"] * len(account_ids))
            # 从数据库中读取缓存数据
            sql = f"""
                SELECT 
                    b.account_id, 
                    b.username, 
                    c.clan_id 
                FROM user_base as b 
                LEFT JOIN user_clan as c 
                  ON b.account_id = c.account_id 
                WHERE b.account_id IN ({placeholders});
            """
            await cur.execute(
                sql,account_ids
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

    @ExceptionLogger.handle_database_exception_async
    async def refresh_base(user_data: UserBasicData | None, clan_data: ClanBasicData | None):
        '''
        根据api请求获取到的用户和用户所在工会数据刷新数据库数据
        '''
        try:
            conn: Connection = await MysqlConnection.get_connection()
            await conn.begin()
            cur: Cursor = await conn.cursor()

            account_id = user_data.account_id
            # 先处理更新user_base user_basic user_clan的用户数据
            sql = """
                SELECT 
                    username, 
                    UNIX_TIMESTAMP(updated_at) 
                FROM T_user_base 
                WHERE account_id = %s;
            """
            await cur.execute(
                sql,[account_id]
            )
            result = await cur.fetchone()
            if result is None:
                default_name = GameUtils.get_user_default_name(account_id)
                sql = """
                    INSERT INTO T_user_base (
                        account_id, 
                        username
                    ) VALUES (
                        %s, %s
                    );
                """
                await cur.execute(
                    sql,[account_id, default_name]
                )
                for table_name in EnvConfig.constants.USER_INIT_TABLE_LIST:
                    sql = f"""
                        INSERT INTO {table_name} (
                            account_id
                        ) VALUES (
                            %s
                        );
                    """
                    await cur.execute(
                        sql,[account_id]
                    )
                sql = """
                    UPDATE T_user_base 
                    SET 
                        table_count = %s 
                    WHERE account_id = %s;
                """
                await cur.execute(
                    sql,[len(EnvConfig.constants.USER_INIT_TABLE_LIST),account_id]
                )
                result = [default_name, None]
            if user_data.username:
                if user_data.insignias is None:
                    sql = """
                        UPDATE T_user_base 
                        SET 
                            username = %s, 
                            updated_at = CURRENT_TIMESTAMP 
                        WHERE account_id = %s;
                    """
                    await cur.execute(
                        sql, [user_data.username, account_id]
                    )
                else:
                    sql = """
                        UPDATE T_user_base 
                        SET 
                            username = %s, 
                            register_time = FROM_UNIXTIME(%s), 
                            insignias = %s, 
                            updated_at = CURRENT_TIMESTAMP 
                        WHERE account_id = %s;
                    """
                    await cur.execute(
                        sql,[user_data.username, user_data.register_time, user_data.insignias, account_id]
                    )
                if result[1] and result[0] != user_data.username:
                    sql = """
                        INSERT INTO T_user_action (
                            account_id, 
                            username
                        ) VALUES (
                            %s, %s
                        );
                    """
                    await cur.execute(
                        sql, [account_id, result[0]]
                    )
            if user_data.is_enabled == 0:
                sql = """
                    UPDATE T_user_stats 
                    SET 
                        is_enabled = 0, 
                        activity_level = 0,  
                        updated_at = CURRENT_TIMESTAMP 
                    WHERE account_id = %s;
                """
                await cur.execute(
                    sql,[account_id]
                )
            elif user_data.is_public == 0:
                sql = """
                    UPDATE T_user_stats 
                    SET 
                        is_enabled = 1, 
                        is_public = 0, 
                        activity_level = 0, 
                        updated_at = CURRENT_TIMESTAMP 
                    WHERE account_id = %s;
                """
                await cur.execute(
                    sql,[account_id]
                )
                
            else:
                last_battle_time = user_data.last_battle_at if user_data.last_battle_at != 0 else None
                sql = """
                    UPDATE T_user_stats 
                    SET 
                        is_enabled = 1,  
                        is_public = 1, 
                        activity_level = F_user_activity_level(%s),
                        total_battles = %s, 
                        pve_battles = %s, 
                        pvp_battles = %s, 
                        ranked_battles = %s, 
                        rating_battles = %s, 
                        karma = %s, 
                        last_battle_at = FROM_UNIXTIME(%s), 
                        updated_at = CURRENT_TIMESTAMP 
                    WHERE account_id = %s;
                """
                await cur.execute(
                    sql,
                    [
                        last_battle_time, 
                        user_data.total_battles, 
                        user_data.pve_battles, 
                        user_data.pvp_battles, 
                        user_data.ranked_battles, 
                        user_data.rating_battles, 
                        user_data.karma, 
                        last_battle_time, 
                        account_id
                    ]
                )
            # 处理更新clan_base数据
            if clan_data != None:
                sql = """
                    UPDATE T_user_clan 
                    SET 
                        clan_id = %s, 
                        updated_at = CURRENT_TIMESTAMP 
                    WHERE account_id = %s;
                """
                await cur.execute(
                    sql,[clan_data.clan_id, account_id]
                )
                if clan_data.clan_id:
                    sql = """
                        UPDATE T_clan_base 
                        SET 
                            tag = %s, 
                            league = %s, 
                            updated_at = CURRENT_TIMESTAMP 
                        WHERE clan_id = %s;
                    """
                    await cur.execute(
                        sql,[clan_data.tag, clan_data.league, clan_data.clan_id]
                    )

            await conn.commit()
            return JSONResponse.API_1000_Success
        except Exception as e:
            await conn.rollback()
            raise e
        finally:
            await cur.close()
            await MysqlConnection.release_connection(conn)