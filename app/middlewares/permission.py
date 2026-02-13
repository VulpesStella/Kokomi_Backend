class AccessManager:
    _ip_blacklist = []
    _game_user_blacklist = []
    _game_clan_blacklist = []

    @classmethod
    def reload(cls, data: dict) -> tuple[int, int, int]:
        cls._ip_blacklist = data.get('ip', [])
        cls._game_user_blacklist = data.get('game_user', [])
        cls._game_clan_blacklist = data.get('game_clan', [])
        return len(cls._ip_blacklist), len(cls._game_user_blacklist), len(cls._game_clan_blacklist)

    @classmethod
    def is_ip_blacklisted(cls, ip: str) -> bool:
        return ip in cls._ip_blacklist
    
    @classmethod
    def is_account_blacklisted(cls, account_id: int) -> bool:
        return int(account_id) in cls._game_user_blacklist
    
    @classmethod
    def is_clan_blacklisted(cls, clan_id: int) -> bool:
        return int(clan_id) in cls._game_clan_blacklist
