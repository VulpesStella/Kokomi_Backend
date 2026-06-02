from app.core import EnvConfig
from app.response import JSONResponse
from app.loggers import ExceptionLogger
from app.network import ExternalAPI
from app.models import PlayerModel, ShipModel, UserStatsSyncer
from app.utils import RatingUtils, DevUtils
from app.middlewares import RedisClient

from .basic import BasicAPI
from .process import format_overall, accumulate_overall
from .schema import OriginalData, ProcessedData


class RankedAPI:
    @ExceptionLogger.handle_program_exception_async
    async def overall(
        account_id: int, 
        include_old: bool = False
    ):
        # Credits 消耗
        credits_spent = 1

        if EnvConfig.DEV_MODE:
            # 跳过读取 token 步骤
            access_token = None
        else:
            # 从 Redis 中获取用户的 access_token
            redis_key = f"token:ac:{account_id}"
            response = await RedisClient.get_token(redis_key)
            error, access_token = JSONResponse.extract_data_strict(response)
            if error:
                return access_token
        
        # 读取用户的基本信息（name, clan等）
        if EnvConfig.DEV_MODE:
            # 跳过读取数据库步骤，后续直接请求 API 获取数据
            user = None
        else:
            # 先读数据库，读不到数据再请求
            error, user = JSONResponse.extract_data_strict(
                response=await PlayerModel.get_user_name_and_clan(account_id)
            )
            if error:
                return user
            
        # 通过 API 接口读取用户的基本信息：
        # 1. 没有读取到用户的缓存数据
        # 2. 用户的缓存数据表示该用户可能隐藏战绩或无数据
        if user is None or not user['stats']:
            error, user_basic = JSONResponse.extract_data_strict(
                response=await BasicAPI.get_user_basic(account_id, access_token)
            )
            if error:
                return user_basic
            
            credits_spent += 1
        else:
            user_basic = user['basic']
        
        # 读取用户的排位信息
        error, response = JSONResponse.extract_data_strict(
            response=await ExternalAPI.get_user_ranked(account_id, access_token)
        )
        if error:
            return response
        
        credits_spent += 1
        
        # 处理可能的隐藏战绩情况
        # 用户在缓存中的数据表示该用户是公开战绩导致了跳过更新流程
        if 'hidden_profile' in response.get(str(account_id)):
            if not EnvConfig.DEV_MODE:
                # 将用户的缓存数据刷新为隐藏战绩
                error, refresh = JSONResponse.extract_data_strict(
                    response=await UserStatsSyncer.refresh(account_id, {str(account_id): {'hidden_profile': True}})
                )
                if error:
                    return refresh
            return JSONResponse.API_2015_UserHiddenProfile
    
        if EnvConfig.DEV_MODE:
            # 从本地的初始化文件中读取船只数据
            ship_info = DevUtils.read_ship_info()
            ship_stats = DevUtils.read_ship_stats()
        else:
            # 从数据库中读取船只数据
            error, ship_info = JSONResponse.extract_data_strict(
                response=await ShipModel.get_ship_base()
            )
            if error:
                return ship_info
            error, ship_stats = JSONResponse.extract_data_strict(
                response=await ShipModel.get_ship_stats()
            )
            if error:
                return ship_stats

        # 统计数据
        statistics = {
            'overall': {},
            'ship_type': {},
            'record': {},
            'chart': {}
        }
            
        # 筛选出 OLD 船只 ID 列表
        old_ship_ids = []
        for ship_id, ship_base in ship_info.items():
            if ship_base[0]:
                old_ship_ids.append(ship_id)

        # 将 API 数据进行初步筛选、处理、计算
        original_data = {}
        record = {
            'max_damage_dealt': 0,
            'max_frags': 0,
            'max_exp': 0,
            'max_planes_killed': 0,
            'max_scouting_damage': 0,
            'max_total_agro': 0
        }
        response = response.get(str(account_id)).get('statistics', {})

        for ship_id, ship_data in response.items():
            # 如果用户设置排除 OLD 船只，则跳过
            if not include_old and ship_id in old_ship_ids:
                continue

            field_data = ship_data.get('rank_solo', {})
            if field_data == {}:
                continue

            if ship_id not in original_data:
                original_data[ship_id] = OriginalData.copy()

            # 筛选出需要的基本数据
            for key in ['battles_count','wins','damage_dealt','frags','original_exp']:
                original_data[ship_id][key] = field_data[key]

            # 记录 Record 数据
            for key in ['max_damage_dealt','max_frags','max_exp','max_planes_killed','max_scouting_damage','max_total_agro']:
                if field_data[key] > record[key]:
                    record[key] = field_data[key]
        
        if original_data == {}:
            return JSONResponse.API_2022_NoStatisticsData

        ShipTypeIndex = {
            'AirCarrier': 0,
            'Battleship': 1,
            'Cruiser': 2,
            'Destroyer': 3,
            'Submarine': 4
        }
        original_chart_data = [[0,0,0,0,0] for _ in range(11)]
        original_overall_data = ProcessedData.copy()
        original_ship_type_data = {
            'AirCarrier': ProcessedData.copy(),
            'Battleship': ProcessedData.copy(),
            'Cruiser': ProcessedData.copy(),
            'Destroyer': ProcessedData.copy(),
            'Submarine': ProcessedData.copy()
        }

        for ship_id, ship_data in original_data.items():
            # 计算 Rating
            RatingUtils.calculate_rating('rank', ship_data, ship_stats.get(ship_id))
            ship_base = ship_info.get(ship_id)
            if ship_base is None:
                continue
            ship_tier = ship_base[1]
            ship_type = ship_base[2]

            # 将每一艘船只数据按其等级或者类型进行累加
            original_chart_data[ship_tier-1][ShipTypeIndex[ship_type]] += ship_data['battles_count']
            accumulate_overall(original_overall_data, ship_data)
            accumulate_overall(original_ship_type_data[ship_type], ship_data)

        # 将累加后的数据进行数据格式化
        statistics['overall'] = format_overall(original_overall_data, True)
        statistics['ship_type'] = {
            'AirCarrier': format_overall(original_ship_type_data['AirCarrier']),
            'Battleship': format_overall(original_ship_type_data['Battleship']),
            'Cruiser': format_overall(original_ship_type_data['Cruiser']),
            'Destroyer': format_overall(original_ship_type_data['Destroyer']),
            'Submarine': format_overall(original_ship_type_data['Submarine'])
        }
        statistics['record'] = {
            'damage': '{:,}'.format(record['max_damage_dealt']).replace(',', ' '),
            'exp': '{:,}'.format(record['max_exp']).replace(',', ' '),
            'frags': '{:,}'.format(record['max_frags']).replace(',', ' '),
            'planes': '{:,}'.format(record['max_planes_killed']).replace(',', ' '),
            'scout': '{:,}'.format(record['max_scouting_damage']).replace(',', ' '),
            'potent': '{:,}'.format(record['max_total_agro']).replace(',', ' ')
        }
        statistics['chart'] = original_chart_data

    
        result = {
            'mode': 'Ranked',
            'type': 'Overall',
            'basic': user_basic,
            'statistics': statistics,
            'credits_spent': credits_spent
        }
        return JSONResponse.get_success_response(result)
    