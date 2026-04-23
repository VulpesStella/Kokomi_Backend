#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import random
import asyncio
import datetime
import threading
from fastapi import FastAPI, Request, Security
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
# from fastapi.middleware.gzip import GZipMiddleware
from contextlib import asynccontextmanager
from starlette.responses import StreamingResponse

from app.response import JSONResponse as API_JSONResponse
from app.core import EnvConfig, api_logger
from app.utils import TimeUtils
from app.loggers import CSVWriter, log_queue
from app.database import MysqlConnection
from app.health import HealthManager, ServiceMetrics
from app.apis.platform import StatusAPI
from app.middlewares import (
    RedisConnection,
    get_role,
)

from app.routers import (
    platform_router, 
    demo_router, 
    statistics_router,
    recent_router
)


# 应用程序的定期刷新任务
async def schedule():
    while True:
        # 检查各服务状态
        # await HealthManager.refresh()
        # 检查
        await asyncio.sleep(60)  # 每 60 秒执行一次任务


# ------------------------------------------------------
# 后台日志写入线程，用于将日志队列中的请求信息写入CSV文件
# 功能逻辑：
# 1. 主线程将日志数据放入队列log_queue
# 2. 写线程阻塞读取队列并写入磁盘
# 3. 程序退出时发送None信号，线程flush缓存并关闭文件
# 避免请求处理被 I/O 阻塞，保证日志完整
# ------------------------------------------------------
def csv_writer_thread():
    writer = CSVWriter()
    api_logger.info('The log writing thread has been started')
    while True:
        record = log_queue.get()
        api_logger.debug('Received a log data to be written')
        if record is None:  # 退出信号
            break
        writer.write(record)
        log_queue.task_done()

    writer.close()
    api_logger.info('The log writing thread has exited')


# ------------------------------------------------------
# 应用程序的生命周期管理
# 功能逻辑：
# 1. yield前的代码在应用启动时执行（startup）
# 2. yield后的finally块在应用关闭时执行（shutdown）
# ------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 从环境中加载配置
    env_file = EnvConfig.init()
    if env_file:
        api_logger.info(f"Env config loaded: {env_file}")
    else:
        api_logger.error("Env config load failed")
    api_logger.info(f"Current region: {EnvConfig.REGION.upper()}")
    # 启动定时任务
    task = asyncio.create_task(schedule())
    # 启动API日志写入线程
    writer_thread = threading.Thread(target=csv_writer_thread, daemon=True)
    writer_thread.start()
    # 初始化mysql并测试mysql连接
    await MysqlConnection.test_mysql()
    # 初始化并测试redis连接
    await RedisConnection.test_redis()
    # 启动 lifespan
    try:
        yield
    finally:
        await MysqlConnection.close_mysql()
        await RedisConnection.close_redis()
        # 发送退出信号，等待剩下数据写入并退出线程
        log_queue.put(None)
        writer_thread.join()
        # 关闭时取消定时任务
        task.cancel()  


# 初始化模板
templates = Jinja2Templates(directory="app/templates")
# 加载APP
app = FastAPI(lifespan=lifespan)

# # 消息压缩
# app.add_middleware(
#     GZipMiddleware,
#     minimum_size=1000  # 大于 1KB 才压缩
# )

# ------------------------------------------------------
# 请求中间件
# 功能逻辑：
# 1. 所有HTTP请求在到达路由处理函数前都会经过这里
# 2. 可以在此记录请求信息、统计耗时、处理通用逻辑
# 3. 中间件调用call_next(request)将请求传递给后续处理
# ------------------------------------------------------
@app.middleware("http")
async def request_rate_limiter(request: Request, call_next):
    # client_ip = request.client.host if request.client else None
    # if client_ip not in EnvConfig.config.BIND_HOST:
    #     return JSONResponse(
    #         status_code=403,
    #         content={"detail": "Forbidden"}
    #     )
    start = TimeUtils.timestamp_ms()
    now_time = TimeUtils.now_iso()
    await ServiceMetrics.requests_incr('api', now_time[0:10])
    response: StreamingResponse = await call_next(request)
    elapsed = int((TimeUtils.timestamp_ms() - start))
    record = [
        now_time,
        request.client.host if request.client else "-",
        request.method,
        request.url,
        response.status_code,
        elapsed
    ]
    try:
        log_queue.put_nowait(record)
    except Exception:
        api_logger.warning('Log queue full!')
        pass  # 队列满时直接丢弃，避免阻塞接口
    return response


