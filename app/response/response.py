import uuid
from typing import Optional, Literal, Any, Union
from typing_extensions import TypedDict

from app.core import EnvConfig


class ResponseStatus(str):
    """API 响应状态标识

    定义了两种基础响应状态：
    - SUCCESS：请求处理成功
    - ERROR：请求处理失败
    """
    SUCCESS = 'ok'
    ERROR = 'error'

class ErrorInfo(TypedDict):
    """错误追踪信息

    用于在错误响应中携带问题定位所需的关键信息。
    """
    trace_id: str      # 链路追踪 ID，便于日志排查
    platform: str      # 当前服务所在的平台标识

class SuccessResponseDict(TypedDict):
    """成功响应结构

    所有业务处理成功时返回的统一数据格式。
    data 字段承载具体的业务返回内容，可为任意类型或空
    """
    status: Literal['ok']
    code: Literal[1000]
    message: Literal['Success']
    data: Optional[Any]

class ErrorResponseDict(TypedDict):
    """业务错误响应结构

    当请求处理过程中出现预期内的业务错误或系统异常时，
    返回此结构。error 字段携带 trace_id 用于问题追踪
    """
    status: Literal['error']
    code: int
    message: str
    error: ErrorInfo

class InfoResponseDict(TypedDict):
    """信息提示响应结构

    用于返回非致命性的提示信息，请求仍视为成功处理，
    但通过 code 向调用方传递具体的业务状态
    """
    status: Literal['error']
    code: int
    message: str

# 统一的响应类型联合，涵盖上述三种具体结构
ResponseDict = Union[SuccessResponseDict, ErrorResponseDict, InfoResponseDict]

