from app.loggers import ExceptionLogger
from app.health import ServiceMetrics
from app.response import JSONResponse


class ShipRankingAPI:
    @ExceptionLogger.handle_program_exception_async
    async def get_ship_top50(ship_id: int):
        ...