import uuid
from typing import Optional, Literal, Any
from typing_extensions import TypedDict

from app.core import EnvConfig

# 定义状态常量
class ResponseStatus(str):
    SUCCESS = 'ok'
    ERROR = 'error'

class ErrorInfo(TypedDict):
    trace_id: str
    platform: str

class SuccessResponseDict(TypedDict):
    status: Literal['ok']
    code: Literal[1000]
    message: Literal['Success']
    data: Optional[Any]

class ErrorResponseDict(TypedDict):
    status: Literal['error']
    code: int
    message: str
    error: ErrorInfo

class JSONResponse:
    '''接口返回值'''
    # 1000 -> 成功
    API_1000_Success = {'status': 'ok','code': 1000,'message': 'Success','data': None}
    '''
    2000-2999 -> [INFO]  业务层消息
    3000-3999 -> [ERROR] 异常

    子节点API
    2000 - 2299 节点API消息
    3000 - 3099 节点API异常 
    3100 - 3199 游戏API异常
    '''
    # INFO
    API_2001_IllegalAccountID = {'status': 'ok','code': 2001,'message': 'IllegalAccountID'}
    API_2002_IllegalClanID = {'status': 'ok','code': 2002,'message': 'IllegalClanID'}
    API_2003_IllegalUserName = {'status': 'ok','code': 2003,'message': 'IllegalUserName'}
    API_2004_IllegalClanTag = {'status': 'ok','code': 2004,'message': 'IllegalClanTag'}
    API_2005_InvalidAccessToken = {'status': 'ok','code': 2005,'message': 'InvalidAccessToken'}
    API_2006_InvalidAuthToken = {'status': 'ok','code': 2006,'message': 'InvalidAuthToken'}
    API_2007_RegionNotSupported = {'status': 'ok','code': 2007,'message': 'RegionNotSupported'}
    API_2008_IllegalUserName = {'status': 'ok','code': 2008,'message': 'IllegalUserName'}
    API_2009_IllegalClanTag = {'status': 'ok','code': 2009,'message': 'IllegalClanTag'}
    API_2010_AccountNotEligible = {'status': 'ok','code': 2010,'message': 'AccountNotEligible'}
    API_2011_UserNotExist = {'status': 'ok','code': 2011,'message': 'UserNotExist'}
    API_2012_ClanNotExist = {'status': 'ok','code': 2012,'message': 'ClanNotExist'}
    API_2013_UserDataisNone = {'status': 'ok','code': 2013,'message': 'UserDataisNone'}
    API_2014_ClanDataisNone = {'status': 'ok','code': 2014,'message': 'ClanDataisNone'}
    API_2015_UserHiddenProfile = {'status': 'ok','code': 2015,'message': 'UserHiddenProfile'}
    API_2016_UserNotInDB = {'status': 'ok', 'code': 2016, 'message': 'UserNotInDB'}
    API_2017_ClanNotInDB = {'status': 'ok', 'code': 2017, 'message': 'ClanNotInDB'}
    # 船只不符合排行版资格
    API_2018_ShipNotQualifiedForRanking = {'status': 'ok', 'code': 2018, 'message': 'ShipNotQualifiedForRanking'}
    # 该船只没有排行榜数据
    API_2019_NoRankingDataForShip = {'status': 'ok', 'code': 2019, 'message': 'NoRankingDataForShip'}
    # 该用户没有在该船只上的排名数据
    API_2020_NoRankingDataForUser = {'status': 'ok', 'code': 2020, 'message': 'NoRankingDataForUser'}
    API_2021_NoRankingDataForClan = {'status': 'ok', 'code': 2021, 'message': 'NoRankingDataForClan'}
    API_2022_NoRankingDataForClanSeason = {'status': 'ok', 'code': 2022, 'message': 'NoRankingDataForClanSeason'}
    # API_20_ = {'status': 'ok','code': 20,'message': ''}

    @staticmethod
    def get_success_response(
        data: Optional[Any] = None
    ) -> SuccessResponseDict:
        """成功的返回值"""
        return {
            'status': ResponseStatus.SUCCESS,
            'code': 1000,
            'message': 'Success',
            'data': data
        }
    
    @staticmethod
    def get_error_response(
        code: int,
        message: str,
        error_id: Optional[str] = None
    ) -> ErrorResponseDict:
        """失败的返回值"""
        if error_id is None:
            error_id = str(uuid.uuid4())
        return {
            'status': ResponseStatus.ERROR,
            'code': code,
            'message': message,
            'error': {
                'trace_id': error_id,
                'platform': EnvConfig.PLATFORM
            }
        }

    @staticmethod
    def extract_data(response: SuccessResponseDict | ErrorResponseDict) -> tuple[bool, Any]:
        if response.get('code') != 1000:
            return False, response
        return True, response.get('data')
