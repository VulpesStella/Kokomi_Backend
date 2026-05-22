from app.core import EnvConfig
from app.response import JSONResponse
from app.loggers import ExceptionLogger
from app.models import PlayerModel, UserStatsSyncer
from app.utils import GameUtils, JsonUtils
from app.middlewares import RedisClient
from app.network import ExternalAPI
from .processing import (
    pvp_calculate_rating, 
    processing_overall_data, 
    processing_battle_type_data,
    processing_ship_type_data,
    processing_pvp_chart,
    processing_cb_overall_data,
    processing_cb_seasons_data
)

class StatsAPI:
    @staticmethod
    @ExceptionLogger.handle_program_exception_async
    async def get_user_pvp_overall(
        account_id: int,
        include_old: bool = True
    ):
        # 从 Redis 中获取用户的 access_token
        redis_key = f"token:ac:{account_id}"
        response = await RedisClient.get_token(redis_key)
        error, access_token = JSONResponse.extract_data_strict(response)
        if error:
            return access_token
        
        # 先读数据库，读不到数据再请求
        error, user = JSONResponse.extract_data_strict(
            response=await PlayerModel.get_user_name_and_clan(account_id)
        )
        if error:
            return user
        
        if user is None or not user['stats']:
            error, response = JSONResponse.extract_data_strict(
                response=await ExternalAPI.get_user_basic(account_id, access_token)
            )
            if error:
                return response
            
            user_info = response.get(str(account_id)) if response else None

            if user_info is None:
                return JSONResponse.API_2011_UserNotExist
            
            if 'hidden_profile' in user_info:
                return JSONResponse.API_2015_UserHiddenProfile
            
            if (
                user_info is None or 
                'statistics' not in user_info or 
                'basic' not in user_info['statistics']
            ):
                return JSONResponse.API_2013_UserDataIsNone
            
            error, refresh = JSONResponse.extract_data_strict(
                response=await UserStatsSyncer.refresh(account_id, response)
            )
            if error:
                return refresh
            
            statistics = user_info['statistics']
            basic_data = statistics.get('basic', {})
            leveling_points = basic_data.get('leveling_points', 0)
            if leveling_points >= 1_000_000:
                leveling_points -= 1_000_000
            
            if leveling_points == 0:
                return JSONResponse.API_2013_UserDataIsNone
            
            register_time = int(user_info.get('created_at', 0))
            
            user_basic = {
                'user_id': account_id,
                'username': user_info['name'],
                'clan_id': None,
                'clan_tag': None,
                'league': None,
                'karma': user_info.get('karma', 0),
                'created_at': register_time if register_time not in (0, None) else None,
                'insignias': user_info.get('dog_tag')
            }
        else:
            user_basic = user['basic']

        result = {
            'mode': 'pvp',
            'basic': user_basic,
            'statistics': {}
        }

        return JSONResponse.get_success_response(result)
        
        # if result['data'] is None:
        #     # 数据库中无用户数据，进行网络请求获取数据
        #     result = await ExternalAPI.get_user_brief(account_id, ac)
        #     if result['code'] != 1000:
        #         return result
        # data = {
        #     'type': field,
        #     'basic': result['data'],
        #     'statistics': {}
        # }
        # result = await ExternalAPI.get_user_pvp(account_id, ac, field, include_old)
        # if result['code'] != 1000:
        #     return result
        # data['statistics'] = {
        #     'overall': {},
        #     'battle_type': {},
        #     'ship_type': {},
        #     'record': {},
        #     'chart': {}
        # }
        
        # server_data = JsonUtils.read('ship_data')
        # if EnvConfig.REGION == 'ru':
        #     shipid_data = JsonUtils.read('ship_name_lesta')
        # else:
        #     shipid_data = JsonUtils.read('ship_name_wg')
        # original_data = pvp_calculate_rating(result['data']['original_data'], server_data['ship_data'])
        # data['statistics']['overall'] = processing_overall_data(original_data, 'pvp')
        # data['statistics']['battle_type'] = processing_battle_type_data(original_data)
        # data['statistics']['ship_type'] = processing_ship_type_data(original_data, 'pvp', shipid_data)
        # data['statistics']['chart'] = processing_pvp_chart(original_data, shipid_data)
        # data['statistics']['record'] = result['data']['record']

        # return JSONResponse.get_success_response(data)
    
    # @staticmethod
    # @ExceptionLogger.handle_program_exception_async
    # async def get_user_cb(account_id: int):
    #     redis_key = f"token:ac:{account_id}"
    #     result = await RedisClient.get(redis_key)
    #     if result['code'] != 1000:
    #         return result
    #     if result['data']:
    #         ac = result['data'].get('ac')
    #     else:
    #         ac = None
    #     if ac:
    #         return JSONResponse.API_2027_ACQueryNotSupported
    #     # 先读数据库，读不到数据再请求
    #     result = await PlatyerModel.get_user_brief(account_id)
    #     if result['code'] != 1000:
    #         return result
    #     if result['data'] is None:
    #         # 数据库中无用户数据，进行网络请求获取数据
    #         result = await ExternalAPI.get_user_brief(account_id, ac)
    #         if result['code'] != 1000:
    #             return result
    #     data = {
    #         'type': 'clan_battle',
    #         'basic': result['data'],
    #         'statistics': {}
    #     }
    #     result = await ExternalAPI.get_user_cb(account_id)
    #     if result['code'] != 1000:
    #         return result
    #     data['statistics'] = {
    #         'overall': {},
    #         'achievements': result['data']['achievements'],
    #         'seasons': {}
    #     }
    #     data['statistics']['overall'] = processing_cb_overall_data(result['data']['seasons'])
    #     data['statistics']['seasons'] = processing_cb_seasons_data(result['data']['seasons'])

    #     return JSONResponse.get_success_response(data)