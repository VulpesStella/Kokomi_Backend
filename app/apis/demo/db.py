import os
import json

from app.loggers import ExceptionLogger
from app.models import PlatformModel, PlatyerModel, ClanModel
from app.core import EnvConfig
from app.response import JSONResponse
from app.utils import JsonUtils


class MySQLAPI:
    @ExceptionLogger.handle_program_exception_async
    async def get_user_overview(account_id: int):
        result = await PlatyerModel.read_base(account_id)
        return result
    
    @ExceptionLogger.handle_program_exception_async
    async def get_clan_overview(clan_id: int):
        result = await ClanModel.read_base(clan_id)
        return result