# 测试接口
@app.get("/", summary='Home', tags=['Default'])
async def root():
    """
    测试接口连通性
    """
    return {'status':'ok','messgae':'Hello! Welcome to KokomiPlatform Interface.'}

@app.get("/status/", summary="API指标", tags=['Default'])
async def testRootPermission():
    return await StatusAPI.api_stats()

@app.get("/permission/", summary="测试当前token是否可用", tags=['Default'])
async def testRootPermission(role: bool = Security(get_role)):
    return API_JSONResponse.get_success_response(role)

@app.get("/dashboard/", response_class=HTMLResponse, summary="Dashboard", tags=['Default'])
async def dashboard(request: Request):
    today = datetime.date.today()

    days = [
        (today - datetime.timedelta(days=i)).isoformat()
        for i in range(14, -1, -1)
    ]
    data = {

        "api_metrics": {
            "Today Requests": 84211,
            "Today Errors": 12,
            "Avg Latency (ms)": 34,
            "API Calls": 125411,
            "API Failures": 212,
            "Celery Tasks": 45221
        },

        "database": {
            "MySQL Users": 15231,
            "MySQL Clans": 421,
            "MySQL Recent": 892123,
            "MySQL Recents": 32122,
            "SQLite Files": 54,
            "SQLite Size (MB)": 312
        },

        "charts":[
            {
                "id":"request_chart",
                "title":"Request Trend",
                "x":days,
                "y":[random.randint(5000, 20000) for _ in days]
            },
            {
                "id":"error_chart",
                "title":"Error Trend",
                "x":days,
                "y":[random.randint(0, 30) for _ in days]
            }
        ]

    }

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "node_region": "Asia",
            **data
        }
    )

# ------------------------------------------------------
# 在主路由中注册子路由
# 功能逻辑：
# 1. 将routers中定义的路由统一挂载到主应用app上
# 2. prefix: 给子路由统一添加路径前缀
# 3. tags: 给子路由分组，用于自动生成OpenAPI文档分类
# ------------------------------------------------------

app.include_router(
    demo_router, 
    prefix="/api/demo", 
    tags=['Demo Interface'],
    dependencies=[Security(get_role)]
)

app.include_router(
    platform_router, 
    prefix="/api/platform", 
    tags=['Platform Interface'],
    dependencies=[Security(get_role)]
)

app.include_router(
    statistics_router,
    prefix="/api/stats",
    tags=['Statistics Interface'],
    dependencies=[Security(get_role)]
)

app.include_router(
    recent_router,
    prefix="/api/recent",
    tags=['Recent Interface'],
    dependencies=[Security(get_role)]
)

# ------------------------------------------------------
# 【该功能已弃用】
# 重写 shutdown 函数，避免某些协程在关闭时出错
# 原理：
# 1. 调用原始 shutdown 执行默认清理
# 2. 等待指定时间确保后台协程完成或安全退出
# ------------------------------------------------------
# async def _shutdown(self, any = None):
#     await origin_shutdown(self)
#     wait_second = 1
#     while wait_second > 0:
#         api_logger.info(f'App will close after {wait_second} seconds')
#         await asyncio.sleep(1)
#         wait_second -= 1
#     api_logger.info('App has been closed')

# origin_shutdown = asyncio.BaseEventLoop.shutdown_default_executor
# asyncio.BaseEventLoop.shutdown_default_executor = _shutdown