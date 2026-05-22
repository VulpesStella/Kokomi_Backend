import random
import asyncio
from typing import Optional, Union, Any

from app.loggers import ExceptionLogger
from app.utils import GameUtils, TimeUtils
from app.constants import ClanColor
from app.models import PlayerModel
from app.health import ServiceMetrics
from app.core import EnvConfig, api_logger
from app.schemas import UserBasicData, ClanBasicData
from app.response import JSONResponse, ResponseDict

from .client import HttpClient
from .processing import (
    processing_user_basic, 
    processing_season,
    processing_pvp_data,
    processing_cb_achieve,
    processing_cb_seasons
)



async def record_http_metrics(
    responses: list[ResponseDict],
    urls: list[str]
) -> Union[tuple[True, ResponseDict], tuple[False, list[Any]]]:
    """记录 HTTP 请求指标到 Redis
    
    如果有多个Error则返回最后一个Error的信息

    Args:
        responses: fetch_data 返回结果列表

    Returns:
        错误字符串，全部成功则返回 None
    """
    results = []
    error_count = 0
    error = None

    for i, response in enumerate(responses):
        error, result = JSONResponse.extract_data_strict(response)
        if error:
            api_logger.warning(f"{result['message']} {urls[i]}")
            error_count += 1
            error = result
        else:
            results.append(result)

    if error_count:
        today = TimeUtils.now_iso()[:10]
        await ServiceMetrics.http_error_incrby(today, error_count)
        return True, error
    else:
        return False, results

class DemoExternalAPI:
    @staticmethod
    @ExceptionLogger.handle_program_exception_async
    async def get_user_basic(account_id: int, user_token: Optional[str]) -> ResponseDict:
        """请求获取用户的基本数据

        通过 Vortex API 获取指定账户的基本信息，包括用户名、统计数据、注册时间等

        Args:
            account_id: 用户 ID
            user_token: 用户的访问令牌

        Returns:
            ResponseDict: 统一格式的响应对象
        """
        # 获取配置的端点列表
        endpoints = EnvConfig.get_endpoints()
        base_url = random.choice(endpoints.VORTEX_API)

        # 调用 HTTP 客户端获取用户数据
        url = f'{base_url}/api/accounts/{account_id}/' + (f'?ac={user_token}' if user_token else '')
        response = await HttpClient.get_user_data(url)

        error, results = await record_http_metrics([response], [url])
        if error:
            return results
        
        return JSONResponse.get_success_response(results[0])
    
    @staticmethod
    @ExceptionLogger.handle_program_exception_async
    async def get_user_clan(account_id: int) -> ResponseDict:
        # 获取配置的端点列表
        endpoints = EnvConfig.get_endpoints()
        base_url = random.choice(endpoints.VORTEX_API)
        
        # 调用 HTTP 客户端获取用户所在工会数据
        url = f'{base_url}/api/accounts/{account_id}/clans/'
        response = await HttpClient.get_user_data(url)

        error, results = await record_http_metrics([response], [url])
        if error:
            return results
        
        return JSONResponse.get_success_response(results[0])
    
    @staticmethod
    @ExceptionLogger.handle_program_exception_async
    async def get_clan_basic(clan_id: int) -> ResponseDict:
        # 获取配置的端点列表
        endpoints = EnvConfig.get_endpoints()
        base_url = endpoints.CLAN_API

        # 调用 HTTP 客户端获取用户数据
        url = f'{base_url}/api/clanbase/{clan_id}/claninfo/'
        response = await HttpClient.get_clan_data(url)

        error, results = await record_http_metrics([response], [url])
        if error:
            return results
        
        return JSONResponse.get_success_response(results[0])
    
    @staticmethod
    @ExceptionLogger.handle_program_exception_async
    async def get_clan_users(clan_id: int) -> ResponseDict:
        # 获取配置的端点列表
        endpoints = EnvConfig.get_endpoints()
        base_url = endpoints.CLAN_API

        # 调用 HTTP 客户端获取用户数据
        url = f'{base_url}/api/members/{clan_id}/'
        response = await HttpClient.get_clan_data(url)

        error, results = await record_http_metrics([response], [url])
        if error:
            return results
        
        return JSONResponse.get_success_response(results[0])
       

