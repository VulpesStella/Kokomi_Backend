from app.schemas import ShipOriginalData, ShipProcessedData


OriginalData = ShipOriginalData(
    battles_count=0, 
    wins=0, 
    damage_dealt=0, 
    frags=0, 
    original_exp=0, 
    personal_rating=-1, 
    damage_rating=-1, 
    frags_rating=-1
)
ProcessedData = ShipProcessedData(
    battles=0,
    wins=0,
    damage=0,
    frags=0,
    exp=0,
    v_battles=0,
    p_rating=0,
    d_rating=0,
    f_rating=0
)