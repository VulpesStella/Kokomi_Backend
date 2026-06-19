import json

from app.core import EnvConfig


class BlacklistManager:
    """黑名单管理器
    
    管理用户黑名单和公会黑名单，支持从本地文件加载和保存
    """

    _users: list[int] = []
    _clans: list[int] = []
    
    @classmethod
    def _load_json_file(cls) -> dict:
        """加载 JSON 文件数据"""
        file_path = EnvConfig.DATA_DIR / 'json/blacklist.json'

        if file_path.exists():
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        else:
            return {"user": [], "clan": []}
    
    @classmethod
    def _save_json_file(cls) -> None:
        """保存数据到 JSON 文件"""
        file_path = EnvConfig.DATA_DIR / 'json/blacklist.json'

        result = {
            "user": cls._users,
            "clan": cls._clans
        }
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    
    @classmethod
    def init(cls) -> None:
        """启动时读取本地文件初始化"""
        data = cls._load_json_file()
        cls._users = data.get("user", [])
        cls._clans = data.get("clan", [])
    
    @classmethod
    def add_user(cls, user_id: int) -> bool:
        """添加用户黑名单，并保存至本地
        
        Args:
            user_id: 用户 ID
        """
        if user_id in cls._users:
            return
        
        cls._users.append(user_id)
        cls._save_json_file()

        return
    
    @classmethod
    def add_clan(cls, clan_id: int) -> bool:
        """添加工会黑名单，并保存至本地
        
        Args:
            clan_id: 公会 ID
        """
        if clan_id in cls._clans:
            return
        
        cls._clans.append(clan_id)
        cls._save_json_file()

        return
    
    @classmethod
    def is_user_blocked(cls, user_id: int) -> bool:
        """传入的用户 ID 是否在黑名单
        
        Args:
            user_id: 用户 ID
            
        Returns:
            bool: 是否在黑名单中
        """
        return user_id in cls._users
    
    @classmethod
    def is_clan_blocked(cls, clan_id: int) -> bool:
        """传入的公会 ID 是否在黑名单
        
        Args:
            clan_id: 公会 ID
            
        Returns:
            bool: 是否在黑名单中
        """
        return clan_id in cls._clans
    
    @classmethod
    def get_all(cls) -> dict:
        """获取所有黑名单数据"""
        return {
            "user": cls._users,
            "clan": cls._clans
        }