import os
import time
import json
import logging
import pymysql
import requests
from tqdm import tqdm
from pathlib import Path
from dotenv import load_dotenv


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

ROOT_DIR = Path(os.getcwd())

if (ROOT_DIR / 'env.dev').exists():
    logger.info('Loading environment file: env.dev')
    load_dotenv('env.dev')
elif (ROOT_DIR / 'env.prod').exists():
    logger.info('Loading environment file: env.prod')
    load_dotenv('env.prod')
else:
    raise FileNotFoundError('No environment file found')

DB_CONFIG = {
    "host": 'localhost',
    "port": int(os.getenv("MYSQL_PORT", 3306)),
    "user": 'root',
    "password": os.getenv("MYSQL_ROOT_PASSWORD"),
    "database": os.getenv("MYSQL_DATABASE"),
    'autocommit': False
}

os.environ['NO_PROXY'] = '127.0.0.1,localhost'

file_path = ROOT_DIR / 'data/json/init_marker.json'
with open(file_path, "r", encoding="utf-8") as f:
    data = json.load(f)
    REGION: str = data['region']
file_path = ROOT_DIR / 'data/const/constants.json'
with open(file_path, "r", encoding="utf-8") as f:
    data = json.load(f)
    USER_ACTIVITY_THRESHOLDS: list = data['USER_ACTIVITY_THRESHOLDS']
    USER_INIT_TABLE_LIST: list = data['USER_INIT_TABLE_LIST']
file_path = ROOT_DIR / 'data/const/endpoints.json'
with open(file_path, "r", encoding="utf-8") as f:
    data = json.load(f)
    VORTEX_API: list = data[REGION]['vortex_api']

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

        diff = int(time.time()) - last_battle_time
        for threshold, level in USER_ACTIVITY_THRESHOLDS:
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
        if REGION == 'ru':
            rating_count = 0
            rating_count += statistics.get('rating_solo', {}).get('battles_count', 0)
            rating_count += statistics.get('rating_div', {}).get('battles_count', 0)
            user_data['rating_battles'] = rating_count
        
        return user_data

    @staticmethod
    def _init_new_user(cursor, account_id: int, username: str) -> None:
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
        cursor.execute(sql, [account_id, username])
        for table_name in USER_INIT_TABLE_LIST:
            sql = f"""
                INSERT INTO {table_name} (
                    account_id
                ) VALUES (
                    %s
                );
            """
            cursor.execute(sql, [account_id])

    @staticmethod
    def _fetch_user_base_row(cursor, account_id: int) -> tuple | None:
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
        cursor.execute(sql, [account_id])
        return cursor.fetchone()

    @staticmethod
    def _update_user_base(cursor, account_id: int, user_data: dict, old_username: str, old_timestamp: int) -> None:
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
            cursor.execute(sql, [user_data['username'], account_id])
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
    def _update_user_stats(cursor, account_id: int, user_level: int, user_data: dict) -> None:
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
            cursor.execute(sql, [account_id])
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
            cursor.execute(sql, [user_level, account_id])
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
            cursor.execute(
                sql,
                [user_data['activity_level'], user_data['total_battles'], user_data['pve_battles'], 
                user_data['pvp_battles'], user_data['ranked_battles'], user_data['rating_battles'], 
                user_data['karma'], user_data['last_battle_at'], user_level, user_data['activity_level'], 
                account_id]
            )

    @classmethod
    def refresh(cls, cursor, account_id: int, api_result: dict) -> str | None:
        """基于用户基本信息接口的数据，刷新数据库的 user_stats 表
        
        eg. https://vortex.worldofwarships.asia/api/accounts/2023619512/
        
        Returns:
            None: 成功
            str: 错误类型名称
        """
        user_data = cls._extract_user_data(account_id, api_result)

        # 从数据库中读取用户的username
        existing = cls._fetch_user_base_row(cursor, account_id)
        
        if not existing:
            cls._init_new_user(cursor, account_id, user_data['username'])
            old_username = user_data['username']
            old_timestamp = None
            user_level = None
        else:
            old_username, old_timestamp, user_level = existing

        if not user_level:
            user_level = 0

        # 更新 T_user_base
        cls._update_user_base(cursor, account_id, user_data, old_username, old_timestamp)
        # 更新 T_user_stats
        cls._update_user_stats(cursor, account_id, user_level, user_data)

        return

def is_existing(cursor, account_id: int):
    cursor.execute("SELECT 1 FROM T_user_base WHERE account_id = %s;", [account_id])
    if cursor.fetchone():
        return True
    else:
        return False

def fetch_data(url: str, params: dict = None):
    try:
        resp = requests.get(url, params=params, timeout=5)
        if resp.status_code == 200:
            result = resp.json()
            return result
        elif resp.status_code == 404:
            return {}
        return f'HTTP_STATUS_{resp.status_code}'
    except Exception as e:
        return f'ERROR_{type(e).__name__}'

def main(filepath: Path):
    with open(filepath, "r", encoding="utf-8") as f:
        users: list = json.load(f)

    if not users:
        logger.info("No users to process, exiting")
        return
    
    conn = pymysql.connect(**DB_CONFIG)
    
    with conn.cursor() as cursor:
        with tqdm(users, desc="Inserting clans", total=len(users)) as pbar:
            for item in pbar:
                pbar.set_postfix_str(str(item))
                existing = is_existing(cursor, item)
                if existing:
                    continue
                url = f'{VORTEX_API[0]}/api/accounts/{item}/'
                response = fetch_data(url)
                if response == {}:
                    tqdm.write(f'{item} | User not exist')
                    continue
                if isinstance(response, str):
                    tqdm.write(f'{item} | {response}')
                    continue
                # 处理异常情况
                if response.get('status') != 'ok':
                    tqdm.write(f'{item} | GameAPI Error')
                    continue
                response = response.get('data', {})
                result = UserStatsSyncer.refresh(cursor, item, response)
                if isinstance(result, str):
                    tqdm.write(f'{item} | {result}')
                    continue
                conn.commit()

if __name__ == '__main__':
    """从接口读取所有有效的工会数据
    
    使用示例：
    python init/fetch_users.py
    """
    
    filepath = ROOT_DIR / 'data/trash/users.json'

    try:
        main(filepath)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(e)