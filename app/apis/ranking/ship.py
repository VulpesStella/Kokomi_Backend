from typing import Any

from app.core import EnvConfig
from app.loggers import ExceptionLogger
from app.response import JSONResponse
from app.middlewares import RedisClient
from app.models import ShipModel, PlayerModel


class ShipRankingAPI:
    PAGE_SIZE = 50
    CACHE_EXPIRE = 2 * 60  # 2分钟

    @staticmethod
    async def _get_ranking_base_data(ship_id: int, is_specify: bool) -> tuple[bool, Any]:
        ok, ship_ids = JSONResponse.extract_data(
            response=await ShipModel.get_ranking_ship_ids()
        )
        if not ok:
            return False, ship_ids

        if ship_id not in ship_ids:
            return False, JSONResponse.API_2018_ShipNotQualifiedForRanking

        ok, updated_at = JSONResponse.extract_data(
            response=await RedisClient.get("leaderboard:update_time")
        )
        if not ok:
            return False, updated_at

        ok, ship_info = JSONResponse.extract_data(
            response=await ShipModel.get_ship_info(ship_id)
        )
        if not ok:
            return False, ship_info

        constants = EnvConfig.get_constants()
        if is_specify:
            ranking_data = {
                'page': 0,
                'info': {
                    'region': EnvConfig.REGION,
                    'limit': constants.RANKING_BATTLES_LIMIT.get(
                        str(ship_info['tier']),
                        0
                    ),
                    'updated_at': updated_at
                },
                'ship': ship_info,
                'rank': 0,
                'datas': []
            }
        else:
            ranking_data = {
                'page': 0,
                'info': {
                    'region': EnvConfig.REGION,
                    'limit': constants.RANKING_BATTLES_LIMIT.get(
                        str(ship_info['tier']),
                        0
                    ),
                    'updated_at': updated_at
                },
                'ship': ship_info,
                'datas': []
            }
        return True, ranking_data

    @staticmethod
    async def _build_leaderboard(ship_id: int, user_ids: list[str], start_rank: int):
        ok, users_data = JSONResponse.extract_data(
            response=await PlayerModel.fetch_leaderboard_data(ship_id, user_ids)
        )
        if not ok:
            return False, users_data

        leaderboard = []
        for offset, user_id in enumerate(user_ids):
            user_detail = users_data.get(user_id, {})
            if user_detail.get('clan_tag'):
                user_clan = {
                    'tag': user_detail.get('clan_tag', ''),
                    'league': user_detail.get('league', 0)
                }
            else:
                user_clan = None

            leaderboard.append({
                'rank': start_rank + offset,
                'username': user_detail.get('username', ''),
                'clan': user_clan,
                'battles': user_detail.get('battles', 0),
                'rating': int(user_detail.get('rating', 0)),
                'win_rate': user_detail.get('win_rate', 0.0),
                'solo_rate': user_detail.get('solo_rate', 0.0),
                'avg_damage': user_detail.get('avg_damage', 0),
                'avg_frags': user_detail.get('avg_frags', 0.0),
                'avg_exp': user_detail.get('avg_exp', 0),
                'hit_ratio': user_detail.get('hit_ratio', 0.0),
                'level': {
                    'rating': user_detail.get('rating_level', 1),
                    'win_rate': user_detail.get('win_rate_level', 1),
                    'solo_rate': user_detail.get('solo_rate_level', 1),
                    'avg_damage': user_detail.get('avg_damage_level', 1),
                    'avg_frags': user_detail.get('avg_frags_level', 1)
                },
                'max': {
                    'exp': user_detail.get('max_exp', 0),
                    'damage': user_detail.get('max_damage', 0)
                }
            })

        return True, leaderboard

    @ExceptionLogger.handle_program_exception_async
    async def get_ship_ranking(ship_id: int, page: int = 1):
        """获取指定船只排行榜指定页的数据，每页 50 条"""

        ok, ranking_data = await ShipRankingAPI._get_ranking_base_data(ship_id, False)
        if not ok:
            return ranking_data

        if page <= 0:
            page = 1

        # 查缓存
        cache_key = f'leaderboard:cache:{ship_id}_{page}'
        ok, cached_data = JSONResponse.extract_data(
            response=await RedisClient.get(cache_key)
        )
        if ok and cached_data:
            return JSONResponse.get_success_response(cached_data)

        # 缓存未命中，走数据库
        ship_ranking_key = f"leaderboard:ship:{ship_id}"
        start = (page - 1) * ShipRankingAPI.PAGE_SIZE
        stop = start + ShipRankingAPI.PAGE_SIZE - 1

        ok, page_user_ids = JSONResponse.extract_data(
            response=await RedisClient.zget_range(ship_ranking_key, start, stop)
        )
        if not ok:
            return page_user_ids

        if not page_user_ids:
            return JSONResponse.API_2019_NoRankingDataForShip

        ok, leaderboard = await ShipRankingAPI._build_leaderboard(
            ship_id,
            page_user_ids,
            start + 1
        )
        if not ok:
            return leaderboard

        ranking_data['page'] = page
        ranking_data['datas'] = leaderboard

        # 写缓存
        await RedisClient.set(cache_key, ranking_data, ShipRankingAPI.CACHE_EXPIRE)

        return JSONResponse.get_success_response(ranking_data)

    @ExceptionLogger.handle_program_exception_async
    async def get_ship_user_ranking(ship_id: int, account_id: int):
        """获取指定用户在某个船只排行榜中的排名及所在页数据"""

        ok, ranking_data = await ShipRankingAPI._get_ranking_base_data(ship_id, True)
        if not ok:
            return ranking_data

        ship_ranking_key = f"leaderboard:ship:{ship_id}"
        ok, user_rank = JSONResponse.extract_data(
            response=await RedisClient.zget_rank(ship_ranking_key, str(account_id))
        )
        if not ok:
            return user_rank

        if user_rank is None:
            return JSONResponse.API_2020_NoRankingDataForUser

        rank = user_rank + 1
        page = (user_rank // ShipRankingAPI.PAGE_SIZE) + 1
        start = (page - 1) * ShipRankingAPI.PAGE_SIZE
        stop = start + ShipRankingAPI.PAGE_SIZE - 1

        ok, page_user_ids = JSONResponse.extract_data(
            response=await RedisClient.zget_range(ship_ranking_key, start, stop)
        )
        if not ok:
            return page_user_ids

        if not page_user_ids:
            return JSONResponse.API_2019_NoRankingDataForShip

        ok, leaderboard = await ShipRankingAPI._build_leaderboard(
            ship_id,
            page_user_ids,
            start + 1
        )
        if not ok:
            return leaderboard

        ranking_data['rank'] = rank
        ranking_data['page'] = page
        ranking_data['datas'] = leaderboard
        
        return JSONResponse.get_success_response(ranking_data)
