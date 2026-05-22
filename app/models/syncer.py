from aiomysql.cursors import Cursor
from typing import Optional

from app.core import EnvConfig
from app.constants import ClanColor
from app.database import MySQLManager
from app.middlewares import RedisClient
from app.loggers import ExceptionLogger
from app.response import JSONResponse
from app.utils import TimeUtils


class UserStatsSyncer:
    @staticmethod
    def _get_insignias(data: dict) -> str:
        """从 DogTag 数据中生成标识字符串"""
        if not data:
            return None
        
        keys = [
            "texture_id",
            "symbol_id",
            "border_color_id",
            "background_color_id",
            "background_id"
        ]

        if any(k not in data for k in keys):
            return None
        
        return "-".join(str(data[k]) for k in keys)
    
    @staticmethod
    def _get_activity_level(last_battle_time: int | None) -> int:
        """根据最后战斗时间戳返回活跃等级（0-9）"""
        if not last_battle_time or last_battle_time <= 0:
            return 0

        diff = TimeUtils.timestamp() - last_battle_time

        constants = EnvConfig.get_constants()
        for threshold, level in constants.USER_ACTIVITY_THRESHOLDS:
            if diff <= threshold:
                return level

        return 9

    @classmethod
    def _extract_user_data(cls, account_id: int, api_result: dict) -> dict:
        """从 API 响应中提取用户基础数据"""
        user_data = {
            'username': None,
            'register_time': None,
            'insignias': None,
            'is_enabled': 1,
            'is_public': 1,
            'activity_level': 0,
            'total_battles': 0,
            'pve_battles': 0,
            'pvp_battles': 0,
            'ranked_battles': 0,
            'rating_battles': 0,
            'karma': 0,
            'last_battle_at': None
        }
        
        user_info = api_result.get(str(account_id)) if api_result else None

        # 隐藏战绩
        if 'hidden_profile' in user_info:
            user_data['is_public'] = 0
            user_data['username'] = user_info['name']
            return user_data
        
        # 无有效数据
        if user_info is None or 'statistics' not in user_info:
            user_data['is_enabled'] = 0
            return user_data
        
        # 无数据账号
        if 'basic' not in user_info['statistics']:
            user_data['username'] = user_info['name']
            register_time = int(user_info.get('created_at', 0))
            user_data['register_time'] = register_time if register_time != 0 else None
            return user_data
        
        # 正常有数据用户
        statistics = user_info['statistics']
        basic_data = statistics.get('basic', {})
        leveling_points = basic_data.get('leveling_points', 0)
        
        # 中国服主播体验账号的特殊等级点数偏移量（1,000,000）
        # 国服 API 返回的 leveling_points 包含了此偏移，需减去以得到真实场次
        if leveling_points >= 1_000_000:
            leveling_points -= 1_000_000
        
        # 处理时间戳字段
        register_time = int(user_info.get('created_at', 0))
        last_battle_time = basic_data.get('last_battle_time', 0)
        if last_battle_time == 0:
            last_battle_time = None
        
        user_data.update({
            'username': user_info['name'],
            'register_time': register_time if register_time not in (0, None) else None,
            'insignias': cls._get_insignias(user_info.get('dog_tag')),
            'activity_level': cls._get_activity_level(last_battle_time),
            'total_battles': leveling_points,
            'karma': basic_data.get('karma', 0),
            'last_battle_at': last_battle_time,
            'pve_battles': statistics.get('pve', {}).get('battles_count', 0),
            'pvp_battles': statistics.get('pvp', {}).get('battles_count', 0),
            'ranked_battles': statistics.get('rank_solo', {}).get('battles_count', 0),
        })
        
        # 处理俄服的评分战数据
        if EnvConfig.REGION == 'ru':
            rating_count = 0
            rating_count += statistics.get('rating_solo', {}).get('battles_count', 0)
            rating_count += statistics.get('rating_div', {}).get('battles_count', 0)
            user_data['rating_battles'] = rating_count
        
        return user_data

    @staticmethod
    async def _init_new_user(cursor: Cursor, account_id: int, username: str | None) -> None:
        """为新用户创建基础表记录"""
        if not username:
            username = f'User_{account_id}'
        sql = """
            INSERT INTO T_user_base (
                account_id, 
                username 
            ) VALUES (
                %s, %s
            );
        """
        await cursor.execute(sql, [account_id, username])
        constants = EnvConfig.get_constants()
        for table_name in constants.USER_INIT_TABLE_LIST:
            sql = f"""
                INSERT INTO {table_name} (
                    account_id
                ) VALUES (
                    %s
                );
            """
            await cursor.execute(sql, [account_id])

    @staticmethod
    async def _fetch_user_base_row(cursor: Cursor, account_id: int) -> tuple | None:
        sql = """
            SELECT
                b.username,
                UNIX_TIMESTAMP(b.updated_at),
                c.user_level
            FROM T_user_base b
            LEFT JOIN T_user_config c
              ON b.account_id = c.account_id
            WHERE b.account_id = %s;
        """
        await cursor.execute(sql, [account_id])
        return await cursor.fetchone()

    @staticmethod
    async def _update_user_base(cursor: Cursor, account_id: int, user_data: dict, old_username: str, old_timestamp: int) -> None:
        """更新 T_user_base 表"""
        if not user_data['username']:
            return
        
        if user_data['register_time'] is None:
            # 有名称但无注册时间 -> 隐藏战绩用户
            sql = """
                UPDATE T_user_base 
                SET 
                    username = %s, 
                    updated_at = NOW() 
                WHERE account_id = %s;
            """
            await cursor.execute(sql, [user_data['username'], account_id])
        else:
            # 有名称和注册时间 -> 正常用户
            sql = """
                UPDATE T_user_base 
                SET 
                    username = %s, 
                    register_time = FROM_UNIXTIME(%s), 
                    insignias = %s, 
                    updated_at = NOW() 
                WHERE account_id = %s;
            """
            await cursor.execute(
                sql,[user_data['username'], user_data['register_time'], user_data['insignias'], account_id]
            )
        
        # 检测昵称变更
        if old_timestamp and old_username != user_data['username']:
            sql = """
                INSERT INTO T_user_action (
                    account_id, 
                    username
                ) VALUES (
                    %s, %s
                );
            """
            await cursor.execute(sql, [account_id, old_username])

    @staticmethod
    async def _update_user_stats(cursor: Cursor, account_id: int, user_level: int, user_data: dict) -> None:
        """更新 T_user_stats 表"""
        if user_data['is_enabled'] == 0:
            # 账号不存在
            sql = """
                UPDATE T_user_stats 
                SET 
                    is_enabled = 0, 
                    activity_level = 0, 
                    next_refresh_at = NULL,
                    updated_at = NOW() 
                WHERE account_id = %s;
            """
            await cursor.execute(sql, [account_id])
        elif user_data['is_public'] == 0:
            # 账号隐藏战绩
            sql = """
                UPDATE T_user_stats 
                SET 
                    is_enabled = 1, 
                    is_public = 0, 
                    activity_level = 0, 
                    next_refresh_at = F_user_next_refresh_at(%s, 0), 
                    updated_at = NOW() 
                WHERE account_id = %s;
            """
            await cursor.execute(sql, [user_level, account_id])
        else:
            sql = """
                UPDATE T_user_stats 
                SET 
                    is_enabled = 1,  
                    is_public = 1, 
                    activity_level = %s,
                    total_battles = %s, 
                    pve_battles = %s, 
                    pvp_battles = %s, 
                    ranked_battles = %s, 
                    rating_battles = %s, 
                    karma = %s, 
                    last_battle_at = FROM_UNIXTIME(%s), 
                    next_refresh_at = F_user_next_refresh_at(%s, %s), 
                    updated_at = NOW() 
                WHERE account_id = %s;
            """
            await cursor.execute(
                sql,
                [user_data['activity_level'], user_data['total_battles'], user_data['pve_battles'], 
                user_data['pvp_battles'], user_data['ranked_battles'], user_data['rating_battles'], 
                user_data['karma'], user_data['last_battle_at'], user_level, user_data['activity_level'], 
                account_id]
            )

    @classmethod
    @ExceptionLogger.handle_database_exception_async
    async def refresh(cls, account_id: int, api_result: dict) -> str | None:
        """基于用户基本信息接口的数据，刷新数据库的 user_stats 表
        
        eg. https://vortex.worldofwarships.asia/api/accounts/2023619512/
        
        Returns:
            None: 成功
            str: 错误类型名称
        """
        user_data = cls._extract_user_data(account_id, api_result)
        
        async with MySQLManager.auto_transaction_cursor() as cursor:
            # 从数据库中读取用户的username
            existing = await cls._fetch_user_base_row(cursor, account_id)
            
            if not existing:
                lock_key = 'refresh_lock:user_insert'
                error, lock = JSONResponse.extract_data_strict(
                    response=await RedisClient.acquire_lock(lock_key)
                )
                if error:
                    return lock
                if not lock:
                    return JSONResponse.API_2019_AcqurieLockFailed
                await cls._init_new_user(cursor, account_id, user_data['username'])
                old_username = user_data['username']
                old_timestamp = None
                user_level = None
            else:
                old_username, old_timestamp, user_level = existing

        if not existing:
            await RedisClient.drop(lock_key)

        if not user_level:
            user_level = 0
        
        async with MySQLManager.auto_transaction_cursor() as cursor:
            # 更新 T_user_base
            await cls._update_user_base(cursor, account_id, user_data, old_username, old_timestamp)
            # 更新 T_user_stats
            await cls._update_user_stats(cursor, account_id, user_level, user_data)

        return JSONResponse.API_1000_Success
    