class JSONResponse:
    """标准化 JSON 响应工具类

    封装了 API 返回值的构造、预定义状态码常量，以及
    从响应中提取数据的工具方法。

    状态码分段说明：
    - 1000：请求完全成功
    - 2000-2999：业务层提示信息（INFO），请求成功但需调用方关注
    - 3000-3999：系统或业务异常（ERROR），请求失败

    子范围划分：
    - 2000-2299：节点 API 相关消息
    - 3000-3099：节点 API 相关异常
    - 3100-3199：游戏 API 相关异常
    """

    API_1000_Success = {'status': 'ok', 'code': 1000, 'message': 'Success', 'data': None}

    API_2000_APIFailed = {'status': 'ok', 'code': 2000, 'message': 'APIFailed'}
    API_2001_IllegalAccountID = {'status': 'ok', 'code': 2001, 'message': 'IllegalAccountID'}
    API_2002_IllegalClanID = {'status': 'ok', 'code': 2002, 'message': 'IllegalClanID'}
    API_2003_IllegalUserName = {'status': 'ok', 'code': 2003, 'message': 'IllegalUserName'}
    API_2004_IllegalClanTag = {'status': 'ok', 'code': 2004, 'message': 'IllegalClanTag'}
    API_2005_InvalidAccessToken = {'status': 'ok', 'code': 2005, 'message': 'InvalidAccessToken'}
    API_2006_InvalidAuthToken = {'status': 'ok', 'code': 2006, 'message': 'InvalidAuthToken'}
    API_2007_RegionNotSupported = {'status': 'ok', 'code': 2007, 'message': 'RegionNotSupported'}
    API_2008_IllegalUserName = {'status': 'ok', 'code': 2008, 'message': 'IllegalUserName'}
    API_2009_IllegalClanTag = {'status': 'ok', 'code': 2009, 'message': 'IllegalClanTag'}
    API_2010_AccountNotEligible = {'status': 'ok', 'code': 2010, 'message': 'AccountNotEligible'}
    API_2011_UserNotExist = {'status': 'ok', 'code': 2011, 'message': 'UserNotExist'}
    API_2012_ClanNotExist = {'status': 'ok', 'code': 2012, 'message': 'ClanNotExist'}
    API_2013_UserDataIsNone = {'status': 'ok', 'code': 2013, 'message': 'UserDataIsNone'}
    API_2014_ClanDataIsNone = {'status': 'ok', 'code': 2014, 'message': 'ClanDataIsNone'}
    API_2015_UserHiddenProfile = {'status': 'ok', 'code': 2015, 'message': 'UserHiddenProfile'}
    API_2016_UserNotInDB = {'status': 'ok', 'code': 2016, 'message': 'UserNotInDB'}
    API_2017_ClanNotInDB = {'status': 'ok', 'code': 2017, 'message': 'ClanNotInDB'}
    API_2018_LeaderboardUnderMaintenance = {'status': 'ok', 'code': 2018, 'message': 'LeaderboardUnderMaintenance'}

    # 通用程序错误
    _API_3000_ProgramError = {'status': 'ok', 'code': 3000, 'message': 'ProgramError'}

    # 数据库异常 (3001-3004)
    _API_3001_MySQLDatabaseError = {'status': 'ok', 'code': 3001, 'message': 'MySQLDatabaseError'}
    _API_3002_MySQLProgrammingError = {'status': 'ok', 'code': 3002, 'message': 'MySQLProgrammingError'}
    _API_3003_MySQLOperationalError = {'status': 'ok', 'code': 3003, 'message': 'MySQLOperationalError'}
    _API_3004_MySQLIntegrityError = {'status': 'ok', 'code': 3004, 'message': 'MySQLIntegrityError'}

    # 缓存异常
    _API_3005_RedisError = {'status': 'ok', 'code': 3005, 'message': 'RedisError'}

    # 网络请求异常 (3100-3106)
    _API_3100_NetworkError = {'status': 'ok', 'code': 3100, 'message': 'NetworkError'}
    _API_3101_HttpxConnectTimeout = {'status': 'ok', 'code': 3101, 'message': 'HttpxConnectTimeout'}
    _API_3102_HttpxReadTimeout = {'status': 'ok', 'code': 3102, 'message': 'HttpxReadTimeout'}
    _API_3103_HttpxTimeoutError = {'status': 'ok', 'code': 3103, 'message': 'HttpxTimeoutError'}
    _API_3104_HttpxConnectError = {'status': 'ok', 'code': 3104, 'message': 'HttpxConnectError'}
    _API_3105_HttpxReadError = {'status': 'ok', 'code': 3105, 'message': 'HttpxReadError'}
    _API_3106_HttpxHTTPStatusError = {'status': 'ok', 'code': 3106, 'message': 'HttpxHTTPStatusError'}


    @staticmethod
    def get_success_response(
        data: Optional[Any] = None
    ) -> SuccessResponseDict:
        """构造成功响应

        返回 code=1000 的标准成功响应，附带调用方传入的业务数据。

        Args:
            data: 需要返回给客户端的业务数据，默认为 None。

        Returns:
            符合 SuccessResponseDict 结构的字典
        """
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
        """构造错误响应

        返回指定错误码和错误信息的失败响应，自动生成 trace_id
        并注入当前平台标识，便于后期问题定位

        Args:
            code: 业务错误码，格式遵循类级别定义的分段规则
            message: 面向调用方的错误描述信息
            error_id: 链路追踪 ID。未提供时自动生成 UUID

        Returns:
            符合 ErrorResponseDict 结构的字典
        """
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
    def extract_data(response: ResponseDict) -> tuple[bool, Any]:
        """从响应中宽松提取数据

        仅通过 status 字段判定请求成败：
        - status 不是 'ok'：视为失败，返回 (True, 完整响应体)
        - status 是 'ok'：视为成功，返回 (False, 响应中的 data 字段)

        适用于调用方主要关注请求是否产生异常的场景

        Args:
            response: 待提取的响应字典
        """
        if response['status'] != 'ok':
            return True, response
        return False, response['data']

    @staticmethod
    def extract_data_strict(response: ResponseDict) -> tuple[bool, Any]:
        """从响应中严格提取数据

        通过 code 字段精确判定请求成败：
        - code 不等于 1000：视为失败，返回 (True, 完整响应体)
        - code 等于 1000：视为成功，返回 (False, 响应中的 data 字段)

        Args:
            response: 待提取的响应字典
        """
        if response['code'] != 1000:
            return True, response
        return False, response['data']