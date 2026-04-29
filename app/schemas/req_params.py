from enum import Enum


class ShipType(str, Enum):
    AIRCARRIER = "AirCarrier"
    BATTLESHIP = "Battleship"
    CRUISER = "Cruiser"
    DESTROYER = "Destroyer"
    SUBMARINE = "Submarine"

class ShipTier(int, Enum):
    T1 = 1
    T2 = 2
    T3 = 3
    T4 = 4
    T5 = 5
    T6 = 6
    T7 = 7
    T8 = 8
    T9 = 9
    T10 = 10
    T11 = 11

class ShipNation(str, Enum):
    COMMONWEALTH = "commonwealth"
    EUROPE = "europe"
    FRANCE = "france"
    GERMANY = "germany"
    ITALY = "italy"
    JAPAN = "japan"
    NETHERLANDS = "netherlands"
    PAN_AMERICA = "pan_america"
    PAN_ASIA = "pan_asia"
    SPAIN = "spain"
    UK = "uk"
    USA = "usa"
    USSR = "ussr"

class RecentLevel(str, Enum):
    off = "off"
    standard = "standard"
    plus = "plus"

class PVPField(str, Enum):
    PVP = 'pvp'
    PVP_SOLO = 'pvp_solo'
    PVP_DIV2 = 'pvp_div2'
    PVP_DIV3 = 'pvp_div3'
