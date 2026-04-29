#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import time
import httpx
import redis
import pymysql
import asyncio
import traceback
from tqdm import tqdm
from datetime import datetime

from logger import logger
from settings import (
    CLIENT_NAME, REFRESH_INTERVAL, USE_TQDM, 
    MYSQL_CONFIG, REDIS_CONFIG,
    REGION, DATE_FMT
)
from utils import (
    progress_iterable,
    get_update_ids,
    get_version,
    get_refresh,
    read_metric_level,
    read_ship_record,
    read_ship_data,
    update_user_cache
)


async def main():
    while True:
        start = time.monotonic()
        TIMEOUT = httpx.Timeout(connect=2.0, read=10.0, write=3.0, pool=2.0)
        async_client = httpx.AsyncClient(timeout=TIMEOUT)
        redis_client = redis.Redis(**REDIS_CONFIG)
        redis_client.set(f'status:{CLIENT_NAME}', 1, ex=int(REFRESH_INTERVAL*1.1))
        mysql_connection = pymysql.connect(**MYSQL_CONFIG)
        
        try:
            refresh_data = get_refresh(mysql_connection)
            if type(refresh_data) != dict:
                logger.error(f"Read refresh_time data failed: {refresh_data}")
                raise ValueError()
            ship_tier = read_ship_data(mysql_connection)
            if type(ship_tier) != dict:
                logger.error(f"Read ship_tier data failed: {ship_tier}")
                raise ValueError()
            update_ids = get_update_ids(mysql_connection)
            len_update_ids = len(update_ids)
            logger.info(f'Update Numbers: {len_update_ids}')
            ship_record = read_ship_record(mysql_connection)
            if type(ship_record) != dict:
                logger.error(f"Read ship_record data failed: {ship_record}")
                raise ValueError()
            metric_level = read_metric_level(mysql_connection)
            if type(metric_level) != dict:
                logger.error(f"Read metric_level data failed: {metric_level}")
                raise ValueError()
            if len_update_ids > 0:
                game_version = get_version()
                for update_data in progress_iterable(
                    items=update_ids, 
                    desc="Processing",
                    logger_obj=logger
                ):
                    await update_user_cache(
                        mysql_connection,
                        redis_client,
                        async_client,
                        update_data,
                        game_version,
                        ship_record,
                        ship_tier,
                        metric_level
                    )
        except Exception:
            logger.error(traceback.format_exc())
            # 严重错误导致的循环中断，删除用于标记服务状态的key
            try:
                redis_client.delete(f'status:{CLIENT_NAME}')
            except Exception as e:
                logger.error(f'Failed to delete status key: {e}')
        finally:
            # 大部分情况下每次循环运行时间远小于刷新间隔，大部分时间都处于sleep状态
            # 为了减少资源占用，每次循环结束后释放数据库和redis连接，等待下一次循环时再重新建立连接
            redis_client.close()
            mysql_connection.close()

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