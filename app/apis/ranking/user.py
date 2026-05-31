from typing import Any, Optional

from app.core import EnvConfig
from app.loggers import ExceptionLogger
from app.response import JSONResponse, ResponseDict
from app.middlewares import RedisClient
from app.models import ShipModel, PlayerModel
from app.schemas import ShipOriginalData
from app.utils import RatingUtils


OriginalData = ShipOriginalData(
    battles_count=0, 
    wins=0, 
    damage_dealt=0, 
    frags=0, 
    original_exp=0, 
    personal_rating=-1, 
    damage_rating=-1, 
    frags_rating=-1
)

class UserRankingAPI:
    @ExceptionLogger.handle_program_exception_async
    async def get_user_ranking(account_id: int, language: str, top_n: int = None) -> ResponseDict:
        """获取指定船只排行榜的分页数据

        Args:
            account_id: 用户ID

        Returns:
            ResponseDict
        """
        error, ship_stats = JSONResponse.extract_data_strict(
            response=await ShipModel.get_ranking_ship_stats()
        )
        if error:
            return ship_stats

        error, user_cache = JSONResponse.extract_data_strict(
            response=await PlayerModel.get_user_cache(account_id)
        )
        if error:
            return user_cache
        
        if user_cache == {}:
            return JSONResponse.API_2022_NoStatisticsData
        
        cached_ships = 0
        total_battles = 0
        ranking_ships = 0
        N_50_ships = 0
        ranking_score = 0

        user_ranking = {}
        for ship_id, ship_cache in user_cache.items():
            cached_ships += 1
            total_battles += ship_cache[0]
            
            ship = ship_stats.get(int(ship_id))
            if ship is None:
                continue
            if ship_cache[0] < ship[0]:
                continue
            
            original_data = ShipOriginalData(
                battles_count=ship_cache[0],
                wins=ship_cache[1],
                damage_dealt=ship_cache[2],
                frags=ship_cache[3],
                original_exp=ship_cache[4],
                personal_rating=-1,
                damage_rating=-1,
                frags_rating=-1
            )

            RatingUtils.calculate_rating(
                'pvp',
                original_data,
                ship[1]
            )

            if original_data['personal_rating'] >= 0:
                ranking_ships += 1
                user_ranking[ship_id] = original_data

        ship_ranking = {}
        for ship_id in user_ranking.keys():
            # 获取用户排名
            ship_ranking_key = f"leaderboard:ship:{ship_id}"
            error, user_rank = JSONResponse.extract_data_strict(
                response=await RedisClient.zget_rank(ship_ranking_key, str(account_id))
            )
            if error:
                return user_rank
            
            if user_rank:
                if user_rank <= 50:
                    N_50_ships += 1
                    ranking_score += (50 - user_rank + 1)
                if top_n:
                    if user_rank > top_n:
                        continue
                ship_ranking[ship_id] = user_rank

        if ship_ranking == {}:
            return JSONResponse.API_2022_NoStatisticsData
        
        error, ship_info = JSONResponse.extract_data_strict(
            response=await ShipModel.get_ship_info(language)
        )
        if error:
            return ship_info
        
        result = {
            'overall': {
                'battles': total_battles,
                'ship_count': cached_ships,
                'in_ranking': ranking_ships,
                'top_50': N_50_ships,
                'score': ranking_score
            },
            'items': []
        }

        for ship_id, ranking in sorted(ship_ranking.items(), key=lambda x: x[1]):
            processed_data = user_ranking.get(ship_id)
            ship_data = {
                'ranking': ranking,
                'battles': '{:,}'.format(processed_data['battles_count']).replace(',', ' '),
                'win_rate': '{:.2f}%'.format(processed_data['wins']/processed_data['battles_count']*100),
                'avg_damage': '{:,}'.format(int(processed_data['damage_dealt']/processed_data['battles_count'])).replace(',', ' '),
                'avg_frags': '{:.2f}'.format(processed_data['frags']/processed_data['battles_count']),
                'avg_exp': '{:,}'.format(int(processed_data['original_exp']/processed_data['battles_count'])).replace(',', ' '),
                'rating': str(int(processed_data['personal_rating'])),
                'next': '1',
                'level': {
                    'rating': 0,
                    'win_rate': 0,
                    'avg_damage': 0,
                    'avg_frags': 0
                },
                'info': ship_info.get(int(ship_id))
            }
            rating_level, rating_next = RatingUtils.get_rating_level(
                rating = int(processed_data['personal_rating'])
            )
            ship_data['next'] = str(rating_next)
            ship_data['level']['rating'] = rating_level
            ship_data['level']['win_rate'] = RatingUtils.get_metric_level(0, processed_data['wins']/processed_data['battles_count']*100)
            ship_data['level']['avg_damage'] = RatingUtils.get_metric_level(1, processed_data['damage_rating']/processed_data['battles_count'])
            ship_data['level']['avg_frags'] = RatingUtils.get_metric_level(2, processed_data['frags_rating']/processed_data['battles_count'])

            result['items'].append(ship_data)
        
        return JSONResponse.get_success_response(result)