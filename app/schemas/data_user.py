from pydantic import BaseModel


class ClanBasicData(BaseModel):
    clan_id: int = None
    tag: str = None
    league: int = None

class UserBasicData(BaseModel):
    account_id: int
    username: str = None
    register_time: int = None
    insignias: str = None

    is_enabled: int = 1
    is_public: int = 1
    total_battles: int = 0
    pve_battles: int = 0
    pvp_battles: int = 0
    ranked_battles: int = 0
    rating_battles: int = 0
    last_battle_at: int = 0
    karma: int = 0
