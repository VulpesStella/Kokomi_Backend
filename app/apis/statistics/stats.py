from app.core import EnvConfig
from app.response import JSONResponse
from app.loggers import ExceptionLogger
from app.models import PlatyerModel
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
    @ExceptionLogger.handle_program_exception_async
    async def refresh_user_cache(account_id: int):
        redis_key = f"token:ac:{account_id}"
        result = await RedisClient.get(redis_key)
        if result['code'] != 1000:
            return result
        if result['data']:
            ac = result['data']
        else:
            ac = None
        result = await ExternalAPI.get_user_header(account_id, ac)
        return result
    
    # @staticmethod
    # @ExceptionLogger.handle_program_exception_async
    # async def get_user_pvp(
    #     account_id: int,
    #     field: str = None,
    #     include_old: bool = True
    # ):
    #     redis_key = f"token:ac:{account_id}"
    #     result = await RedisClient.get(redis_key)
    #     if result['code'] != 1000:
    #         return result
    #     if result['data']:
    #         ac = result['data']
    #     else:
    #         ac = None
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
    #         'type': field,
    #         'basic': result['data'],
    #         'statistics': {}
    #     }
    #     result = await ExternalAPI.get_user_pvp(account_id, ac, field, include_old)
    #     if result['code'] != 1000:
    #         return result
    #     data['statistics'] = {
    #         'overall': {},
    #         'battle_type': {},
    #         'ship_type': {},
    #         'record': {},
    #         'chart': {}
    #     }
        
    #     server_data = JsonUtils.read('ship_data')
    #     if EnvConfig.REGION == 'ru':
    #         shipid_data = JsonUtils.read('ship_name_lesta')
    #     else:
    #         shipid_data = JsonUtils.read('ship_name_wg')
    #     original_data = pvp_calculate_rating(result['data']['original_data'], server_data['ship_data'])
    #     data['statistics']['overall'] = processing_overall_data(original_data, 'pvp')
    #     data['statistics']['battle_type'] = processing_battle_type_data(original_data)
    #     data['statistics']['ship_type'] = processing_ship_type_data(original_data, 'pvp', shipid_data)
    #     data['statistics']['chart'] = processing_pvp_chart(original_data, shipid_data)
    #     data['statistics']['record'] = result['data']['record']

    #     return JSONResponse.get_success_response(data)
    
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