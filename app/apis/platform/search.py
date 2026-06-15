from typing import List, Dict, Any
from dataclasses import dataclass, field

from app.loggers import ExceptionLogger
from app.network import ExternalAPI
from app.response import JSONResponse
from app.core import EnvConfig


@dataclass
class SearchResponse:
    """排行榜响应数据结构"""
    meta: Dict[str, Any] = field(default_factory=dict)
    rows: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'meta': self.meta,
            'rows': self.rows
        }

class SearchAPI:
    @ExceptionLogger.handle_program_exception_async
    async def search_user(name: str):
        response = await ExternalAPI.get_user_search(name)
        error, result = JSONResponse.extract_data(response)
        if error:
            return result
        
        search_count = 0
        search_data = []
        for search in result:
            search_count += 1
            search_data.append({
                'user_id':search['spa_id'],
                'name':search['name']
            })

        data = SearchResponse(
            meta={
                'region': EnvConfig.REGION,
                'count': search_count
            },
            rows=search_data
        )
        return JSONResponse.success(data.to_dict())
    
    @ExceptionLogger.handle_program_exception_async
    async def search_clan(tag: str):
        response = await ExternalAPI.get_clan_search(tag)
        error, result = JSONResponse.extract_data(response)
        if error:
            return result
        
        search_count = 0
        search_data = []
        for search in result:
            search_count += 1
            search_data.append({
                'clan_id':search['id'],
                'tag':search['tag']
            })

        data = SearchResponse(
            meta={
                'region': EnvConfig.REGION,
                'count': search_count
            },
            rows=search_data
        )
        return JSONResponse.success(data.to_dict())