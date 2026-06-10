# 业务错误状态码文档

本文档定义了 API 响应中所有业务错误状态码

> 这些状态码均在 **HTTP 200** 响应中返回，`status` 字段为 `"ok"`，通过 `code` 字段区分具体的错误类型

| Code | Status | Message | 说明 |
|------|--------|---------|------|
| 1001 | ok | NodeNotAvailable | 当前节点维护中，不可用 |
| 1002 | ok | RegionNotSupported | 当前区域不支持该接口 |
| 1003 | ok | UserNotExist | 用户数据不存在 |
| 1004 | ok | ClanNotExist | 公会数据不存在 |
| 1005 | ok | UserDataIsNone | 用户数据为空 |
| 1006 | ok | ClanDataIsNone | 公会数据为空 |
| 1007 | ok | UserHiddenProfile | 用户隐藏战绩 |
| 1008 | ok | AcqurieLockFailed | 获取写入锁失败 |
| 1009 | ok | NoStatisticsData | 无统计数据 |
