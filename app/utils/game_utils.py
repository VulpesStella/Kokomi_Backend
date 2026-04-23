from app.core import EnvConfig

from .time_utils import TimeUtils


class GameUtils:
    """存放和游戏相关的工具函数"""
    def get_user_default_name(account_id: int):
        "获取用户的默认名称"
        return f'User_{account_id}'
    
    def get_clan_default_name():
        "获取工会的默认名称"
        return f'N/A'
    
    @staticmethod
    def get_insignias(data: dict):
        if not data:
            return None
        keys = [
            "texture_id",
            "symbol_id",
            "border_color_id",
            "background_color_id",
            "background_id"
        ]
        if any(k not in data for k in keys):
            return None
        return "-".join(str(data[k]) for k in keys)
    
    @staticmethod
    def get_dog_tag(data: str):
        if data is None or data == "":
            return {}
        data = data.split('-')
        return {
            "texture_id": data[0],
            "symbol_id": data[1],
            "border_color_id": data[2],
            "background_color_id": data[3],
            "background_id": data[4]
        }

    @staticmethod
    def check_uid(account_id: int) -> bool:
        "检查account_id是否合法"
        uid_rule = EnvConfig.UID_RULE
        if uid_rule[0] <= account_id <= uid_rule[1]:
            return True
        return False