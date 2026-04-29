from app.core import EnvConfig
from app.database import MySQLManager
from app.loggers import ExceptionLogger
from app.response import JSONResponse
from app.schemas import UserBasicData, ClanBasicData
from app.utils import GameUtils, TimeUtils


class PlayerModel:
    @ExceptionLogger.handle_database_exception_async
    async def test_read_base(account_id: int):
        '''
        从数据库中获取用户的基本数据
        '''
        async with MySQLManager.read_only_cursor() as cur:
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

    @ExceptionLogger.handle_database_exception_async
    async def refresh_base(user_data: UserBasicData | None, clan_data: ClanBasicData | None):
        '''
        根据api请求获取到的用户和用户所在工会数据刷新数据库数据
        '''
        constants = EnvConfig.get_constants()
        async with MySQLManager.auto_transaction_cursor() as cur:
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
                for table_name in constants.USER_INIT_TABLE_LIST:
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
                    sql,[len(constants.USER_INIT_TABLE_LIST),account_id]
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

            return JSONResponse.API_1000_Success

    @ExceptionLogger.handle_database_exception_async
    async def fetch_leaderboard_data(ship_id: int, account_ids: list[str]):
        """根据用户ID列表，从数据库中批量读取排行榜数据"""
        async with MySQLManager.read_only_cursor() as cur:
            placeholders = ','.join(['%s'] * len(account_ids))
            sql = f"""
                SELECT 
                    s.account_id,
                    u.clan_tag,
                    u.league,
                    u.username,
                    s.battles,
                    s.rating,
                    CASE
                        WHEN s.rating < 750 THEN 1
                        WHEN s.rating < 1100 THEN 2
                        WHEN s.rating < 1350 THEN 3
                        WHEN s.rating < 1550 THEN 4
                        WHEN s.rating < 1750 THEN 5
                        WHEN s.rating < 2100 THEN 6
                        WHEN s.rating < 2450 THEN 7
                        ELSE 8
                    END AS rating_level,
                    ROUND(s.win_rate, 2) AS win_rate,
                    CASE
                        WHEN s.win_rate < 40 THEN 1
                        WHEN s.win_rate < 45 THEN 2
                        WHEN s.win_rate < 50 THEN 3
                        WHEN s.win_rate < 52.5 THEN 4
                        WHEN s.win_rate < 55 THEN 5
                        WHEN s.win_rate < 60 THEN 6
                        WHEN s.win_rate < 67 THEN 7
                        ELSE 8
                    END AS win_rate_level,
                    ROUND(s.solo_rate, 2) AS solo_rate,
                    CASE
                        WHEN s.solo_rate < 10 THEN 1
                        WHEN s.solo_rate < 30 THEN 2
                        WHEN s.solo_rate < 40 THEN 3
                        WHEN s.solo_rate < 50 THEN 4
                        WHEN s.solo_rate < 60 THEN 5
                        WHEN s.solo_rate < 70 THEN 6
                        WHEN s.solo_rate < 80 THEN 7
                        ELSE 8
                    END AS solo_rate_level,
                    s.avg_damage,
                    s.avg_damage_level AS avg_damage_level,
                    s.avg_frags,
                    s.avg_frags_level AS avg_frags_level,
                    s.avg_exp,
                    ROUND(s.hit_ratio, 2) AS hit_ratio,
                    s.max_exp,
                    s.max_damage
                FROM T_ship_pvp_leaderboard s
                LEFT JOIN V_user_basic_with_clan u
                    ON s.account_id = u.account_id
                WHERE s.account_id IN ({placeholders})
                  AND s.ship_id = %s;
            """
            await cur.execute(sql, account_ids + [ship_id])
            rows = await cur.fetchall()
            result = {}
            for row in rows:
                account_id = str(row[0])
                result[account_id] = {
                    'clan_tag': row[1],
                    'league': row[2],
                    'username': row[3],
                    'battles': row[4],
                    'rating': row[5],
                    'rating_level': row[6],
                    'win_rate': row[7],
                    'win_rate_level': row[8],
                    'solo_rate': row[9],
                    'solo_rate_level': row[10],
                    'avg_damage': row[11],
                    'avg_damage_level': row[12],
                    'avg_frags': row[13],
                    'avg_frags_level': row[14],
                    'avg_exp': row[15],
                    'hit_ratio': row[16],
                    'max_exp': row[17],
                    'max_damage': row[18]
                }
            
            return JSONResponse.get_success_response(result)