class UserClanSyncer:
    @staticmethod
    async def _is_existing(cursor: Cursor, clan_id: int) -> tuple | None:
        sql = """
            SELECT 
                1 
            FROM T_clan_base 
            WHERE clan_id = %s;
        """
        await cursor.execute(sql, [clan_id])
        return await cursor.fetchone()
    
    @staticmethod
    async def _init_new_clan(cursor: Cursor, clan_id: int, clan_tag: str, league: int) -> None:
        """为新用户创建基础表记录"""
        if not clan_tag:
            clan_tag = f'N/A'
        sql = """
            INSERT INTO T_clan_base (
                clan_id, 
                tag, 
                league
            ) VALUES (
                %s, %s, %s
            );
        """
        await cursor.execute(sql, [clan_id, clan_tag, league])
        constants = EnvConfig.get_constants()
        for table_name in constants.CLAN_INIT_TABLE_LIST:
            sql = f"""
                INSERT INTO {table_name} (
                    clan_id
                ) VALUES (
                    %s
                );
            """
            await cursor.execute(sql, [clan_id])

        sql = """
            UPDATE T_clan_base 
            SET 
                table_count = %s, 
                updated_at = NOW()
            WHERE clan_id = %s;
        """
        await cursor.execute(sql, [len(constants.CLAN_INIT_TABLE_LIST), clan_id])

    @staticmethod
    async def _update_user_clan(cursor: Cursor, account_id: int, clan_id: Optional[int]) -> None:
        """批量更新公会成员关系

        Args:
            cursor: 数据库游标
            clan_id: 公会 ID
            user_ids: 当前公会成员 ID 列表
        """
        sql = f"""
            UPDATE T_user_clan 
            SET 
                clan_id = %s, 
                updated_at = NOW() 
            WHERE account_id = %s;
        """
        await cursor.execute(sql, [clan_id, account_id])

    @classmethod
    async def refresh(cls, account_id: int, result: dict) -> str | None:
        """基于公会成员接口数据刷新数据库中的公会成员信息

        Args:
            conn: 数据库连接
            clan_id: 公会 ID
            result: API 返回的公会成员数据

        Returns:
            None: 成功
            str: 失败时返回错误类型名称
        """

        async with MySQLManager.auto_transaction_cursor() as cursor:
            clan_id = result.get('clan_id')
            if clan_id:
                clan_tag = result.get('clan', {}).get('tag')
                league = ClanColor.CLAN_COLOR_INDEX.get(
                    result.get('clan', {}).get('color'), 5
                )
                existing = await cls._is_existing(cursor, clan_id)
                if not existing:
                    await cls._init_new_clan(cursor, clan_id, clan_tag, league)
            await cls._update_user_clan(cursor, account_id, clan_id)

        return JSONResponse.API_1000_Success