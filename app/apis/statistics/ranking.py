import pandas as pd

from app.core import EnvConfig
from app.loggers import ExceptionLogger
from app.response import JSONResponse
from app.models import PlayerModel, ClanModel
from app.utils import NameUtils

class RankingAPI:
    @ExceptionLogger.handle_program_exception_async
    async def get_region_top(ship_id: int):
        csv_path = EnvConfig.DATA_DIR / 'ranking' / f'{EnvConfig.REGION}_{ship_id}.csv'
        if csv_path.exists() is None:
            return JSONResponse.API_1000_Success
        ship_info = NameUtils.get_ship(ship_id)
        if ship_info is None:
            return JSONResponse.API_1000_Success
        ship_tier = ship_info['tier']
        if ship_tier <= 5:
            return JSONResponse.API_1000_Success
        df = pd.read_csv(csv_path, nrows=50)
        account_ids = df['account_id'].tolist()
        result = await PlayerModel.get_user_name_batch(account_ids)
        if result['code'] != 1000:
            return result
        user_map = result['data']
        result = await ClanModel.get_clan_tag_batch()
        if result['code'] != 1000:
            return result
        clan_map = result['data']
        result = {
            'basic': {
                'region': EnvConfig.REGION,
                'limit': EnvConfig.constants.BATTLES_LIMIT.get(str(ship_tier)),
                'mtime': int(csv_path.stat().st_mtime)
            },
            'info': ship_info,
            'data': []
        }
        for _, row in df.iterrows():
            account_id = int(row.iloc[1])
            user_data = user_map.get(account_id)
            clan_id = user_data[1] if user_data else None
            clan_data = clan_map.get(clan_id) if clan_id else None
            temp_data = {
                'rank': row.iloc[0],
                'clan_id': clan_id,
                'account_id': account_id,
                'clan_tag': clan_data[0] if clan_data else None,
                'user_name': user_data[0] if user_data else f'User_{account_id}',
                
                'battles': row.iloc[2],
                
                'rating': row.iloc[3],
                'rating_delta': row.iloc[4],

                'win_rate': row.iloc[5], 
                'solo_rate': row.iloc[6], 
                'avg_damage': row.iloc[7], 
                'avg_frags': row.iloc[8], 
                'avg_exp': row.iloc[9], 
                'max_exp': row.iloc[10], 
                'max_damage': row.iloc[11], 

                'field_color_index': {
                    'rating': row.iloc[12],
                    'win_rate': row.iloc[13], 
                    'solo_rate': row.iloc[14], 
                    'avg_damage': row.iloc[15], 
                    'avg_frags': row.iloc[16], 
                }
            }
            result['data'].append(temp_data)
        return JSONResponse.get_success_response(result)