class  ExternalAPI:
    @staticmethod
    @ExceptionLogger.handle_program_exception_async
    async def get_user_search(nickname: str):
        '''获取用户名称搜索结构

        通过输入的用户名称搜索用户账号

        参数：
            nickname: 用户名称
        
        返回：
            结果列表
        '''
        endpoints = EnvConfig.get_endpoints()
        base_url = random.choice(endpoints.VORTEX_API)
        
        url = f'{base_url}/api/accounts/search/{nickname.lower()}/'
        response = await HttpClient.get_user_data(url)

        error, results = await record_http_metrics([response], [url])
        if error:
            return results
        
        return JSONResponse.get_success_response(results[0])
    
    @staticmethod
    @ExceptionLogger.handle_program_exception_async
    async def get_clan_search(tag: str):
        '''
        通过输入的工会名称搜索工会账号

        参数：
            tga: 工会名称
        
        返回：
            结果列表
        '''
        endpoints = EnvConfig.get_endpoints()
        base_url = endpoints.CLAN_API

        url = f'{base_url}/api/search/autocomplete/?search={tag.lower()}&type=clans'
        response = await HttpClient.get_clan_data(url)

        error, results = await record_http_metrics([response], [url])
        if error:
            return results
        
        return JSONResponse.get_success_response(results[0].get('search_autocomplete_result', []))

    @staticmethod
    @ExceptionLogger.handle_program_exception_async
    async def get_user_refresh(account_id: int, user_token: Optional[str]):
        endpoints = EnvConfig.get_endpoints()
        base_url = random.choice(endpoints.VORTEX_API)
        urls = [
            f'{base_url}/api/accounts/{account_id}/' + (f'?ac={user_token}' if user_token else ''),
            f'{base_url}/api/accounts/{account_id}/clans/'
        ]
        tasks = []
        responses = []
        async with asyncio.Semaphore(len(urls)):
            for url in urls:
                tasks.append(HttpClient.get_user_data(url))
            responses = await asyncio.gather(*tasks)

        error, results = await record_http_metrics(responses, urls)
        if error:
            return results
        
        return JSONResponse.get_success_response(results)

    @staticmethod
    @ExceptionLogger.handle_program_exception_async
    async def get_user_basic(account_id: int, user_token: Optional[str]):
        endpoints = EnvConfig.get_endpoints()
        base_url = random.choice(endpoints.VORTEX_API)
        url = f'{base_url}/api/accounts/{account_id}/' + (f'?ac={user_token}' if user_token else '')
        response = await HttpClient.get_user_data(url)

        error, results = await record_http_metrics([response], [url])
        if error:
            return results
        
        return JSONResponse.get_success_response(results[0])

    @staticmethod
    @ExceptionLogger.handle_program_exception_async
    async def get_user_pvp_overall(account_id: int, ac1: str = None):
        base_url = random.choice(EnvConfig.endpoints.VORTEX_API)
        urls = [
            f'{base_url}/api/accounts/{account_id}/ships/pvp_solo/' + (f'?ac={ac1}' if ac1 else ''),
            f'{base_url}/api/accounts/{account_id}/ships/pvp_div2/' + (f'?ac={ac1}' if ac1 else ''),
            f'{base_url}/api/accounts/{account_id}/ships/pvp_div3/' + (f'?ac={ac1}' if ac1 else '')
        ]
        tasks = []
        responses = []
        async with asyncio.Semaphore(len(urls)):
            for url in urls:
                tasks.append(HttpClient.get_user_data(url))
            responses = await asyncio.gather(*tasks)

        error, results = await record_http_metrics(responses, urls)
        if error:
            return results
        
        return JSONResponse.get_success_response(results)
        
    # @staticmethod
    # @ExceptionLogger.handle_program_exception_async
    # async def varify_ac(account_id: int, user_token: Optional[str]):
    #     """检测传入的用户ac是否有效"""
    #     # 获取配置的端点列表
    #     endpoints = EnvConfig.get_endpoints()
    #     base_url = random.choice(endpoints.VORTEX_API)
    #     url = f'{base_url}/api/accounts/{account_id}/'
    #     response = await HttpClient.get_user_data(url)
    #     error, results = await record_http_metrics([response], [url])
    #     if error:
    #         return results[0]
        
    #     if response['data']:
    #         user_basic = response['data'][str(account_id)]
    #     if user_basic == None:
    #         return JSONResponse.API_2011_UserNotExist
    #     if 'hidden_profile' not in user_basic:
    #         return JSONResponse.get_success_response(False)
    #     url = f'{base_url}/api/accounts/{account_id}/' + (f'?ac={user_token}' if user_token else '')
    #     response = await HttpClient.get_user_data(url)
    #     await ServiceMetrics.http_incrby(now_time[:10], 1)
    #     error_count, error_return = varify_responses(response)
    #     if error_count != None:
    #         await ServiceMetrics.http_error_incrby(now_time[:10], error_count)
    #         return error_return
    #     # 刷新数据库数据
    #     if response['data']:
    #         user_basic = response['data'][str(account_id)]
    #     if 'hidden_profile' in user_basic:
    #         refresh_user_data = UserBasicData(
    #             account_id=account_id, 
    #             username=user_basic['name'],
    #             is_enabled=1,
    #             is_public=0
    #         )
    #         result = await PlayerModel.refresh_base(refresh_user_data, None)
    #         if result['code'] != 1000:
    #             return result
    #     elif 'statistics' not in user_basic:
    #         refresh_user_data = UserBasicData(
    #             account_id=account_id, 
    #             is_enabled=0
    #         )
    #         result = await PlayerModel.refresh_base(refresh_user_data, None)
    #         if result['code'] != 1000:
    #             return result
    #     elif 'basic' not in user_basic['statistics']:
    #         result = await PlayerModel.refresh_base(
    #             UserBasicData(
    #                 account_id=account_id, 
    #                 username=user_basic['name'],
    #                 register_time=int(user_basic['created_at'])
    #             ), None
    #         )
    #         if result['code'] != 1000:
    #             return result
    #     else:
    #         rating_count = 0
    #         if EnvConfig.REGION == 'ru':
    #             rating_count += 0 if user_basic['rating_solo']['pve'] == {} else user_basic['statistics']['rating_solo']['battles_count']
    #             rating_count += 0 if user_basic['rating_div']['pve'] == {} else user_basic['statistics']['rating_div']['battles_count']
    #         refresh_user_data = UserBasicData(
    #             account_id=account_id, 
    #             username=user_basic['name'],
    #             register_time=int(user_basic['created_at']),
    #             insignias=GameUtils.get_insignias(user_basic['dog_tag']),
    #             is_enabled=1,
    #             is_public=1,
    #             total_battles=user_basic['statistics']['basic']['leveling_points'],
    #             pve_battles=0 if user_basic['statistics']['pve'] == {} else user_basic['statistics']['pve']['battles_count'],
    #             pvp_battles=0 if user_basic['statistics']['pvp'] == {} else user_basic['statistics']['pvp']['battles_count'],
    #             ranked_battles=0 if user_basic['statistics']['rank_solo'] == {} else user_basic['statistics']['rank_solo']['battles_count'],
    #             rating_battles=rating_count,
    #             last_battle_at=user_basic['statistics']['basic']['last_battle_time'],
    #             karma=user_basic['statistics']['basic']['karma']
    #         )
    #         result = await PlayerModel.refresh_base(refresh_user_data, None)
    #         if result['code'] != 1000:
    #             return result
    #     # 效验用户ac是否有效
    #     if user_basic == None:
    #         return JSONResponse.API_2011_UserNotExist
    #     if 'hidden_profile' not in user_basic:
    #         return JSONResponse.get_success_response(True)
    #     else:
    #         return JSONResponse.get_success_response(False)

    # @staticmethod
    # @ExceptionLogger.handle_program_exception_async
    # async def get_user_pvp(account_id: int, ac1: str = None, field: str = 'pvp', include_old: bool = True):
    #     base_url = random.choice(EnvConfig.endpoints.VORTEX_API)
    #     if field == 'pvp':
    #         urls = [
    #             f'{base_url}/api/accounts/{account_id}/ships/pvp_solo/' + (f'?ac={ac1}' if ac1 else ''),
    #             f'{base_url}/api/accounts/{account_id}/ships/pvp_div2/' + (f'?ac={ac1}' if ac1 else ''),
    #             f'{base_url}/api/accounts/{account_id}/ships/pvp_div3/' + (f'?ac={ac1}' if ac1 else '')
    #         ]
    #         fields = ['pvp_solo','pvp_div2','pvp_div3']
    #     else:
    #         urls = [
    #             f'{base_url}/api/accounts/{account_id}/ships/{field}/' + (f'?ac={ac1}' if ac1 else '')
    #         ]
    #         fields = [field]
    #     tasks = []
    #     responses = []
    #     async with asyncio.Semaphore(len(urls)):
    #         for url in urls:
    #             tasks.append(HttpClient.get_user_data(url))
    #         responses = await asyncio.gather(*tasks)
    #     now_time = TimeUtils.now_iso()
    #     await ServiceMetrics.http_incrby(now_time[:10], len(urls))
    #     error_count, error_return = varify_responses(responses)
    #     if error_count != None:
    #         await ServiceMetrics.http_error_incrby(now_time[:10], error_count)
    #         return error_return
    #     data = []
    #     for response in responses:
    #         if response['data'] is None or response['data'][str(account_id)] == None:
    #             return JSONResponse.API_2011_UserNotExist
    #         if 'hidden_profile' in response['data'][str(account_id)]:
    #             return JSONResponse.API_2015_UserHiddenProfile
    #         if 'statistics' not in response['data'][str(account_id)]:
    #             return JSONResponse.API_2013_UserDataisNone
    #         data.append(response['data'][str(account_id)]['statistics'])
    #     result, record = processing_pvp_data(data,fields,include_old)
    #     return JSONResponse.get_success_response(
    #         {
    #             'original_data': result,
    #             'record': record
    #         }
    #     )
        
    # @staticmethod
    # @ExceptionLogger.handle_program_exception_async
    # async def get_user_cb(account_id: int):
    #     base_url = EnvConfig.endpoints.OFFICIAL_API
    #     api_token = EnvConfig.API_TOKEN
    #     if not base_url or not api_token:
    #         return JSONResponse.API_2007_RegionNotSupported
    #     urls = [
    #         f'{base_url}/wows/clans/seasonstats/?application_id={api_token}&account_id={account_id}',
    #         f'{base_url}/wows/account/achievements/?application_id={api_token}&account_id={account_id}'
    #     ]
    #     tasks = []
    #     responses = []
    #     async with asyncio.Semaphore(len(urls)):
    #         for url in urls:
    #             tasks.append(HttpClient.get_offical_user_data(url))
    #         responses = await asyncio.gather(*tasks)
    #     now_time = TimeUtils.now_iso()
    #     await ServiceMetrics.http_incrby(now_time[:10], len(urls))
    #     error_count, error_return = varify_responses(responses)
    #     if error_count != None:
    #         await ServiceMetrics.http_error_incrby(now_time[:10], error_count)
    #         return error_return
    #     for response in responses:
    #         if response['data']['meta']['hidden'] != None:
    #             return JSONResponse.API_2015_UserHiddenProfile
    #     if responses[0]['data']['data'][str(account_id)] is None:
    #         return JSONResponse.API_2013_UserDataisNone
    #     season_data = processing_cb_seasons(responses[0]['data']['data'][str(account_id)])
    #     achievements = processing_cb_achieve(responses[1]['data']['data'][str(account_id)])
    #     return JSONResponse.get_success_response(
    #         {
    #             'seasons': season_data,
    #             'achievements': achievements
    #         }
    #     )