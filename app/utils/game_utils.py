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
        if data is None or data == {}:
            return None
        else:
            return f"{data['texture_id']}-{data['symbol_id']}-{data['border_color_id']}-{data['background_color_id']}-{data['background_id']}"
    
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
    
    @staticmethod
    def get_refresh_time(activity_level: int, lbt: int, enable_recent: bool, enable_daily: bool):
        if enable_daily:
            if lbt < 60*60:
                return 5*60
            else:
                return EnvConfig.constants.USER_REFRESH_INTERVAL[str(activity_level)][2]
        elif enable_recent:
            return EnvConfig.constants.USER_REFRESH_INTERVAL[str(activity_level)][1]
        else:
            return EnvConfig.constants.USER_REFRESH_INTERVAL[str(activity_level)][0]
    
    @staticmethod
    def get_activity_level(is_public: bool, total_battles: int = 0, last_battle_time: int = 0):
        "获取activity_level"
        # 具体对应关系的表格
        # | is_public | total_battles | last_battle_time | activity_level | decs    |
        # | --------- | ------------- | ---------------- | -------------- | ------- |
        # | 0         | -             | -                | 0              | 隐藏战绩 |
        # | 1         | 0             | 0                | 1              | 无数据   |
        # | 1         | -             | [0, 1d]          | 2              | 活跃    |
        # | 1         | -             | [1d, 3d]         | 3              | -       |
        # | 1         | -             | [3d, 7d]         | 4              | -       |
        # | 1         | -             | [7d, 1m]         | 5              | -       |
        # | 1         | -             | [1m, 3m]         | 6              | -       |
        # | 1         | -             | [3m, 6m]         | 7              | -       |
        # | 1         | -             | [6m, 1y]         | 8              | -       |
        # | 1         | -             | [1y, + ]         | 9              | 不活跃  |
        if not is_public:
            return 0
        if total_battles == 0 or last_battle_time == 0:
            return 1
        current_timestamp = TimeUtils.timestamp()
        time_differences = EnvConfig.constants.TIME_DIFFERENCES
        time_since_last_battle = current_timestamp - last_battle_time
        for time_limit, return_value in time_differences:
            if time_since_last_battle <= time_limit:
                return return_value
        return 9