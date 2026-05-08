#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
用户PVP数据缓存更新系统

定期更新玩家的PVP战斗数据缓存，包括个人统计、船只数据、排行榜排名等信息。
该服务作为后台维护进程，持续监控需要更新的用户列表，并通过调用外部API获取最新数据，
将处理后的数据存储到MySQL数据库和Redis缓存中。

工作流程：
    1. 初始化异步HTTP客户端、Redis、MySQL连接
    2. 获取需要更新的用户ID列表
    3. 并发处理每个用户的数据更新
    4. 异常恢复与资源清理
    5. 检测维护模式，必要时等待
    6. 计算循环耗时，调整sleep时间

维护模式流程：
    - 主循环正常运行
    - 若检测到'leaderboard:maintenance' key则抛出MaintenanceInterrupt异常
    - 进入维护等待循环，每30秒检查一次
    - 最多等待10分钟，10分钟后无论如何都会退出
"""

import os
import gc
import time
import httpx
import redis
import pymysql
import asyncio
import traceback
from tqdm import tqdm
from redis import Redis
from httpx import AsyncClient
from pymysql import Connection
from typing import Any, Iterator

from logger import TqdmAwareLogger, get_formatted_date, logger
from updater import UserCacheUpdater
from utils import get_current_timestamp
from db_ops import (
    get_update_ids,
    read_ship_data,
    read_ship_record
)
from settings import (
    CLIENT_NAME, 
    REGION,
    USE_TQDM,
    REFRESH_INTERVAL, 
    MYSQL_CONFIG, 
    REDIS_CONFIG
)


TIMEOUT = httpx.Timeout(connect=2.0, read=10.0, write=3.0, pool=2.0)

class MaintenanceInterrupt(Exception):
    """维护模式中断异常"""
    pass

def check_maintenance(redis_client) -> None:
    """检查是否进入维护模式，如果是则抛出内部异常"""
    if redis_client.exists('leaderboard:maintenance'):
        raise MaintenanceInterrupt("Maintenance mode detected")

def progress_iterable(
    items: list[Any], desc: str, logger_obj: TqdmAwareLogger
) -> Iterator[Any]:
    """遍历列表，tqdm 模式下用进度条，否则日志输出进度。

    Args:
        items: 待遍历的列表。
        desc: 进度描述文本。
        logger_obj: TqdmAwareLogger 实例。

    Yields:
        列表中的每个元素。
    """
    if USE_TQDM:
        tqdm_desc = f'{get_formatted_date()} [INFO] {desc}'
        with tqdm(items, desc=tqdm_desc, total=len(items)) as pbar:
            for item in pbar:
                pbar.set_postfix_str(str(item))
                yield item
    else:
        total = len(items)
        for idx, item in enumerate(items, 1):
            logger_obj.info('%s - [%d/%d] | Current: %s', desc, idx, total, item)
            yield item

async def worker(mysql_connection: Connection, redis_client: Redis, async_client: AsyncClient) -> None:
    # 1. 加载循环需要的一些船只数据
    try:
        with mysql_connection.cursor() as cursor:
            update_ids = get_update_ids(cursor)
            len_update_ids = len(update_ids)
            if len_update_ids == 0:
                return
            logger.info(f'Cache update numbers: {len_update_ids}')

            # 加载符合排行榜统计船只的数据
            ship_data = read_ship_data(cursor)

            # 读取船只相关字段的最高记录信息
            ship_record = read_ship_record(cursor)
    except Exception:
        logger.error(traceback.format_exc())
        return
    
    # 维护模式等待机制：
    # - 维护期间会对排行榜数据库进行全表更新，导致锁全表
    # - 为避免写操作冲突，检测到维护 key 就等待
    # - 每 30 秒检查一次，维护结束立即退出
    maintenance_time = 0
    while True:
        # 超时保护：10 分钟后无论维护是否结束都退出循环
        if maintenance_time >= 600:
            logger.warning("Maintenance wait timeout, exiting anyway")
            break

        try:
            check_maintenance(redis_client)  # 未检测到维护 key，正常退出循环
        except MaintenanceInterrupt:
            logger.info("Maintenance mode detected, waiting 30s...")
            time.sleep(30)
            maintenance_time += 30
            continue  # 继续等待
        except Exception:
            pass  # Redis 异常不阻塞流程
        
        break  # 检查通过，退出等待循环
    
    # 主更新循环
    updater = UserCacheUpdater(ship_record, ship_data)
    logger.enable_tqdm()
    for update_data in progress_iterable(
        items=update_ids, 
        desc="Processing cache",
        logger_obj=logger
    ):
        try:
            check_maintenance(redis_client)  # 检查是否处于维护模式
        except MaintenanceInterrupt:
            logger.info("Maintenance mode detected, stop updating...")
            break  # 跳出内层 for 循环，继续外层 while 循环

        await updater.main(
            mysql_connection,
            redis_client,
            async_client,
            update_data
        )
    logger.disable_tqdm()

async def main():
    async_client = None
    redis_client = None
    mysql_connection = None

    while True:
        start = time.monotonic()
        
        try:
            redis_client = redis.Redis(**REDIS_CONFIG)
            # 设置当前服务状态，用于外部监控系统判断服务是否正常运行
            redis_client.set(f'status:{CLIENT_NAME}', 1, ex=int(REFRESH_INTERVAL*1.5))
            mysql_connection = pymysql.connect(**MYSQL_CONFIG)
            async_client = httpx.AsyncClient(timeout=TIMEOUT)

            await worker(
                mysql_connection=mysql_connection,
                redis_client=redis_client,
                async_client=async_client
            )

            redis_client.set(f'leaderboard:ship_update_time', get_current_timestamp())

        except Exception:
            logger.error(traceback.format_exc())
            # 严重错误导致的循环中断，删除用于标记服务状态的key
            try:
                if redis_client:
                    redis_client.delete(f'status:{CLIENT_NAME}')
            except Exception as e:
                logger.error(f'Failed to delete status key: {e}')
        finally:
            # 大部分情况下每次循环运行时间远小于刷新间隔，大部分时间都处于sleep状态
            # 为了减少相关资源占用，每次循环结束后关闭所有连接，释放资源空间
            # 等待下一次循环运行时再重新建立连接
            if async_client:
                await async_client.aclose()
            if redis_client:
                redis_client.close()
            if mysql_connection:
                mysql_connection.close()
            async_client = None
            redis_client = None
            mysql_connection = None
            gc.collect()

        # 计算本次循环的实际运行时间，并根据刷新间隔决定是否需要sleep
        elapsed = time.monotonic() - start
        logger.info('This loop took %.2f seconds', round(elapsed, 2))
        sleep_time = max(0, round(REFRESH_INTERVAL - elapsed, 2))

        if sleep_time >= 1:
            logger.info(f'The process sleeps for {sleep_time} seconds')
            time.sleep(sleep_time)
        logger.info('-'*70)

def handler(*_):
    """信号处理器，退出"""
    logger.info('The process is closing')
    exit(0)

if __name__ == '__main__':
    logger.info('Start running service: %s', CLIENT_NAME)
    logger.info('Service refresh interval: %s seconds', REFRESH_INTERVAL)
    logger.info('Current node region: %s', REGION.upper())

    if os.name != 'nt':
        # 在非Windows系统上注册SIGTERM信号处理器，在接收到SIGTERM信号时关闭服务
        import signal
        signal.signal(signal.SIGTERM, handler)

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # 在Windows系统上，无法捕获SIGTERM信号，但可以通过捕获KeyboardInterrupt异常来实现类似的功能
        handler()