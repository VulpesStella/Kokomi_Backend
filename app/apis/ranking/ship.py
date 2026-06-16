from typing import List, Dict, Any
from dataclasses import dataclass, field

from app.core import EnvConfig
from app.loggers import ExceptionLogger
from app.response import JSONResponse, ResponseDict
from app.middlewares import RedisClient
from app.models import ShipModel, RankingModel

@dataclass
class ShipLeaderboardResponse:
    """排行榜响应数据结构"""
    meta: Dict[str, Any] = field(default_factory=dict)
    rows: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'meta': self.meta,
            'rows': self.rows
        }

class ShipRankingAPI:
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
                'username': user_detail.get('username', f'User_{user_id}'),
                'clan': user_clan,
                'battles': user_detail.get('battles', 0),
                'rating': int(user_detail.get('rating', 0)),
                'win_rate': user_detail.get('win_rate', 0.0),
                'avg_damage': user_detail.get('avg_damage', 0),
                'avg_frags': user_detail.get('avg_frags', 0.0),
                'avg_exp': user_detail.get('avg_exp', 0),
                'hit_ratio': user_detail.get('hit_ratio', 0.0),
                'level': {
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
    async def get_ship_ranking(
        cls, 
        ship_id: int, 
        page_index: int = 1, 
        page_size: int = 50
    ) -> ResponseDict:
        """获取指定船只排行榜的分页数据

        Args:
            ship_id: 船只ID
            page_index: 页码，从1开始
            page_size: 每页数量

        Returns:
            ResponseDict
        """

        # 获取并验证符合条件的船只ID列表
        error, ship_ids = JSONResponse.extract_data(
            response=await ShipModel.get_ranking_ship_ids()
        )
        if error:
            return ship_ids

        # 船只不存在排行榜中，返回空数据
        if ship_id not in ship_ids:
            return JSONResponse.API_1000_Success

        # 计算分页起始和结束索引
        ship_ranking_key = f"leaderboard:ship:{ship_id}"
        start = (page_index - 1) * page_size
        stop = start + page_size - 1

        # 获取排行榜总人数
        error, total_users = JSONResponse.extract_data(
            response=await RedisClient.zget_total(ship_ranking_key)
        )
        if error:
            return total_users
        
        # 起始索引超过总人数时的处理
        if start >= total_users:
            return JSONResponse.API_1000_Success

        # 获取当前页的用户ID列表
        error, page_user_ids = JSONResponse.extract_data(
            response=await RedisClient.zget_range(ship_ranking_key, start, stop)
        )
        if error:
            return page_user_ids

        if not page_user_ids:
            return JSONResponse.API_1000_Success

        # 批量获取用户详情数据
        error, users_data = JSONResponse.extract_data(
            response=await RankingModel.get_ship_leaderboard(ship_id, page_user_ids)
        )
        if error:
            return users_data

        data = ShipLeaderboardResponse(
            meta={
                'region': EnvConfig.REGION,
                'limit': ship_ids.get(ship_id, 40),
                'users': total_users
            },
            rows=cls._build_leaderboard(start + 1, page_user_ids, users_data)
        )

        return JSONResponse.success(data.to_dict())