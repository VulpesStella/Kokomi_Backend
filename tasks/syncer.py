import json
from pymysql import Connection
from pymysql.cursors import Cursor

from .settings import REGION, USER_INIT_TABLE_LIST


CSSLP = 1_000_000

class UserStatsSyncer:
    # 注意：此部分代码复制来自 scripts/cache/syncer.py
    # 如需修改必须确保源文件代码也被修改，确保数据处理和写入逻辑一致
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

    @classmethod
    def _extract_user_data(cls, account_id: int, api_result: dict) -> dict:
        """从 API 响应中提取用户基础数据"""
        user_data = {
            'username': None,
            'register_time': None,
            'insignias': None,
            'is_enabled': 1,
            'is_public': 1,
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
        if 'statistics' not in user_info:
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
        
        # 处理中国服的主播体验账号的特殊情况
        if REGION == 'cn' and leveling_points >= CSSLP:
            leveling_points -= CSSLP
        
        # 处理时间戳字段：0 或 None 都转为 None
        register_time = int(user_info.get('created_at', 0))
        last_battle_time = basic_data.get('last_battle_time', 0)
        
        user_data.update({
            'username': user_info['name'],
            'register_time': register_time if register_time not in (0, None) else None,
            'insignias': cls._get_insignias(user_info.get('dog_tag')),
            'total_battles': leveling_points,
            'karma': basic_data.get('karma', 0),
            'last_battle_at': last_battle_time if last_battle_time not in (0, None) else None,
            'pve_battles': statistics.get('pve', {}).get('battles_count', 0),
            'pvp_battles': statistics.get('pvp', {}).get('battles_count', 0),
            'ranked_battles': statistics.get('rank_solo', {}).get('battles_count', 0),
        })
        
        # 处理俄服的评分战数据
        if REGION == 'ru':
            rating_count = 0
            rating_count += statistics.get('rating_solo', {}).get('battles_count', 0)
            rating_count += statistics.get('rating_div', {}).get('battles_count', 0)
            user_data['rating_battles'] = rating_count
        
        return user_data

    @staticmethod
    def _is_existing(cursor: Cursor, account_id: int) -> tuple | None:
        sql = """
            SELECT 
                username, 
                UNIX_TIMESTAMP(updated_at) 
            FROM T_user_base 
            WHERE account_id = %s;
        """
        cursor.execute(sql, [account_id])
        return cursor.fetchone()

    @staticmethod
    def _update_user_base(cursor: Cursor, account_id: int, user_data: dict, old_username: str, old_timestamp: int) -> None:
        """更新 T_user_base 表"""
        if not user_data['username']:
            return
        
        if user_data['register_time'] is None:
            # 有名称但无注册时间 -> 隐藏战绩用户
            sql = """
                UPDATE T_user_base 
                SET 
                    username = %s, 
                    updated_at = CURRENT_TIMESTAMP 
                WHERE account_id = %s;
            """
            cursor.execute(sql, [user_data['username'], account_id])
        else:
            # 有名称和注册时间 -> 正常用户
            sql = """
                UPDATE T_user_base 
                SET 
                    username = %s, 
                    register_time = FROM_UNIXTIME(%s), 
                    insignias = %s, 
                    updated_at = CURRENT_TIMESTAMP 
                WHERE account_id = %s;
            """
            cursor.execute(
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
            cursor.execute(sql, [account_id, old_username])

    @staticmethod
    def _update_user_stats(cursor: Cursor, account_id: int, user_data: dict) -> None:
        """更新 T_user_stats 表"""
        if user_data['is_enabled'] == 0:
            # 账号不存在
            sql = """
                UPDATE T_user_stats 
                SET 
                    is_enabled = 0, 
                    activity_level = 0, 
                    updated_at = CURRENT_TIMESTAMP 
                WHERE account_id = %s;
            """
            cursor.execute(sql, [account_id])
        elif user_data['is_public'] == 0:
            # 账号隐藏战绩
            sql = """
                UPDATE T_user_stats 
                SET 
                    is_enabled = 1, 
                    is_public = 0, 
                    activity_level = 0, 
                    updated_at = CURRENT_TIMESTAMP 
                WHERE account_id = %s;
            """
            cursor.execute(sql, [account_id])
        else:
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
            cursor.execute(
                sql,
                [user_data['last_battle_at'], user_data['total_battles'], user_data['pve_battles'], 
                user_data['pvp_battles'], user_data['ranked_battles'], user_data['rating_battles'], 
                user_data['karma'], user_data['last_battle_at'], account_id]
            )

    @classmethod
    def refresh(cls, conn: Connection, account_id: int, api_result: dict) -> str | None:
        """基于用户基本信息接口的数据，刷新数据库的 user_stats 表
        
        eg. https://vortex.worldofwarships.asia/api/accounts/2023619512/
        
        Returns:
            None: 成功
            str: 错误类型名称
        """
        try:
            user_data = cls._extract_user_data(account_id, api_result)
        except Exception as e:
            return type(e).__name__
        
        try:
            with conn.cursor() as cursor:
                # 从数据库中读取用户的username
                existing = cls._is_existing(cursor, account_id)
                
                if not existing:
                    return "UserNotInDB"  # 账号不存在，跳过
                
                old_username, old_timestamp = existing

                # 更新 T_user_base
                cls._update_user_base(cursor, account_id, user_data, old_username, old_timestamp)
                
                # 更新 T_user_stats
                cls._update_user_stats(cursor, account_id, user_data)
            
            conn.commit()
            return None
        except Exception as e:
            conn.rollback()
            return type(e).__name__
        
class ClanUsersSyncer:
    @staticmethod
    def _get_existing_members(cursor: Cursor, clan_id: int) -> tuple:
        """获取公会当前的成员列表和更新时间

        Args:
            cursor: 数据库游标
            clan_id: 公会 ID

        Returns:
            (member_ids_json, updated_at_timestamp) 或 None
        """
        sql = """
            SELECT 
                member_ids, 
                UNIX_TIMESTAMP(updated_at) 
            FROM T_clan_users 
            WHERE clan_id = %s;
        """
        cursor.execute(sql, [clan_id])
        return cursor.fetchone()

    @staticmethod
    def _disable_empty_clan(cursor: Cursor, clan_id: int) -> None:
        """将无成员的公会标记为不可用并清理成员关系

        Args:
            cursor: 数据库游标
            clan_id: 公会 ID
        """
        sql = """
            UPDATE T_clan_users 
            SET 
                is_enabled = 0, 
                member_count = 0, 
                member_ids = NULL, 
                updated_at = CURRENT_TIMESTAMP 
            WHERE clan_id = %s;
        """
        cursor.execute(sql, [clan_id])

        sql = """
            SELECT 
                account_id 
            FROM T_user_clan 
            WHERE clan_id = %s;
        """
        cursor.execute(sql, [clan_id])
        for row in cursor.fetchall():
            sql = """
                UPDATE T_user_clan 
                SET 
                    clan_id = NULL, 
                    updated_at = CURRENT_TIMESTAMP 
                WHERE account_id = %s;
            """
            cursor.execute(sql, [row[0]])

            sql = """
                INSERT INTO T_clan_action (
                    clan_id, 
                    account_id, 
                    action_type
                ) VALUES (
                    %s, %s, %s
                );
            """
            cursor.execute(sql, [clan_id, row[0], 2])

    @staticmethod
    def _init_new_users(cursor: Cursor, account_ids: list, users: dict) -> None:
        """为新用户创建基础表记录

        Args:
            cursor: 数据库游标
            account_ids: 需要初始化的 account_id 列表
            users: account_id -> username 映射
        """
        for account_id in account_ids:
            sql = """
                INSERT INTO T_user_base (
                    account_id, 
                    username,
                    updated_at 
                ) VALUES (
                    %s, %s, CURRENT_TIMESTAMP
                );
            """
            cursor.execute(sql, [account_id, users[account_id]])

            for table_name in USER_INIT_TABLE_LIST:
                sql = f"""
                    INSERT INTO {table_name} (
                        account_id
                    ) VALUES (
                        %s
                    );
                """
                cursor.execute(sql, [account_id])

            sql = """
                UPDATE T_user_base 
                SET 
                    table_count = %s 
                WHERE account_id = %s;
            """
            cursor.execute(sql, [len(USER_INIT_TABLE_LIST), account_id])

    @staticmethod
    def _remove_left_members(cursor: Cursor, clan_id: int, current_ids: set) -> None:
        """清理已退出公会的成员关系

        Args:
            cursor: 数据库游标
            clan_id: 公会 ID
            current_ids: 当前公会成员 ID 集合
        """
        sql = """
            SELECT 
                account_id 
            FROM T_user_clan 
            WHERE clan_id = %s;
        """
        cursor.execute(sql, [clan_id])
        for row in cursor.fetchall():
            if row[0] not in current_ids:
                sql = """
                    UPDATE T_user_clan 
                    SET 
                        clan_id = NULL, 
                        updated_at = CURRENT_TIMESTAMP 
                    WHERE account_id = %s;
                """
                cursor.execute(sql, [row[0]])

    @staticmethod
    def _update_member_relations(cursor: Cursor, clan_id: int, user_ids: list) -> None:
        """批量更新公会成员关系

        Args:
            cursor: 数据库游标
            clan_id: 公会 ID
            user_ids: 当前公会成员 ID 列表
        """
        placeholders = ",".join(["%s"] * len(user_ids))
        sql = f"""
            UPDATE T_user_clan 
            SET 
                clan_id = %s, 
                updated_at = CURRENT_TIMESTAMP 
            WHERE account_id IN ({placeholders});
        """
        cursor.execute(sql, [clan_id] + user_ids)

    @staticmethod
    def _update_clan_users(cursor: Cursor, clan_id: int, user_ids: list) -> None:
        """更新公会成员统计信息

        Args:
            cursor: 数据库游标
            clan_id: 公会 ID
            user_ids: 当前公会成员 ID 列表
        """
        sql = """
            UPDATE T_clan_users 
            SET 
                is_enabled = 1, 
                member_count = %s, 
                member_ids = %s, 
                updated_at = CURRENT_TIMESTAMP 
            WHERE clan_id = %s;
        """
        cursor.execute(sql, [len(user_ids), json.dumps(user_ids), clan_id])

    @staticmethod
    def _record_member_changes(cursor: Cursor, clan_id: int, old_data: dict, user_ids: list) -> None:
        """记录公会成员的加入和退出行为

        Args:
            cursor: 数据库游标
            clan_id: 公会 ID
            old_data: 旧成员数据 (member_ids_json, updated_at)
            user_ids: 当前公会成员 ID 列表
        """
        if not old_data or not old_data[1]:
            return

        old_ids = json.loads(old_data[0] if old_data[0] else '[]')
        added_ids = [uid for uid in user_ids if uid not in old_ids]
        removed_ids = [uid for uid in old_ids if uid not in user_ids]

        for added_id in added_ids:
            sql = """
                INSERT INTO T_clan_action (
                    clan_id, 
                    account_id, 
                    action_type
                ) VALUES (
                    %s, %s, %s
                );
            """
            cursor.execute(sql, [clan_id, added_id, 1])

        for removed_id in removed_ids:
            sql = """
                INSERT INTO T_clan_action (
                    clan_id, 
                    account_id, 
                    action_type
                ) VALUES (
                    %s, %s, %s
                );
            """
            cursor.execute(sql, [clan_id, removed_id, 2])

    @classmethod
    def refresh(cls, conn: Connection, clan_id: int, result: dict) -> str | None:
        """基于公会成员接口数据刷新数据库中的公会成员信息

        Args:
            conn: 数据库连接
            clan_id: 公会 ID
            result: API 返回的公会成员数据

        Returns:
            None: 成功
            str: 失败时返回错误类型名称
        """
        try:
            # 提取公会成员映射
            users = {}
            for user_info in result.get('items', []):
                users[user_info['id']] = user_info['name']
            user_ids = list(users.keys())

            with conn.cursor() as cursor:
                old_data = cls._get_existing_members(cursor, clan_id)

                if len(user_ids) == 0:
                    cls._disable_empty_clan(cursor, clan_id)
                else:
                    placeholders = ",".join(["%s"] * len(user_ids))
                    sql = f"""
                        SELECT account_id 
                        FROM T_user_clan 
                        WHERE account_id IN ({placeholders});
                    """
                    cursor.execute(sql, user_ids)
                    existing_ids = {row[0] for row in cursor.fetchall()}
                    missing_ids = [uid for uid in user_ids if uid not in existing_ids]

                    if missing_ids:
                        cls._init_new_users(cursor, missing_ids, users)

                    cls._remove_left_members(cursor, clan_id, set(user_ids))
                    cls._update_member_relations(cursor, clan_id, user_ids)
                    cls._update_clan_users(cursor, clan_id, user_ids)
                    cls._record_member_changes(cursor, clan_id, old_data, user_ids)

            conn.commit()
            return None
        except Exception as e:
            conn.rollback()
            return type(e).__name__