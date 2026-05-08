import uuid
from typing import Optional, Literal, Any, Union
from typing_extensions import TypedDict

from app.core import EnvConfig


class ResponseStatus(str):
    """响应状态常量"""
    SUCCESS = 'ok'
    ERROR = 'error'

class ErrorInfo(TypedDict):
    """错误信息结构定义"""
    trace_id: str
    platform: str

class SuccessResponseDict(TypedDict):
    """成功响应结构定义
    
    当请求处理成功时返回的统一格式
    """
    status: Literal['ok']
    code: Literal[1000]
    message: Literal['Success']
    data: Optional[Any]

class ErrorResponseDict(TypedDict):
    """错误响应结构定义
    
    当请求处理失败时返回的统一格式
    """
    status: Literal['error']
    code: int
    message: str
    error: ErrorInfo

ResponseDict = Union[SuccessResponseDict, ErrorResponseDict]

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
    API_2000_APIFailed = {'status': 'ok','code': 2000,'message': 'APIFailed','data' : None}
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
    API_2013_UserDataIsNone = {'status': 'ok','code': 2013,'message': 'UserDataIsNone'}
    API_2014_ClanDataIsNone = {'status': 'ok','code': 2014,'message': 'ClanDataIsNone'}
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

    
    # 程序错误 3000
    API_3000_ProgramError = {'status': 'ok', 'code': 3000, 'message': 'ProgramError'}

    # 数据库错误 3001-3004
    API_3001_MySQLDatabaseError = {'status': 'ok', 'code': 3001, 'message': 'MySQLDatabaseError'}
    API_3002_MySQLProgrammingError = {'status': 'ok', 'code': 3002, 'message': 'MySQLProgrammingError'}
    API_3003_MySQLOperationalError = {'status': 'ok', 'code': 3003, 'message': 'MySQLOperationalError'}
    API_3004_MySQLIntegrityError = {'status': 'ok', 'code': 3004, 'message': 'MySQLIntegrityError'}

    # 缓存错误 3005
    API_3005_RedisError = {'status': 'ok', 'code': 3005, 'message': 'RedisError'}

    # 网络错误 3100-3106
    API_3100_NetworkError = {'status': 'ok', 'code': 3100, 'message': 'NetworkError'}
    API_3101_HttpxConnectTimeout = {'status': 'ok', 'code': 3101, 'message': 'HttpxConnectTimeout'}
    API_3102_HttpxReadTimeout = {'status': 'ok', 'code': 3102, 'message': 'HttpxReadTimeout'}
    API_3103_HttpxTimeoutError = {'status': 'ok', 'code': 3103, 'message': 'HttpxTimeoutError'}
    API_3104_HttpxConnectError = {'status': 'ok', 'code': 3104, 'message': 'HttpxConnectError'}
    API_3105_HttpxReadError = {'status': 'ok', 'code': 3105, 'message': 'HttpxReadError'}
    API_3106_HttpxHTTPStatusError = {'status': 'ok', 'code': 3106, 'message': 'HttpxHTTPStatusError'}


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
        """从响应中提取数据（基于 status 字段判断）
        
        根据响应的 status 字段判断请求是否成功:
            - 如果 status 不是 'ok'，表示请求失败，返回错误信息
            - 如果 status 是 'ok'，表示请求成功，返回 data 字段的数据
        """
        if response['status'] != 'ok':
            return True, response
        return False, response['data']

    @staticmethod
    def extract_data_strict(response: SuccessResponseDict | ErrorResponseDict) -> tuple[bool, Any]:
        """从响应中严格提取数据（基于 code 字段判断）
    
        根据响应的 code 字段判断请求是否成功:
            - 如果 code 不等于 1000，表示请求失败，返回错误信息
            - 如果 code 等于 1000，表示请求成功，返回 data 字段的数据
        """
        if response['code'] != 1000:
            return True, response
        return False, response['data']
