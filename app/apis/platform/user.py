from app.loggers import ExceptionLogger
from app.models import BotUserModel, PremiumModel


class UserAPI:
    @ExceptionLogger.handle_program_exception_async
    async def get_user_premium_status(platform: str, user_id: int):
        result = await BotUserModel.premium_status(platform, user_id)
        return result
    
    @ExceptionLogger.handle_program_exception_async
    async def generate_code(max_use: int, validity: int, level: int, limit: int, describe: str = None):
        result = await PremiumModel.generate_code(
            max_use,
            validity,
            level,
            limit,
            describe
        )
        return result
