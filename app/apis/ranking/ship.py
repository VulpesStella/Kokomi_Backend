from typing import Any, Optional

from app.core import EnvConfig
from app.loggers import ExceptionLogger
from app.response import JSONResponse, ResponseDict
from app.middlewares import RedisClient
from app.models import ShipModel, PlayerModel, RankingModel


class ShipRankingAPI:
    @staticmethod
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

        return leaderboard

    @classmethod
    async def _get_ship_ids(cls) -> tuple[Optional[Any], Optional[dict]]:
        """获取所有参与排行的船只ID列表

        Returns:
            (error, ship_ids): error为None时ship_ids有效，否则ship_ids为错误响应
        """
        error, ship_ids = JSONResponse.extract_data_strict(
            response=await ShipModel.get_ranking_ship_ids()
        )
        return error, ship_ids

    @classmethod
    async def _get_ship_info(cls, ship_id: int) -> tuple[Optional[Any], Optional[dict]]:
        """获取船只详细信息

        Args:
            ship_id: 船只ID

        Returns:
            (error, ship_info): error为None时ship_info有效，否则ship_info为错误响应
        """
        error, ship_info = JSONResponse.extract_data_strict(
            response=await ShipModel.get_ship_info(ship_id)
        )
        return error, ship_info

    @classmethod
    async def _get_updated_at(cls) -> tuple[Optional[Any], Optional[str]]:
        """获取排行榜最后更新时间

        Returns:
            (error, updated_at): error为None时updated_at有效，否则updated_at为错误响应
        """
        error, updated_at = JSONResponse.extract_data_strict(
            response=await RedisClient.get("leaderboard:ship_update_time")
        )
        return error, updated_at

    @classmethod
    @ExceptionLogger.handle_program_exception_async
    async def get_ship_ranking(cls, ship_id: int, page_index: int = 1, page_size: int = 50) -> ResponseDict:
        """获取指定船只排行榜的分页数据

        Args:
            ship_id: 船只ID
            page_index: 页码，从1开始
            page_size: 每页数量

        Returns:
            ResponseDict
        """

        # 1. 获取并验证符合条件的船只ID列表
        error, ship_ids = await cls._get_ship_ids()
        if error:
            return ship_ids

        # 船只不存在排行榜中，返回空数据
        if ship_id not in ship_ids:
            return JSONResponse.API_1000_Success

        # 2. 获取缓存更新时间
        error, updated_at = await cls._get_updated_at()
        if error:
            return updated_at

        # 3. 获取船只详细信息
        error, ship_info = await cls._get_ship_info(ship_id)
        if error:
            return ship_info

        # 4. 计算分页起始和结束索引
        ship_ranking_key = f"leaderboard:ship:{ship_id}"
        start = (page_index - 1) * page_size
        stop = start + page_size - 1
        
        # 检测是否处于维护状态
        maintenance_key = 'leaderboard:maintenance'
        error, maintenance = JSONResponse.extract_data_strict(
            response=await RedisClient.get(maintenance_key)
        )
        if error:
            return maintenance
        
        if maintenance:
            return JSONResponse.API_2018_LeaderboardUnderMaintenance

        # 5. 获取排行榜总人数
        error, total_users = JSONResponse.extract_data_strict(
            response=await RedisClient.zget_total(ship_ranking_key)
        )
        if error:
            return total_users
        
        # 起始索引超过总人数时的处理
        if start >= total_users:
            return JSONResponse.API_1000_Success

        # 7. 获取当前页的用户ID列表
        error, page_user_ids = JSONResponse.extract_data_strict(
            response=await RedisClient.zget_range(ship_ranking_key, start, stop)
        )
        if error:
            return page_user_ids

        if not page_user_ids:
            return JSONResponse.API_1000_Success

        # 8. 批量获取用户详情数据
        error, users_data = JSONResponse.extract_data_strict(
            response=await RankingModel.get_ship_leaderboard(ship_id, page_user_ids)
        )
        if error:
            return users_data

        # 9. 构建返回数据
        total_pages = (total_users + page_size - 1) // page_size
        data = {
            'page': {
                'index': page_index,
                'size': page_size,
                'total': total_pages
            },
            'info': {
                'region': EnvConfig.REGION,
                'limit': ship_ids.get(ship_id, 40),
                'users': total_users,
                'updated_at': updated_at
            },
            'ship': ship_info,
            'datas': cls._build_leaderboard(
                start + 1,
                page_user_ids,
                users_data
            )
        }

        return JSONResponse.get_success_response(data)

    @classmethod
    @ExceptionLogger.handle_program_exception_async
    async def get_ship_user_ranking(cls, ship_id: int, account_id: int, page_size: int = 50) -> ResponseDict:
        """获取指定用户在船只排行榜中的排名及所在页数据

        Args:
            ship_id: 船只ID
            account_id: 用户账号ID
            page_size: 每页数量

        Returns:
            ResponseDict
        """
        error, record = JSONResponse.extract_data_strict(
            response=await PlayerModel.record_query(account_id)
        )
        if error:
            return record

        # 1. 获取并验证符合条件的船只ID列表
        error, ship_ids = await cls._get_ship_ids()
        if error:
            return ship_ids

        if ship_id not in ship_ids:
            return JSONResponse.API_1000_Success
        
        # 检测是否处于维护状态
        maintenance_key = 'leaderboard:maintenance'
        error, maintenance = JSONResponse.extract_data_strict(
            response=await RedisClient.get(maintenance_key)
        )
        if error:
            return maintenance
        
        if maintenance:
            return JSONResponse.API_2018_LeaderboardUnderMaintenance

        # 2. 获取用户排名
        ship_ranking_key = f"leaderboard:ship:{ship_id}"
        error, user_rank = JSONResponse.extract_data_strict(
            response=await RedisClient.zget_rank(ship_ranking_key, str(account_id))
        )
        if error:
            return user_rank

        # 用户不存在于排行榜中
        if user_rank is None:
            return JSONResponse.API_1000_Success

        # 3. 获取排行榜总人数
        error, total_users = JSONResponse.extract_data_strict(
            response=await RedisClient.zget_total(ship_ranking_key)
        )
        if error:
            return total_users

        # 4. 计算用户所在页码及该页的起止索引
        rank = int(user_rank) + 1
        page_index = (user_rank // page_size) + 1
        start = (page_index - 1) * page_size
        stop = start + page_size - 1

        # 5. 获取所在页的用户ID列表
        error, page_user_ids = JSONResponse.extract_data_strict(
            response=await RedisClient.zget_range(ship_ranking_key, start, stop)
        )
        if error:
            return page_user_ids

        if not page_user_ids:
            return JSONResponse.API_1000_Success
        
        # 6. 获取缓存更新时间
        error, updated_at = await cls._get_updated_at()
        if error:
            return updated_at

        # 7. 获取船只详细信息
        error, ship_info = await cls._get_ship_info(ship_id)
        if error:
            return ship_info

        # 8. 获取用户详情数据
        error, users_data = JSONResponse.extract_data_strict(
            response=await RankingModel.get_ship_leaderboard(ship_id, page_user_ids)
        )
        if error:
            return users_data

        # 8. 构建返回数据
        total_pages = (total_users + page_size - 1) // page_size
        data = {
            'page': {
                'index': page_index,
                'size': page_size,
                'total': total_pages
            },
            'info': {
                'region': EnvConfig.REGION,
                'limit': ship_ids.get(ship_id, 40),
                'users': total_users,
                'rank': rank,
                'updated_at': updated_at
            },
            'ship': ship_info,
            'datas': cls._build_leaderboard(
                start + 1,
                page_user_ids,
                users_data
            )
        }

        return JSONResponse.get_success_response(data)
