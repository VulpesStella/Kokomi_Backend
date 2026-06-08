from typing import Optional, Literal, Any, Union
from typing_extensions import TypedDict


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
    node_info: str     # 当前节点信息
    error_name: str    # 错误类型

class APIFiledInfo(TypedDict):
    """错误追踪信息

    用于在错误响应中携带问题定位所需的关键信息。
    """
    node_info: str     # 当前节点信息
    error_name: str    # 错误类型

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

class APIFailedResponseDict(TypedDict):
    """业务错误响应结构"""
    status: Literal['ok']
    code: int
    message: str
    data: APIFiledInfo

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