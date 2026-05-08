from app.loggers import ExceptionLogger
from app.network import ExternalAPI
from app.response import JSONResponse
from app.core import EnvConfig

class SearchAPI:
    @ExceptionLogger.handle_program_exception_async
    async def search_user(name: str):
        response = await ExternalAPI.get_user_search(name)
        error, result = JSONResponse.extract_data_strict(response)
        if error:
            return result
        data = []
        if result and len(result) > 0:
            for search_data in result:
                data.append({
                    'region': EnvConfig.REGION,
                    'account_id':search_data['spa_id'],
                    'name':search_data['name']
                })
        return JSONResponse.get_success_response(data)
    
    @ExceptionLogger.handle_program_exception_async
    async def search_clan(tag: str):
        response = await ExternalAPI.get_clan_search(tag)
        error, result = JSONResponse.extract_data_strict(response)
        if error:
            return result
        data = []
        if result and len(result) > 0:
            for search_data in result:
                data.append({
                    'region': EnvConfig.REGION,
                    'clan_id':search_data['id'],
                    'tag':search_data['tag']
                })
        return JSONResponse.get_success_response(data)