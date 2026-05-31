from typing import TypedDict

class ShipOriginalData(TypedDict):
    battles_count: int
    wins: int
    damage_dealt: int
    frags: int
    original_exp: int
    personal_rating: int
    damage_rating: int
    frags_rating: int

class ShipProcessedData(TypedDict):
    battles: int
    wins: int
    damage: int
    frags: int
    exp: int
    v_battles: int
    p_rating: int
    d_rating: int
    f_rating: int