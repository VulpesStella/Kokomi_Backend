from app.core import EnvConfig


class GameUtils:
    """存放和游戏相关的工具函数"""
    def get_user_default_name(account_id: int):
        "获取用户的默认名称"
        return f'User_{account_id}'
    
    def get_clan_default_name():
        "获取工会的默认名称"
        return f'N/A'
    
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
    
    def get_dog_tag(data: str):
        if data is None or data == "":
            return {}
        data = data.split('-')
        return {
            "texture_id": int(data[0]),
            "symbol_id": int(data[1]),
            "border_color_id": int(data[2]),
            "background_color_id": int(data[3]),
            "background_id": int(data[4])
        }

    def check_uid(account_id: int) -> bool:
        "检查account_id是否合法"
        uid_rule = EnvConfig.UID_RULE
        if uid_rule[0] <= account_id <= uid_rule[1]:
            return True
        return False
    
    def format_nation(nation: str) -> str:
        NATION_DISPLAY = {
            "commonwealth": "Commonwealth",
            "europe": "Europe",
            "france": "France",
            "germany": "Germany",
            "italy": "Italy",
            "japan": "Japan",
            "netherlands": "Netherlands",
            "pan_america": "Pan America",
            "pan_asia": "Pan Asia",
            "spain": "Spain",
            "uk": "UK",
            "usa": "USA",
            "ussr": "USSR",
        }

        return NATION_DISPLAY.get(nation, nation.capitalize())
    
    def format_tier(tier: int) -> str:
        ROMAN_MAP = {
            1: 'Ⅰ',
            2: 'Ⅱ',
            3: 'Ⅲ',
            4: 'Ⅳ',
            5: 'Ⅴ',
            6: 'Ⅵ',
            7: 'Ⅶ',
            8: 'Ⅷ',
            9: 'Ⅸ',
            10: 'Ⅹ',
            11: '★',
        }

        return ROMAN_MAP.get(tier, str(tier))