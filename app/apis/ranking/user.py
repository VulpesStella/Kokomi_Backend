from typing import Any, Optional

from app.core import EnvConfig
from app.loggers import ExceptionLogger
from app.response import JSONResponse, ResponseDict
from app.middlewares import RedisClient
from app.models import ShipModel, PlayerModel, RankingModel
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
    def _build_leaderboard(start_rank: int, user_ids: list, users_data: dict) -> list[dict]:
        """构建排行榜数据列表

        Args:
            start_rank: 起始排名（1-based）
            user_ids: 用户ID列表（按排名顺序）
            users_data: 用户详情数据字典

        Returns:
            排行榜数据列表，每个元素包含排名、用户信息、战绩数据等
        """
        leaderboard = []
        for offset, user_id in enumerate(user_ids):
            user_detail = users_data.get(user_id, {})
            
            # 构建公会信息（如果有）
            user_clan = None
            if user_detail.get('clan_id'):
                user_clan = {
                    'id': user_detail.get('clan_id'),
                    'tag': user_detail.get('clan_tag', ''),
                    'league': user_detail.get('league', 0)
                }

            leaderboard.append({
                'rank': start_rank + offset,  # 计算实际排名
                'user_id': int(user_id),
                'username': user_detail.get('username', ''),
                'clan': user_clan,
                'battles': user_detail.get('battles', 0),
                'rating': int(user_detail.get('rating', 0)),
                'win_rate': user_detail.get('win_rate', 0.0),
                'avg_damage': user_detail.get('avg_damage', 0),
                'avg_frags': user_detail.get('avg_frags', 0.0),
                'avg_exp': user_detail.get('avg_exp', 0),
                'hit_ratio': user_detail.get('hit_ratio', 0.0),
                'level': {
                    'rating': user_detail.get('rating_level', 1),
                    'win_rate': user_detail.get('win_rate_level', 1),
                    'avg_damage': user_detail.get('avg_damage_level', 1),
                    'avg_frags': user_detail.get('avg_frags_level', 1)
                },
                'max': {
                    'exp': user_detail.get('max_exp', 0),
                    'damage': user_detail.get('max_damage', 0)
                }
            })

        return leaderboard

    @classmethod
    @ExceptionLogger.handle_program_exception_async
    async def get_user_ship_ranking(cls, ship_id: int, account_id: int, language: str, page_size: int = 50) -> ResponseDict:
        """获取指定用户在船只排行榜中的排名及所在页数据

        Args:
            ship_id: 船只ID
            account_id: 用户账号ID
            page_size: 每页数量

        Returns:
            ResponseDict
        """
        error, record = JSONResponse.extract_data(
            response=await PlayerModel.record_query(account_id)
        )
        if error:
            return record
        
        error, user = JSONResponse.extract_data(
            response=await PlayerModel.get_user_name_and_clan(account_id)
        )
        if error:
            return user
            
        if user is None:
            return JSONResponse.API_1000_Success
            
        user_basic = user['basic']

        # 获取并验证符合条件的船只ID列表
        error, ship_ids = JSONResponse.extract_data(
            response=await ShipModel.get_ranking_ship_ids()
        )
        if error:
            return ship_ids

        if ship_id not in ship_ids:
            return JSONResponse.API_1000_Success

        # 获取用户排名
        ship_ranking_key = f"leaderboard:ship:{ship_id}"
        error, user_rank = JSONResponse.extract_data(
            response=await RedisClient.zget_rank(ship_ranking_key, str(account_id))
        )
        if error:
            return user_rank

        # 用户不存在于排行榜中
        if user_rank is None:
            return JSONResponse.API_1000_Success

        # 获取排行榜总人数
        error, total_users = JSONResponse.extract_data(
            response=await RedisClient.zget_total(ship_ranking_key)
        )
        if error:
            return total_users

        # 计算用户所在页码及该页的起止索引
        rank = int(user_rank) + 1
        page_index = (user_rank // page_size) + 1
        start = (page_index - 1) * page_size
        stop = start + page_size - 1

        # 获取所在页的用户ID列表
        error, page_user_ids = JSONResponse.extract_data(
            response=await RedisClient.zget_range(ship_ranking_key, start, stop)
        )
        if error:
            return page_user_ids

        if not page_user_ids:
            return JSONResponse.API_1000_Success

        # 获取船只详细信息
        error, ship_info = JSONResponse.extract_data(
            response=await ShipModel.get_ship_info_by_id(ship_id, language)
        )
        if error:
            return ship_info

        # 获取用户详情数据
        error, users_data = JSONResponse.extract_data(
            response=await RankingModel.get_ship_leaderboard(ship_id, page_user_ids)
        )
        if error:
            return users_data

        data = {
            'basic': user_basic,
            'info': {
                'region': EnvConfig.REGION,
                'limit': ship_ids.get(ship_id, 40),
                'users': total_users,
                'rank': rank
            },
            'ship': ship_info,
            'rows': cls._build_leaderboard(
                start + 1,
                page_user_ids,
                users_data
            )
        }

        return JSONResponse.success(data)
    
    @ExceptionLogger.handle_program_exception_async
    async def get_user_ranking_summary(account_id: int, language: str, top_n: int = None) -> ResponseDict:
        """获取指定船只排行榜的分页数据

        Args:
            account_id: 用户ID

        Returns:
            ResponseDict
        """
        error, ship_stats = JSONResponse.extract_data(
            response=await ShipModel.get_ranking_ship_stats()
        )
        if error:
            return ship_stats

        error, user_cache = JSONResponse.extract_data(
            response=await PlayerModel.get_user_cache(account_id)
        )
        if error:
            return user_cache
        
        if user_cache == {}:
            return JSONResponse.API_NoStatisticsData
        
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
            error, user_rank = JSONResponse.extract_data(
                response=await RedisClient.zget_rank(ship_ranking_key, str(account_id))
            )
            if error:
                return user_rank
            
            if user_rank:
                if user_rank <= 49:
                    N_50_ships += 1
                    ranking_score += (50 - user_rank)
                if top_n:
                    if user_rank + 1 > top_n:
                        continue
                ship_ranking[ship_id] = user_rank + 1

        if ship_ranking == {}:
            return JSONResponse.API_NoStatisticsData
        
        error, ship_info = JSONResponse.extract_data(
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
        
        return JSONResponse.success(result)