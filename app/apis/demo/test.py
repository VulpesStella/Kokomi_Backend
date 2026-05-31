import shutil

from app.core import EnvConfig
from app.constants import ClanColor
from app.loggers import ExceptionLogger
from app.network import DemoExternalAPI
from app.response import JSONResponse, ResponseDict
from app.models import DemoRecentModel
from app.middlewares import RedisClient


RECENT_LEVEL_OFF = 0
RECENT_LEVEL_STANDARD = 1
RECENT_LEVEL_PLUS = 2

class TestAPI:
    @ExceptionLogger.handle_program_exception_async
    async def test_error_log():
        """测试错误日志记录功能"""
        raise NotImplementedError

    @ExceptionLogger.handle_program_exception_async
    async def delete_error_logs():
        """删除所有错误日志文件"""
        error_dir = EnvConfig.LOG_DIR / 'error'
        exception_dir = EnvConfig.LOG_DIR / 'exception'
        del_count = 0

        for log_dir in (error_dir, exception_dir):
            if log_dir.exists() and log_dir.is_dir():
                for file_path in log_dir.glob('*'):
                    if file_path.is_file():
                        file_path.unlink()
                        del_count += 1

        return JSONResponse.get_success_response(del_count)
    
    @ExceptionLogger.handle_program_exception_async
    async def clear_service_logs():
        """清空所有服务的异常日志文件（仅清空内容，保留文件）"""
        constant = EnvConfig.get_constants()
        services = constant.SERVICE_LIST
        clear_count = 0

        for service in services:
            log_file = EnvConfig.LOG_DIR / 'scripts' / f'{service}.log'
            if log_file.exists() and log_file.is_file():
                log_file.write_text('')
                clear_count += 1

        return JSONResponse.get_success_response(clear_count)

    @ExceptionLogger.handle_program_exception_async
    async def get_user_basic(account_id: int) -> ResponseDict:
        """获取用户基本信息

        Args:
            account_id: 用户 ID

        Returns:
            ResponseDict: 统一格式的响应对象
        """
        # 从 Redis 中获取用户的 access_token
        redis_key = f"token:ac:{account_id}"
        response = await RedisClient.get_token(redis_key)
        error, access_token = JSONResponse.extract_data_strict(response)
        if error:
            return access_token
        
        # 请求 API 获取用户基本信息
        response = await DemoExternalAPI.get_user_basic(account_id, access_token)
        error, result = JSONResponse.extract_data_strict(response)
        if error:
            return result
        
        # 检查用户是否存在
        if result is None:
            return JSONResponse.API_2011_UserNotExist
        
        # 提取当前用户的详细信息
        user_info = result.get(str(account_id)) if result else None
        
        # 检查用户是否隐藏了个人资料
        if 'hidden_profile' in user_info:
            return JSONResponse.API_2015_UserHiddenProfile
        
        # 验证用户数据和统计信息是否存在
        if user_info is None or 'statistics' not in user_info:
            return JSONResponse.API_2011_UserNotExist
        
        # 验证统计数据中是否包含基本信息
        if 'basic' not in user_info['statistics']:
            return JSONResponse.API_2013_UserDataIsNone
        
        statistics = user_info['statistics']
        basic_data = statistics.get('basic', {})
        leveling_points = basic_data.get('leveling_points', 0)

        # 处理时间戳字段
        register_time = int(user_info.get('created_at', 0))
        last_battle_time = basic_data.get('last_battle_time', 0)
        
        # 构建返回数据
        data = {
            'region': EnvConfig.REGION,
            'user_id': account_id,
            'username': user_info['name'],
            'total_battles': leveling_points,
            'pve_battles': statistics.get('pve', {}).get('battles_count', 0),
            'pvp_battles': statistics.get('pvp', {}).get('battles_count', 0),
            'ranked_battles': statistics.get('rank_solo', {}).get('battles_count', 0),
            'rating_battles': 0,
            'karma': basic_data.get('karma', 0),
            'register_time': register_time if register_time not in (0, None) else None,
            'last_battle_at': last_battle_time if last_battle_time not in (0, None) else None,
            'insignias': user_info.get('dog_tag')
        }

        # RU 区域特殊处理：统计 rating 模式战斗场次
        if EnvConfig.REGION == 'ru':
            rating_count = 0
            rating_count += statistics.get('rating_solo', {}).get('battles_count', 0)
            rating_count += statistics.get('rating_div', {}).get('battles_count', 0)
            data['rating_battles'] = rating_count
        
        return JSONResponse.get_success_response(data)
    
    @ExceptionLogger.handle_program_exception_async
    async def get_user_clan(account_id: int):
        response = await DemoExternalAPI.get_user_clan(account_id)
        error, result = JSONResponse.extract_data_strict(response)
        if error:
            return result
        
        # 构建返回数据
        data = {
            'region': EnvConfig.REGION,
            'user_id': account_id,
            'clan_id': None
        }
        if result and result['clan_id'] != None:
            data['clan_id'] = result['clan_id']
            data['clan_tag'] = result['clan']['tag']
            data['league'] = ClanColor.CLAN_COLOR_INDEX.get(result['clan']['color'], 5)
        
        return JSONResponse.get_success_response(data)

    @ExceptionLogger.handle_program_exception_async
    async def get_clan_basic(clan_id: int):
        response = await DemoExternalAPI.get_clan_basic(clan_id)
        error, result = JSONResponse.extract_data_strict(response)
        if error:
            return result
        
        # 检查用户是否存在
        if result is None:
            return JSONResponse.API_2012_ClanNotExist

        clanview = result.get('clanview', {})
        clan_info = clanview.get('clan', {})

        if clan_info.get('tag') is None or clan_info.get('members_count', 0) == 0:
            return JSONResponse.API_2014_ClanDataIsNone

        # 构建返回数据
        data = {
            'region': EnvConfig.REGION,
            'clan_id': clan_id,
            'tag': clan_info.get('tag'),
            'name': clan_info.get('name'),
            'league': ClanColor.CLAN_COLOR_INDEX_2.get(clan_info.get('color', '#'), 5),
            'members': clan_info.get('members_count', 0),
            'max_members': clan_info.get('max_members_count', 0)
        }

        return JSONResponse.get_success_response(data)

    @ExceptionLogger.handle_program_exception_async
    async def get_clan_members(clan_id: int):
        response = await DemoExternalAPI.get_clan_users(clan_id)
        error, result = JSONResponse.extract_data_strict(response)
        if error:
            return result
        
        # 检查用户是否存在
        if result is None:
            return JSONResponse.API_2012_ClanNotExist
        users = []
        for user_info in result.get('items', []):
            users.append([user_info['id'], user_info['name']])

        data = {
            'region': EnvConfig.REGION,
            'clan_id': clan_id,
            'members': len(users),
            'datas': users
        }

        return JSONResponse.get_success_response(data)
    
    @ExceptionLogger.handle_program_exception_async
    async def set_recent(account_id: int, level: str):
        '''启用用户recent功能'''
        level_map = {
            "standard": RECENT_LEVEL_STANDARD,
            "plus": RECENT_LEVEL_PLUS
        }
        target_level = level_map.get(level)
        if target_level is None:
            return JSONResponse.API_1000_Success
        
        return await DemoRecentModel.set_recent_level(account_id, target_level)

    @ExceptionLogger.handle_program_exception_async
    async def del_recent(account_id: int, level: str):
        '''降低/关闭用户recent功能'''
        level_map = {
            "off": RECENT_LEVEL_OFF,
            "standard": RECENT_LEVEL_STANDARD
        }
        target_level = level_map.get(level)
        if target_level is None:
            return JSONResponse.API_1000_Success
        
        result = await DemoRecentModel.reduce_recent_level(account_id, target_level)
        if result['code'] != 1000:
            return result
        
        # 关闭recent功能时，删除用户的recent数据库文件
        if level == "off":
            user_db_file = EnvConfig.SQLITE_DIR / f'{account_id}.db'
            if user_db_file.exists():
                shutil.move(user_db_file, EnvConfig.DATA_DIR / f'trash/recent_{account_id}.db')
        
        return JSONResponse.API_1000_Success