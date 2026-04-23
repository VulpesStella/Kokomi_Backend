from aiomysql.connection import Connection
from aiomysql.cursors import Cursor

from app.database import MysqlConnection
from app.loggers import ExceptionLogger
from app.response import JSONResponse
from app.schemas import UserBasicData
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
                    username
                FROM user_base 
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
            await conn.begin()
            cur: Cursor = await conn.cursor()

            data = {
                'uid': account_id,
                'base': None,
                'stats': None,
                'cache': None,
                'clan': None,
                'private': None
            }
            # 读user_base库
            sql = """
                SELECT
                    username,
                    UNIX_TIMESTAMP(register_time),
                    insignias,
                    UNIX_TIMESTAMP(touch_at)
                FROM user_base
                WHERE account_id = %s;
            """
            await cur.execute(sql, [account_id])
            row = await cur.fetchone()
            if not row:
                await conn.commit()
                return JSONResponse.get_success_response(data)
            data['base'] = {
                'username': row[0],
                'register_time': TimeUtils.fromtimestamp(row[1]),
                'dog_tag': GameUtils.get_dog_tag(row[2]),
                'last_touch_time': TimeUtils.fromtimestamp(row[3])
            }
            # 读user_stats库
            sql = """
                SELECT
                    is_enabled,
                    activity_level,
                    is_public,
                    total_battles,
                    pvp_battles,
                    ranked_battles,
                    UNIX_TIMESTAMP(last_battle_at),
                    UNIX_TIMESTAMP(touch_at)
                FROM user_stats
                WHERE account_id = %s;
            """
            await cur.execute(sql, [account_id])
            row = await cur.fetchone()
            if row:
                data['stats'] = {
                    'is_enabled': row[0],
                    'activity_level': row[1],
                    'is_public': row[2],
                    'total_battles': row[3],
                    'pvp_battles': row[4],
                    'ranked_battles': row[5],
                    'last_battle_time': TimeUtils.fromtimestamp(row[6]),
                    'last_touch_time': TimeUtils.fromtimestamp(row[7])
                }
            # 读user_cache库
            sql = """
                SELECT
                    pvp_count,
                    win_rate,
                    avg_damage,
                    avg_frags,
                    max_damage,
                    max_damage_id,
                    max_exp,
                    max_exp_id
                FROM user_cache
                WHERE account_id = %s;
            """
            await cur.execute(sql, [account_id])
            row = await cur.fetchone()
            if row:
                data['cache'] = {
                    'pvp_count': row[0],
                    'win_rate': row[1],
                    'avg_damage': row[2],
                    'avg_frags': row[3],
                    'max_damage': row[4],
                    'max_damage_ship_id': row[5],
                    'max_exp': row[6],
                    'max_exp_ship_id': row[7]
                }
            # 读user_clan库
            sql = """
                SELECT
                    clan_id,
                    UNIX_TIMESTAMP(touch_at)
                FROM user_clan
                WHERE account_id = %s;
            """
            await cur.execute(sql, [account_id])
            row = await cur.fetchone()
            if row:
                data['clan'] = {
                    'clan_id': row[0],
                    'last_touch_time': TimeUtils.fromtimestamp(row[1])
                }
            # 读user_private库
            sql = """
                SELECT
                    update_date,
                    battles,
                    life_time,
                    distance,
                    gold,
                    free_xp,
                    credits,
                    slots,
                    port,
                    achieve
                FROM user_private
                WHERE account_id = %s;
            """
            await cur.execute(sql, [account_id])
            row = await cur.fetchone()
            if row:
                data['private'] = {
                    'update_date': row[0],
                    'battles': row[1],
                    'life_time': row[2],
                    'distance': row[3],
                    'gold': row[4],
                    'free_xp': row[5],
                    'credits': row[6],
                    'slots': row[7],
                    'port': row[8],
                    'achieve': row[9]
                }

            await conn.commit()
            return JSONResponse.get_success_response(data)
        except Exception as e:
            await conn.rollback()
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
    async def refresh_base(data: UserBasicData):
        '''
        根据api请求获取到的用户和用户所在工会数据刷新数据库数据
        '''
        try:
            conn: Connection = await MysqlConnection.get_connection()
            await conn.begin()
            cur: Cursor = await conn.cursor()

            # 先处理更新user_base user_basic user_clan的用户数据
            sql = """
                SELECT 
                    username, 
                    UNIX_TIMESTAMP(register_time), 
                    insignias 
                FROM user_base 
                WHERE account_id = %s;
            """
            await cur.execute(
                sql,[data.account_id]
            )
            result = await cur.fetchone()
            if result is None:
                default_name = GameUtils.get_user_default_name(data.account_id)
                sql = """
                    INSERT INTO user_base (
                        account_id, 
                        username
                    ) VALUES (
                        %s, %s
                    );
                """
                await cur.execute(
                    sql,[data.account_id, default_name]
                )
                sql = """
                    INSERT INTO user_stats (
                        account_id
                    ) VALUES (
                        %s
                    );
                """
                await cur.execute(
                    sql,[data.account_id]
                )
                sql = """
                    INSERT INTO user_clan (
                        account_id
                    ) VALUES (
                        %s
                    );
                """
                await cur.execute(
                    sql,[data.account_id]
                )
                sql = """
                    INSERT INTO user_cache (
                        account_id
                    ) VALUES (
                        %s
                    );
                """
                await cur.execute(
                    sql,[data.account_id]
                )
                result = [default_name, None]
            if data.is_enabled == 0:
                sql = """
                    UPDATE user_stats 
                    SET 
                        is_enabled = %s, 
                        touch_at = CURRENT_TIMESTAMP 
                    WHERE account_id = %s;
                """
                await cur.execute(
                    sql,[data.is_enabled, data.account_id]
                )
            elif data.is_public == 0:
                if result[0] != data.username:
                    sql = """
                        UPDATE user_base 
                        SET 
                            username = %s, 
                            touch_at = CURRENT_TIMESTAMP 
                        WHERE account_id = %s;
                    """
                    await cur.execute(
                        sql,[data.username, data.account_id]
                    )
                sql = """
                    UPDATE user_stats 
                    SET 
                        is_enabled = %s, 
                        activity_level = %s, 
                        is_public = %s, 
                        total_battles = 0, 
                        pvp_battles = 0, 
                        ranked_battles = 0,
                        last_battle_at = NULL,
                        touch_at = CURRENT_TIMESTAMP 
                    WHERE account_id = %s;
                """
                await cur.execute(
                    sql,[data.is_enabled, data.activity_level, data.is_public, data.account_id]
                )
            else:
                if result[0] != data.username or result[1] != data.register_time or result[2] != data.insignias:
                    sql = """
                        UPDATE user_base 
                        SET 
                            username = %s, 
                            register_time = FROM_UNIXTIME(%s), 
                            insignias = %s, 
                            touch_at = CURRENT_TIMESTAMP 
                        WHERE account_id = %s;
                    """
                    await cur.execute(
                        sql,[data.username, data.register_time, data.insignias, data.account_id]
                    )
                else:
                    sql = """
                        UPDATE user_base 
                        SET 
                            insignias = %s, 
                            touch_at = CURRENT_TIMESTAMP 
                        WHERE account_id = %s;
                    """
                    await cur.execute(
                        sql,[data.insignias, data.account_id]
                    )
                sql = """
                    UPDATE user_stats 
                    SET 
                        is_enabled = %s, 
                        activity_level = %s, 
                        is_public = %s, 
                        total_battles = %s, 
                        pvp_battles = %s, 
                        ranked_battles = %s, 
                        last_battle_at = FROM_UNIXTIME(%s), 
                        touch_at = CURRENT_TIMESTAMP 
                    WHERE account_id = %s;
                """
                await cur.execute(
                    sql,
                    [
                        data.is_enabled, data.activity_level, data.is_public, data.total_battles, data.pvp_battles,
                        data.ranked_battles, data.last_battle_at if data.last_battle_at != 0 else None, data.account_id
                    ]
                )
            # 处理更新clan_base数据
            if data.clan != None and data.clan.clan_id == None:
                sql = """
                    UPDATE user_clan 
                    SET 
                        clan_id = %s, 
                        touch_at = CURRENT_TIMESTAMP 
                    WHERE account_id = %s;
                """
                await cur.execute(
                    sql,[data.clan.clan_id, data.account_id]
                )
            elif data.clan != None and data.clan.clan_id != None:
                sql = """
                    SELECT 
                        tag, 
                        league 
                    FROM clan_base 
                    WHERE clan_id = %s;
                """
                await cur.execute(
                    sql,[data.clan.clan_id]
                )
                result = await cur.fetchone()
                if result is None:
                    default_name = GameUtils.get_clan_default_name()
                    sql = """
                        INSERT INTO clan_base (
                            clan_id, 
                            tag
                        ) VALUES (
                            %s, %s
                        );
                    """
                    await cur.execute(
                        sql,[data.clan.clan_id, default_name]
                    )
                    sql = """
                        INSERT INTO clan_users (
                            clan_id 
                        ) VALUES (
                            %s
                        );
                    """
                    await cur.execute(
                        sql,[data.clan.clan_id]
                    )
                    result = [default_name, None]
                sql = """
                    UPDATE user_clan 
                    SET 
                        clan_id = %s, 
                        touch_at = CURRENT_TIMESTAMP 
                    WHERE account_id = %s;
                """
                await cur.execute(
                    sql,[data.clan.clan_id, data.account_id]
                )
                if result[0] != data.clan.tag or result[1] != data.clan.league:
                    sql = """
                        UPDATE clan_base 
                        SET 
                            tag = %s, 
                            league = %s, 
                            touch_at = CURRENT_TIMESTAMP 
                        WHERE clan_id = %s;
                    """
                    await cur.execute(
                        sql,[data.clan.tag, data.clan.league, data.clan.clan_id]
                    )

            await conn.commit()
            return JSONResponse.get_success_response(data)
        except Exception as e:
            await conn.rollback()
            raise e
        finally:
            await cur.close()
            await MysqlConnection.release_connection(conn)