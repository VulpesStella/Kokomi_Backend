import random
import asyncio

from app.loggers import ExceptionLogger
from app.utils import GameUtils, TimeUtils
from app.constants import ClanColor
from app.models import PlatyerModel
from app.health import ServiceMetrics
from app.core import EnvConfig
from app.schemas import UserBasicData, ClanBaseData

from .client import HttpClient
from .response import JSONResponse
from .processing import (
    processing_user_basic, 
    processing_season,
    processing_pvp_data,
    processing_cb_achieve,
    processing_cb_seasons
)


def varify_responses(responses: list | dict):
    error = 0
    error_return = None
    if type(responses) == list:
        for response in responses:
            if response['code'] != 1000:
                error += 1
                error_return = response
    else:
        if responses['code'] != 1000:
            error = 1
    if error == 0:
        return None, None
    else:
        return error, error_return

class ExternalAPI:
    '''
    对外部的接口
    '''
    @staticmethod
    @ExceptionLogger.handle_program_exception_async
    async def get_user_search(nickname: str, limit: int = 10):
        '''获取用户名称搜索结构

        通过输入的用户名称搜索用户账号

        参数：
            region: 用户服务器
            nickname: 用户名称
            limit: 限制返回结果数量(1-10)，为1表示精准匹配结果
        
        返回：
            结果列表
        '''
        if limit < 1:
            limit = 1
        if limit > 10:
            limit = 10
        nickname = nickname.lower()
        base_url = random.choice(EnvConfig.endpoints.VORTEX_API)
        url = f'{base_url}/api/accounts/search/{nickname.lower()}/?limit={limit}'
        result = await HttpClient.get_user_search(url)
        now_time = TimeUtils.now_iso()
        await ServiceMetrics.http_incrby(now_time[:10], 1)
        error_count, error_return = varify_responses(result)
        if error_count != None:
            await ServiceMetrics.http_error_incrby(now_time[:10], error_count)
            return error_return
        search_data = []
        if limit == 1:
            for temp_data in result.get('data',None):
                if nickname == temp_data['name'].lower():
                    search_data.append({
                        'region': EnvConfig.REGION,
                        'account_id':temp_data['spa_id'],
                        'name':temp_data['name']
                    })
                    break
        else:
            for temp_data in result.get('data',None):
                if len(search_data) > limit:
                    break
                search_data.append({
                    'region': EnvConfig.REGION,
                    'account_id':temp_data['spa_id'],
                    'name':temp_data['name']
                })
        if search_data == []:
            return JSONResponse.API_3010_UserNameNotFound
        else:
            return JSONResponse.get_success_response(search_data)
    
    @staticmethod
    @ExceptionLogger.handle_program_exception_async
    async def get_clan_search(tag: str, limit: int = 10):
        '''
        通过输入的工会名称搜索工会账号

        参数：
            region: 工会服务器
            tga: 工会名称
            limit: 限制返回结果数量(1-10)，为1表示精准匹配结果
        
        返回：
            结果列表
        '''
        if limit < 1:
            limit = 1
        if limit > 10:
            limit = 10
        tag = tag.lower()
        base_url = EnvConfig.endpoints.CLAN_API
        url = f'{base_url}/api/search/autocomplete/?search={tag}&type=clans'
        result = await HttpClient.get_clan_search(url)
        now_time = TimeUtils.now_iso()
        await ServiceMetrics.http_incrby(now_time[:10], 1)
        error_count, error_return = varify_responses(result)
        if error_count != None:
            await ServiceMetrics.http_error_incrby(now_time[:10], error_count)
            return error_return
        search_data = []
        if limit == 1:
            # 精准匹配工会名称
            for temp_data in result.get('data',None):
                if tag == temp_data['tag'].lower():
                    search_data.append({
                        'region': EnvConfig.REGION,
                        'clan_id':temp_data['id'],
                        'tag':temp_data['tag']
                    })
                    break
        else:
            # 提取前10个结果
            for temp_data in result.get('data',None):
                if len(search_data) > limit:
                    break
                if tag in temp_data['tag'].lower():
                    search_data.append({
                        'region': EnvConfig.REGION,
                        'clan_id':temp_data['id'],
                        'tag':temp_data['tag']
                    })
        if search_data == []:
            return JSONResponse.API_3011_ClanNameNotFound
        else:
            return JSONResponse.get_success_response(search_data)

    @staticmethod
    @ExceptionLogger.handle_program_exception_async
    async def varify_ac(account_id: int, ac: str = None):
        """"""
        base_url = random.choice(EnvConfig.endpoints.VORTEX_API)
        url = f'{base_url}/api/accounts/{account_id}/'
        response = await HttpClient.get_user_data(url)
        now_time = TimeUtils.now_iso()
        await ServiceMetrics.http_incrby(now_time[:10], 1)
        error_count, error_return = varify_responses(response)
        if error_count != None:
            await ServiceMetrics.http_error_incrby(now_time[:10], error_count)
            return error_return
        if response['data']:
            user_basic = response['data'][str(account_id)]
        if user_basic == None:
            return JSONResponse.API_3001_UserNotExist
        if 'hidden_profile' not in user_basic:
            return JSONResponse.get_success_response(False)
        url = f'{base_url}/api/accounts/{account_id}/' + (f'?ac={ac}' if ac else '')
        response = await HttpClient.get_user_data(url)
        await ServiceMetrics.http_incrby(now_time[:10], 1)
        error_count, error_return = varify_responses(response)
        if error_count != None:
            await ServiceMetrics.http_error_incrby(now_time[:10], error_count)
            return error_return
        # 刷新数据库数据
        if response['data']:
            user_basic = response['data'][str(account_id)]
        if 'hidden_profile' in user_basic:
            refresh_user_data = UserBasicData(
                account_id=account_id, 
                is_enabled=1,
                is_public=0,
                activity_level=GameUtils.get_activity_level(is_public=0),
                username=user_basic['name']
            )
            result = await PlatyerModel.refresh_base(refresh_user_data)
            if result['code'] != 1000:
                return result
        elif (
            user_basic == None or
            'statistics' not in user_basic or 
            'basic' not in user_basic['statistics'] or 
            user_basic['statistics']['basic']['leveling_points'] == 0
        ):
            result = await PlatyerModel.refresh_base(
                UserBasicData(
                    account_id=account_id, 
                    is_enabled=0,
                    clan=ClanBaseData()
                )
            )
            if result['code'] != 1000:
                return result
        else:
            if EnvConfig.REGION == 'ru':
                ranked_count = 0
                ranked_count += 0 if user_basic['statistics']['rank_solo'] == {} else user_basic['statistics']['rank_solo']['battles_count']
                ranked_count += 0 if user_basic['statistics']['rating_solo'] == {} else user_basic['statistics']['rating_solo']['battles_count']
                ranked_count += 0 if user_basic['statistics']['rating_div'] == {} else user_basic['statistics']['rating_div']['battles_count']
            else:
                ranked_count = 0 if user_basic['statistics']['rank_solo'] == {} else user_basic['statistics']['rank_solo']['battles_count']
            refresh_user_data = UserBasicData(
                account_id=account_id, 
                is_enabled=1,
                is_public=1,
                activity_level=GameUtils.get_activity_level(
                    is_public=1, 
                    total_battles=user_basic['statistics']['basic']['leveling_points'],
                    last_battle_time=user_basic['statistics']['basic']['last_battle_time']
                ),
                username=user_basic['name'],
                register_time=user_basic['statistics']['basic']['created_at'],
                insignias=GameUtils.get_insignias(user_basic['dog_tag']),
                total_battles=user_basic['statistics']['basic']['leveling_points'],
                pvp_battles=0 if user_basic['statistics']['pvp'] == {} else user_basic['statistics']['pvp']['battles_count'],
                ranked_battles=ranked_count,
                last_battle_at=user_basic['statistics']['basic']['last_battle_time']
            )
            result = await PlatyerModel.refresh_base(refresh_user_data)
            if result['code'] != 1000:
                return result
        # 效验用户ac是否有效
        if response['data']:
            user_basic = response['data'][str(account_id)]
        if user_basic == None:
            return JSONResponse.API_3001_UserNotExist
        if 'hidden_profile' not in user_basic:
            return JSONResponse.get_success_response(True)
        else:
            return JSONResponse.get_success_response(False)

    @staticmethod
    @ExceptionLogger.handle_program_exception_async
    async def get_user_base(account_id: int, ac1: str = None):
        """"""
        base_url = random.choice(EnvConfig.endpoints.VORTEX_API)
        url = f'{base_url}/api/accounts/{account_id}/' + (f'?ac={ac1}' if ac1 else '')
        response = await HttpClient.get_user_data(url)
        now_time = TimeUtils.now_iso()
        await ServiceMetrics.http_incrby(now_time[:10], 1)
        error_count, error_return = varify_responses(response)
        if error_count != None:
            await ServiceMetrics.http_error_incrby(now_time[:10], error_count)
            return error_return
        # 刷新数据库数据
        if response['data']:
            user_basic = response['data'][str(account_id)]
        if 'hidden_profile' in user_basic:
            refresh_user_data = UserBasicData(
                account_id=account_id, 
                is_enabled=1,
                is_public=0,
                activity_level=GameUtils.get_activity_level(is_public=0),
                username=user_basic['name']
            )
            result = await PlatyerModel.refresh_base(refresh_user_data)
            if result['code'] != 1000:
                return result
        elif (
            user_basic == None or
            'statistics' not in user_basic or 
            'basic' not in user_basic['statistics'] or 
            user_basic['statistics']['basic']['leveling_points'] == 0
        ):
            result = await PlatyerModel.refresh_base(
                UserBasicData(
                    account_id=account_id, 
                    is_enabled=0,
                    clan=ClanBaseData()
                )
            )
            if result['code'] != 1000:
                return result
        else:
            if EnvConfig.REGION == 'ru':
                ranked_count = 0
                ranked_count += 0 if user_basic['statistics']['rank_solo'] == {} else user_basic['statistics']['rank_solo']['battles_count']
                ranked_count += 0 if user_basic['statistics']['rating_solo'] == {} else user_basic['statistics']['rating_solo']['battles_count']
                ranked_count += 0 if user_basic['statistics']['rating_div'] == {} else user_basic['statistics']['rating_div']['battles_count']
            else:
                ranked_count = 0 if user_basic['statistics']['rank_solo'] == {} else user_basic['statistics']['rank_solo']['battles_count']
            refresh_user_data = UserBasicData(
                account_id=account_id, 
                is_enabled=1,
                is_public=1,
                activity_level=GameUtils.get_activity_level(
                    is_public=1, 
                    total_battles=user_basic['statistics']['basic']['leveling_points'],
                    last_battle_time=user_basic['statistics']['basic']['last_battle_time']
                ),
                username=user_basic['name'],
                register_time=user_basic['statistics']['basic']['created_at'],
                insignias=GameUtils.get_insignias(user_basic['dog_tag']),
                total_battles=user_basic['statistics']['basic']['leveling_points'],
                pvp_battles=0 if user_basic['statistics']['pvp'] == {} else user_basic['statistics']['pvp']['battles_count'],
                ranked_battles=ranked_count,
                last_battle_at=user_basic['statistics']['basic']['last_battle_time']
            )
            result = await PlatyerModel.refresh_base(refresh_user_data)
            if result['code'] != 1000:
                return result
        # 处理数据成需要的返回格式
        if response['data']:
            user_basic = response['data'][str(account_id)]
        if user_basic == None:
            return JSONResponse.API_3001_UserNotExist
        data = {
            'account_id': account_id,
            'username': None,
            'register_time': None,
            'last_battle_time': None,
            'leveling_points': 0
        }
        data['username'] = user_basic['name']
        if (
            'statistics' in user_basic and
            'basic' in user_basic['statistics'] and
            user_basic['statistics']['basic'] != {}
        ):
            data['register_time'] = user_basic['statistics']['basic']['created_at']
            data['last_battle_time'] = user_basic['statistics']['basic']['last_battle_time']
            data['leveling_points'] = user_basic['statistics']['basic']['leveling_points']
        return JSONResponse.get_success_response(data)
         
    @staticmethod
    @ExceptionLogger.handle_program_exception_async
    async def get_user_brief(account_id: int, ac1: str = None):
        base_url = random.choice(EnvConfig.endpoints.VORTEX_API)
        urls = [
            f'{base_url}/api/accounts/{account_id}/' + (f'?ac={ac1}' if ac1 else ''),
            f'{base_url}/api/accounts/{account_id}/clans/'
        ]
        tasks = []
        responses = []
        async with asyncio.Semaphore(len(urls)):
            for url in urls:
                tasks.append(HttpClient.get_user_data(url))
            responses = await asyncio.gather(*tasks)
        now_time = TimeUtils.now_iso()
        await ServiceMetrics.http_incrby(now_time[:10], 2)
        error_count, error_return = varify_responses(responses)
        if error_count != None:
            await ServiceMetrics.http_error_incrby(now_time[:10], error_count)
            return error_return
        # 刷新数据库数据
        if responses[0]['data']:
            user_basic = responses[0]['data'][str(account_id)]
        user_clan = responses[1]['data']
        if 'hidden_profile' in user_basic:
            refresh_user_data = UserBasicData(
                account_id=account_id, 
                is_enabled=1,
                is_public=0,
                activity_level=GameUtils.get_activity_level(is_public=0),
                username=user_basic['name']
            )
            if user_clan and user_clan['clan_id'] != None:
                refresh_clan_data = ClanBaseData(
                    clan_id=user_clan['clan_id'],
                    tag=user_clan['clan']['tag'],
                    league=ClanColor.CLAN_COLOR_INDEX.get(user_clan['clan']['color'], 5)
                )
            else:
                refresh_clan_data = ClanBaseData()
            refresh_user_data.clan = refresh_clan_data
            result = await PlatyerModel.refresh_base(refresh_user_data)
            if result['code'] != 1000:
                return result
        elif (
            user_basic == None or
            'statistics' not in user_basic or 
            'basic' not in user_basic['statistics'] or 
            user_basic['statistics']['basic']['leveling_points'] == 0
        ):
            result = await PlatyerModel.refresh_base(
                UserBasicData(
                    account_id=account_id, 
                    is_enabled=0,
                    clan=ClanBaseData()
                )
            )
            if result['code'] != 1000:
                return result
        else:
            if EnvConfig.REGION == 'ru':
                ranked_count = 0
                ranked_count += 0 if user_basic['statistics']['rank_solo'] == {} else user_basic['statistics']['rank_solo']['battles_count']
                ranked_count += 0 if user_basic['statistics']['rating_solo'] == {} else user_basic['statistics']['rating_solo']['battles_count']
                ranked_count += 0 if user_basic['statistics']['rating_div'] == {} else user_basic['statistics']['rating_div']['battles_count']
            else:
                ranked_count = 0 if user_basic['statistics']['rank_solo'] == {} else user_basic['statistics']['rank_solo']['battles_count']
            refresh_user_data = UserBasicData(
                account_id=account_id, 
                is_enabled=1,
                is_public=1,
                activity_level=GameUtils.get_activity_level(
                    is_public=1, 
                    total_battles=user_basic['statistics']['basic']['leveling_points'],
                    last_battle_time=user_basic['statistics']['basic']['last_battle_time']
                ),
                username=user_basic['name'],
                register_time=user_basic['statistics']['basic']['created_at'],
                insignias=GameUtils.get_insignias(user_basic['dog_tag']),
                total_battles=user_basic['statistics']['basic']['leveling_points'],
                pvp_battles=0 if user_basic['statistics']['pvp'] == {} else user_basic['statistics']['pvp']['battles_count'],
                ranked_battles=ranked_count,
                last_battle_at=user_basic['statistics']['basic']['last_battle_time']
            )
            if user_clan and user_clan['clan_id'] != None:
                refresh_clan_data = ClanBaseData(
                    clan_id=user_clan['clan_id'],
                    tag=user_clan['clan']['tag'],
                    league=ClanColor.CLAN_COLOR_INDEX.get(user_clan['clan']['color'], 5)
                )
            else:
                refresh_clan_data = ClanBaseData()
            refresh_user_data.clan = refresh_clan_data
            result = await PlatyerModel.refresh_base(refresh_user_data)
            if result['code'] != 1000:
                return result
        # 处理数据成需要的返回格式
        if responses[0]['data']:
            user_basic = responses[0]['data'][str(account_id)]
        user_clan = responses[1]['data']
        if user_basic == None:
            return JSONResponse.API_3001_UserNotExist
        data = {
            'account_id': account_id,
            'username': user_basic['name'],
            'register_time': None,
            'insignias': None,
            'clan_id': None,
            'clan_tag': None,
            'clan_league': None
        }
        if user_clan and user_clan['clan_id'] != None:
            data['clan_id'] = user_clan['clan_id']
            data['clan_tag'] = user_clan['clan']['tag']
            data['clan_league'] = ClanColor.CLAN_COLOR_INDEX.get(user_clan['clan']['color'], 5)
        if 'hidden_profile' in user_basic:
            return JSONResponse.get_success_response(data)
        if (
            'statistics' not in user_basic or 
            'basic' not in user_basic['statistics']
        ):
            return JSONResponse.API_3003_UserDataisNone
        data['insignias'] = GameUtils.get_insignias(user_basic['dog_tag'])
        data['register_time'] = user_basic['statistics']['basic']['created_at']
        return JSONResponse.get_success_response(data)
        
    @staticmethod
    @ExceptionLogger.handle_program_exception_async
    async def get_user_basic(account_id: int, ac1: str = None):
        base_url = random.choice(EnvConfig.endpoints.VORTEX_API)
        urls = [
            f'{base_url}/api/accounts/{account_id}/' + (f'?ac={ac1}' if ac1 else ''),
            f'{base_url}/api/accounts/{account_id}/clans/'
        ]
        tasks = []
        responses = []
        async with asyncio.Semaphore(len(urls)):
            for url in urls:
                tasks.append(HttpClient.get_user_data(url))
            responses = await asyncio.gather(*tasks)
        now_time = TimeUtils.now_iso()
        await ServiceMetrics.http_incrby(now_time[:10], 2)
        error_count, error_return = varify_responses(responses)
        if error_count != None:
            await ServiceMetrics.http_error_incrby(now_time[:10], error_count)
            return error_return
        # 刷新数据库数据
        if responses[0]['data']:
            user_basic = responses[0]['data'][str(account_id)]
        user_clan = responses[1]['data']
        if 'hidden_profile' in user_basic:
            refresh_user_data = UserBasicData(
                account_id=account_id, 
                is_enabled=1,
                is_public=0,
                activity_level=GameUtils.get_activity_level(is_public=0),
                username=user_basic['name']
            )
            if user_clan and user_clan['clan_id'] != None:
                refresh_clan_data = ClanBaseData(
                    clan_id=user_clan['clan_id'],
                    tag=user_clan['clan']['tag'],
                    league=ClanColor.CLAN_COLOR_INDEX.get(user_clan['clan']['color'], 5)
                )
            else:
                refresh_clan_data = ClanBaseData()
            refresh_user_data.clan = refresh_clan_data
            result = await PlatyerModel.refresh_base(refresh_user_data)
            if result['code'] != 1000:
                return result
        elif (
            user_basic == None or
            'statistics' not in user_basic or 
            'basic' not in user_basic['statistics'] or 
            user_basic['statistics']['basic']['leveling_points'] == 0
        ):
            result = await PlatyerModel.refresh_base(
                UserBasicData(
                    account_id=account_id, 
                    is_enabled=0,
                    clan=ClanBaseData()
                )
            )
            if result['code'] != 1000:
                return result
        else:
            if EnvConfig.REGION == 'ru':
                ranked_count = 0
                ranked_count += 0 if user_basic['statistics']['rank_solo'] == {} else user_basic['statistics']['rank_solo']['battles_count']
                ranked_count += 0 if user_basic['statistics']['rating_solo'] == {} else user_basic['statistics']['rating_solo']['battles_count']
                ranked_count += 0 if user_basic['statistics']['rating_div'] == {} else user_basic['statistics']['rating_div']['battles_count']
            else:
                ranked_count = 0 if user_basic['statistics']['rank_solo'] == {} else user_basic['statistics']['rank_solo']['battles_count']
            refresh_user_data = UserBasicData(
                account_id=account_id, 
                is_enabled=1,
                is_public=1,
                activity_level=GameUtils.get_activity_level(
                    is_public=1, 
                    total_battles=user_basic['statistics']['basic']['leveling_points'],
                    last_battle_time=user_basic['statistics']['basic']['last_battle_time']
                ),
                username=user_basic['name'],
                register_time=user_basic['statistics']['basic']['created_at'],
                insignias=GameUtils.get_insignias(user_basic['dog_tag']),
                total_battles=user_basic['statistics']['basic']['leveling_points'],
                pvp_battles=0 if user_basic['statistics']['pvp'] == {} else user_basic['statistics']['pvp']['battles_count'],
                ranked_battles=ranked_count,
                last_battle_at=user_basic['statistics']['basic']['last_battle_time']
            )
            if user_clan and user_clan['clan_id'] != None:
                refresh_clan_data = ClanBaseData(
                    clan_id=user_clan['clan_id'],
                    tag=user_clan['clan']['tag'],
                    league=ClanColor.CLAN_COLOR_INDEX.get(user_clan['clan']['color'], 5)
                )
            else:
                refresh_clan_data = ClanBaseData()
            refresh_user_data.clan = refresh_clan_data
            result = await PlatyerModel.refresh_base(refresh_user_data)
            if result['code'] != 1000:
                return result
        # 处理数据成需要的返回格式
        if responses[0]['data']:
            user_basic = responses[0]['data'][str(account_id)]
        user_clan = responses[1]['data']
        if user_basic == None:
            return JSONResponse.API_3001_UserNotExist
        if 'hidden_profile' in user_basic:
            return JSONResponse.API_3005_UserHiddenProfite
        if (
            'statistics' not in user_basic or 
            'basic' not in user_basic['statistics']
        ):
            return JSONResponse.API_3003_UserDataisNone
        data = {
            'basic': {},
            'clan': {},
            'info': {},
            'statistics': {},
            'seasons': {}
        }
        data['basic'] = {
            'id': account_id,
            'name': user_basic['name'],
            'insignias': GameUtils.get_insignias(user_basic['dog_tag'])
        }
        if user_clan and user_clan['clan_id'] != None:
            data['clan'] = {
                'id': user_clan['clan_id'],
                'tag': user_clan['clan']['tag'],
                'league': ClanColor.CLAN_COLOR_INDEX.get(user_clan['clan']['color'], 5)
            }
        user_basic = user_basic['statistics']
        data['info'] = user_basic['basic']
        data['statistics'] = processing_user_basic(user_basic)
        data['seasons'] = processing_season(user_basic['seasons'], user_basic['rank_info'])
        return JSONResponse.get_success_response(data)
        
    @staticmethod
    @ExceptionLogger.handle_program_exception_async
    async def get_user_pvp(account_id: int, ac1: str = None, field: str = 'pvp', include_old: bool = True):
        base_url = random.choice(EnvConfig.endpoints.VORTEX_API)
        if field == 'pvp':
            urls = [
                f'{base_url}/api/accounts/{account_id}/ships/pvp_solo/' + (f'?ac={ac1}' if ac1 else ''),
                f'{base_url}/api/accounts/{account_id}/ships/pvp_div2/' + (f'?ac={ac1}' if ac1 else ''),
                f'{base_url}/api/accounts/{account_id}/ships/pvp_div3/' + (f'?ac={ac1}' if ac1 else '')
            ]
            fields = ['pvp_solo','pvp_div2','pvp_div3']
        else:
            urls = [
                f'{base_url}/api/accounts/{account_id}/ships/{field}/' + (f'?ac={ac1}' if ac1 else '')
            ]
            fields = [field]
        tasks = []
        responses = []
        async with asyncio.Semaphore(len(urls)):
            for url in urls:
                tasks.append(HttpClient.get_user_data(url))
            responses = await asyncio.gather(*tasks)
        now_time = TimeUtils.now_iso()
        await ServiceMetrics.http_incrby(now_time[:10], len(urls))
        error_count, error_return = varify_responses(responses)
        if error_count != None:
            await ServiceMetrics.http_error_incrby(now_time[:10], error_count)
            return error_return
        data = []
        for response in responses:
            if response['data'] is None or response['data'][str(account_id)] == None:
                return JSONResponse.API_3001_UserNotExist
            if 'hidden_profile' in response['data'][str(account_id)]:
                return JSONResponse.API_3005_UserHiddenProfite
            if 'statistics' not in response['data'][str(account_id)]:
                return JSONResponse.API_3003_UserDataisNone
            data.append(response['data'][str(account_id)]['statistics'])
        result, record = processing_pvp_data(data,fields,include_old)
        return JSONResponse.get_success_response(
            {
                'original_data': result,
                'record': record
            }
        )
        
    @staticmethod
    @ExceptionLogger.handle_program_exception_async
    async def get_user_cb(account_id: int):
        base_url = EnvConfig.endpoints.OFFICIAL_API
        config = EnvConfig.config
        if EnvConfig.REGION == 'ru':
            api_token = config.LESTA_API_TOKEN
        else:
            api_token = config.WG_API_TOKEN
        urls = [
            f'{base_url}/wows/clans/seasonstats/?application_id={api_token}&account_id={account_id}',
            f'{base_url}/wows/account/achievements/?application_id={api_token}&account_id={account_id}'
        ]
        tasks = []
        responses = []
        async with asyncio.Semaphore(len(urls)):
            for url in urls:
                tasks.append(HttpClient.get_offical_user_data(url))
            responses = await asyncio.gather(*tasks)
        now_time = TimeUtils.now_iso()
        await ServiceMetrics.http_incrby(now_time[:10], len(urls))
        error_count, error_return = varify_responses(responses)
        if error_count != None:
            await ServiceMetrics.http_error_incrby(now_time[:10], error_count)
            return error_return
        for response in responses:
            if response['data'] is None:
                return JSONResponse.API_3012_FailedToFetchDataFromAPI
            if response['data']['meta']['hidden'] != None:
                return JSONResponse.API_3005_UserHiddenProfite
        if responses[0]['data']['data'][str(account_id)] is None:
            return JSONResponse.API_3003_UserDataisNone
        season_data = processing_cb_seasons(responses[0]['data']['data'][str(account_id)])
        achievements = processing_cb_achieve(responses[1]['data']['data'][str(account_id)])
        return JSONResponse.get_success_response(
            {
                'seasons': season_data,
                'achievements': achievements
            }
        )