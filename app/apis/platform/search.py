from app.loggers import ExceptionLogger
from app.network import ExternalAPI
from app.response import JSONResponse

class SearchAPI:
    @ExceptionLogger.handle_program_exception_async
    async def search_user(name: str, limit: int = 10):
        result = await ExternalAPI.get_user_search(name, limit)
        return result
    
    @ExceptionLogger.handle_program_exception_async
    async def search_clan(tag: str, limit: int = 10):
        result = await ExternalAPI.get_clan_search(tag, limit)
        return result