from app.core import EnvConfig
from app.response import JSONResponse
from app.loggers import ExceptionLogger
from app.network import ExternalAPI
from app.models import ShipModel, UserStatsSyncer
from app.utils import RatingUtils, DevUtils
from app.middlewares import RedisClient

from .basic import BasicAPI
from .process import format_overall, accumulate_overall
from .schema import OriginalData, ProcessedData


class RandomAPI:
    @ExceptionLogger.handle_program_exception_async
    async def overall(
        account_id: int, 
        filter_type: str, 
        specified_tier: int = None, 
        specified_type: str = None, 
        specified_nation: str = None, 
        include_old: bool = False
    ):
        # 从 Redis 中获取用户的 access_token
        if EnvConfig.DEV_MODE:
            access_token = None
        else:
            redis_key = f"token:ac:{account_id}"
            response = await RedisClient.get_token(redis_key)
            error, access_token = JSONResponse.extract_data_strict(response)
            if error:
                return access_token
        
        error, user_basic = JSONResponse.extract_data_strict(
            response=await BasicAPI.get_user_basic(account_id, access_token)
        )
        if error:
            return user_basic
        
        error, responses = JSONResponse.extract_data_strict(
            response=await ExternalAPI.get_user_pvp_overall(account_id, access_token)
        )
        if error:
            return responses
        
        for response in responses:
            if 'hidden_profile' in response.get(str(account_id)):
                if not EnvConfig.DEV_MODE:
                    error, refresh = JSONResponse.extract_data_strict(
                        response=await UserStatsSyncer.refresh(account_id, {str(account_id): {'hidden_profile': True}})
                    )
                    if error:
                        return refresh
                return JSONResponse.API_2015_UserHiddenProfile
        
        if EnvConfig.DEV_MODE:
            ship_info = DevUtils.read_ship_info()
            ship_stats = DevUtils.read_ship_stats()
        else:
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

        statistics = {
            'overall': {},
            'battle_type': {},
            'ship_type': {},
            'record': {},
            'chart': {}
        }
            
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
        original_ship_mode_data = {
            'pvp_solo': ProcessedData.copy(),
            'pvp_div2': ProcessedData.copy(),
            'pvp_div3': ProcessedData.copy()
        }
        fields = ['pvp_solo', 'pvp_div2', 'pvp_div3']
        for i in range(len(fields)):
            field = fields[i]
            response = responses[i].get(str(account_id)).get('statistics', {})

            for ship_id, ship_data in response.items():
                if not include_old and ship_id in old_ship_ids:
                    continue

                ship_base = ship_info.get(ship_id)
                if ship_base is None:
                    continue

                ship_tier = ship_base[1]
                if specified_tier and ship_tier != specified_tier:
                    continue

                ship_type = ship_base[2]
                if specified_type and ship_type != specified_type:
                    continue

                ship_nation = ship_base[3]
                if specified_nation and ship_nation != specified_nation:
                    continue

                field_data = ship_data.get(field, {})
                if field_data == {}:
                    continue

                if ship_id not in original_data:
                    original_data[ship_id] = OriginalData.copy()
                original_field_data = OriginalData.copy()

                for key in ['battles_count','wins','damage_dealt','frags','original_exp']:
                    original_data[ship_id][key] += field_data[key]
                    original_field_data[key] = field_data[key]

                RatingUtils.calculate_rating('pvp', original_field_data, ship_stats.get(ship_id))
                accumulate_overall(original_ship_mode_data[field], original_field_data)

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
            RatingUtils.calculate_rating('pvp', ship_data, ship_stats.get(ship_id))
            ship_base = ship_info.get(ship_id)
            if ship_base is None:
                continue
            ship_tier = ship_base[1]
            ship_type = ship_base[2]

            original_chart_data[ship_tier-1][ShipTypeIndex[ship_type]] += ship_data['battles_count']
            
            accumulate_overall(original_overall_data, ship_data)
            accumulate_overall(original_ship_type_data[ship_type], ship_data)

        statistics['overall'] = format_overall(original_overall_data, True)
        statistics['battle_type'] = {
            'solo': format_overall(original_ship_mode_data['pvp_solo']),
            'div2': format_overall(original_ship_mode_data['pvp_div2']),
            'div3': format_overall(original_ship_mode_data['pvp_div3'])
        }
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
            'mode': 'Random',
            'type': filter_type,
            'basic': user_basic,
            'statistics': statistics
        }

        return JSONResponse.get_success_response(result)
    
    @ExceptionLogger.handle_program_exception_async
    async def field(
        account_id: int, 
        field: str = None, 
        include_old: bool = False
    ):
        # 从 Redis 中获取用户的 access_token
        if EnvConfig.DEV_MODE:
            access_token = None
        else:
            redis_key = f"token:ac:{account_id}"
            response = await RedisClient.get_token(redis_key)
            error, access_token = JSONResponse.extract_data_strict(response)
            if error:
                return access_token
        
        error, user_basic = JSONResponse.extract_data_strict(
            response=await BasicAPI.get_user_basic(account_id, access_token)
        )
        if error:
            return user_basic
        
        error, response = JSONResponse.extract_data_strict(
            response=await ExternalAPI.get_user_pvp_field(account_id, field, access_token)
        )
        if error:
            return response
        
        if 'hidden_profile' in response.get(str(account_id)):
            if not EnvConfig.DEV_MODE:
                error, refresh = JSONResponse.extract_data_strict(
                    response=await UserStatsSyncer.refresh(account_id, {str(account_id): {'hidden_profile': True}})
                )
                if error:
                    return refresh
            return JSONResponse.API_2015_UserHiddenProfile
    
        if EnvConfig.DEV_MODE:
            ship_info = DevUtils.read_ship_info()
            ship_stats = DevUtils.read_ship_stats()
        else:
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

        statistics = {
            'overall': {},
            'battle_type': {},
            'ship_type': {},
            'record': {},
            'chart': {}
        }
            
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
        original_ship_mode_data = {
            'pvp_solo': ProcessedData.copy(),
            'pvp_div2': ProcessedData.copy(),
            'pvp_div3': ProcessedData.copy()
        }
        response = response.get(str(account_id)).get('statistics', {})

        for ship_id, ship_data in response.items():
            if not include_old and ship_id in old_ship_ids:
                continue

            field_data = ship_data.get(f'pvp_{field}', {})
            if field_data == {}:
                continue

            if ship_id not in original_data:
                original_data[ship_id] = OriginalData.copy()
            original_field_data = OriginalData.copy()

            for key in ['battles_count','wins','damage_dealt','frags','original_exp']:
                original_data[ship_id][key] += field_data[key]
                original_field_data[key] = field_data[key]

            RatingUtils.calculate_rating('pvp', original_field_data, ship_stats.get(ship_id))
            accumulate_overall(original_ship_mode_data[f'pvp_{field}'], original_field_data)

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
            RatingUtils.calculate_rating('pvp', ship_data, ship_stats.get(ship_id))
            ship_base = ship_info.get(ship_id)
            if ship_base is None:
                continue
            ship_tier = ship_base[1]
            ship_type = ship_base[2]

            original_chart_data[ship_tier-1][ShipTypeIndex[ship_type]] += ship_data['battles_count']
            
            accumulate_overall(original_overall_data, ship_data)
            accumulate_overall(original_ship_type_data[ship_type], ship_data)

        statistics['overall'] = format_overall(original_overall_data, True)
        statistics['battle_type'] = {
            'solo': format_overall(original_ship_mode_data['pvp_solo']),
            'div2': format_overall(original_ship_mode_data['pvp_div2']),
            'div3': format_overall(original_ship_mode_data['pvp_div3'])
        }
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
            'mode': 'Random',
            'type': field.upper(),
            'basic': user_basic,
            'statistics': statistics
        }

        return JSONResponse.get_success_response(result)