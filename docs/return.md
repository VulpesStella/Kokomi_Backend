# API 返回值说明

## 概述

所有 API 接口均采用统一的 JSON 响应格式，通过 `status` 和 `code` 字段区分响应类型和状态。

### HTTP 状态码说明

| HTTP Status Code | 说明 | 响应格式 |
|-----------------|------|----------|
| **200 OK** | 请求已成功处理，业务结果由响应体中的 `code` 字段区分 | 标准业务 JSON 格式 |
| **403 Forbidden** | Token 无效或权限布局 | / |
| **422 Unprocessable Entity** | 请求参数校验失败，如缺少必填字段、格式错误等 | / |
| **500 Internal Server Error** | 服务器内部异常，通常为未捕获的系统级错误 | / |

> **核心设计原则：**
> - 正常的业务逻辑处理（包括业务错误如用户不存在、节点不可用等）均返回 **HTTP 200**，业务成功/失败由响应体中的 `code` 字段区分
> - 只有请求层级的错误（认证失败、参数校验失败）或系统级异常才会返回非 200 的 HTTP 状态码

## 标准业务响应结构（HTTP 200）

### 类型定义

```typescript
// 基础响应结构
interface BaseResponse {
    status: 'ok' | 'error';  // 响应状态
    code: number;             // 业务状态码
    message: string;          // 响应消息
}

// 成功响应 (code: 1000)
interface SuccessResponse<T = any> extends BaseResponse {
    status: 'ok';
    code: 1000;
    message: 'Success';
    data: T | null;           // 业务数据
}

// API 调用失败响应 (code: 2000)
interface APIFailedResponse extends BaseResponse {
    status: 'error';
    code: 2000;
    message: 'APIFailed';
    data: {
        node_info: string;    // 节点信息/区域标识
        error_name: string;   // 错误名称
    };
}

// 错误响应 (code: 3000)
interface ErrorResponse extends BaseResponse {
    status: 'error';
    code: 3000;
    message: string;
    error: {
        trace_id: string;     // 链路追踪 ID (UUID)
        node_info: string;    // 节点信息/区域标识
        error_name: string;   // 错误名称
    };
}
```

---

## 状态码说明

### 成功状态码 (Code 1000)

| Code | Status | Message | 说明 |
|------|--------|---------|------|
| 1000 | ok | Success | 获取数据成功或操作成功 |

### API 调用失败状态码 (Code 2000)

| Code | Status | Message | 说明 |
|------|--------|---------|------|
| 2000 | error | APIFailed | 请求游戏 API 失败 |

### 异常错误状态码 (Code 3000)

| Code | Status | Message | 说明 |
|------|--------|---------|------|
| 3000 | error | 错误名称 | 通用异常错误 |

### 业务错误状态码 (1001-1xxx)

> 📖 详细的状态码说明、响应示例及客户端处理指南，请查看 [业务错误状态码文档](./code.md)

---

## 响应示例

### HTTP 200 - 业务响应

#### 1. 成功响应

```json
{
    "status": "ok",
    "code": 1000,
    "message": "Success",
    "data": {
        "user_id": "12345",
        "username": "player1"
    }
}
```

> code=1000 并不一定代表 data 会携带业务数据，部分接口 code=1000 表示操作或者刷洗成功，data中不携带任何数据

#### 2. ⚠️ 服务器维护响应

> 检测到 `code === 1001` 时，表示该节点服务器正在维护

```json
{
    "status": "ok",
    "code": 1001,
    "message": "NodeNotAvailable"
}
```

#### 3. 预定义业务错误响应

> 表示由于该原因导致未能成功获取到业务数据（例如用户不存在或者隐藏战绩）

```json
{
    "status": "ok",
    "code": 1003,
    "message": "UserNotExist"
}
```

#### 4. 异常错误响应

> 后续可以通过 node_info + trace_id 参数来查找对应的程序错误日志，进行 DEBUG

```json
{
    "status": "error",
    "code": 3000,
    "message": "DatabaseError",
    "error": {
        "trace_id": "550e8400-e29b-41d4-a716-446655440000",
        "node_info": "cn",
        "error_name": "DatabaseConnectionError"
    }
}
```

#### 5. 游戏 API 请求失败响应

> 网络波动导致

```json
{
    "status": "error",
    "code": 2000,
    "message": "APIFailed",
    "data": {
        "node_info": "cn",
        "error_name": "GameAPITimeout"
    }
}
```

## 客户端处理流程

- **HTTP 非 200**：请求层错误，需单独处理
- **HTTP 200 + code === 1000**：成功，返回 `(false, data)`
- **HTTP 200 + code !== 1000**：业务失败，返回 `(true, 完整响应体)`

### TypeScript 实现示例代码

```typescript
interface APIResponse {
    status: 'ok' | 'error';
    code: number;
    message: string;
    data?: any;
    error?: any;
}

async function callAPI<T>(
    url: string, 
    options?: RequestInit
): Promise<T> {
    const response = await fetch(url, options);
    
    // 处理非 200 HTTP 状态码
    if (!response.ok) {
        throw new Error(`请求失败: HTTP ${response.status}`);
    }
    
    // 处理 HTTP 200 的业务响应
    const result: APIResponse = await response.json();
    
    if (result.code === 1000) {
        return result.data as T;
    }
    
    if (result.code === 1001) {
        throw new Error('服务器维护中，请稍后重试');
    }

    // TODO: 处理其他可能的返回值
    
    throw new Error(`业务错误: ${result.message}`);
}

// 使用示例
try {
    const userData = await callAPI('/api/user/info', {
        method: 'POST',
        headers: {
            'Access-Token': token,
            'Content-Type': 'application/json'
        }
    });
    console.log('用户数据:', userData);
} catch (error) {
    console.error('调用失败:', error.message);
}
```