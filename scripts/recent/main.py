#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import gc
import time
import redis
import httpx
import pymysql
import asyncio
import traceback
from tqdm import tqdm
from redis import Redis
from httpx import AsyncClient
from pymysql import Connection
from typing import Any, Iterator

from logger import TqdmAwareLogger, get_formatted_date, logger
from updater import UserConfig, UserStats, UserRecentUpdater
from db_ops import get_recent_users
from utils import get_current_timestamp
# from update import update_user_recent
# from utils import (
#     get_recent_update_ids,
#     get_private_update_ids,
#     update_user_private,
#     get_token_update_ids,
#     update_user_token,
#     db_stats
# )
from settings import (
    LOG_LEVEL,
    CLIENT_NAME, 
    REGION,
    USE_TQDM,
    REFRESH_INTERVAL, 
    MYSQL_CONFIG, 
    REDIS_CONFIG
)



TIMEOUT = httpx.Timeout(connect=2.0, read=10.0, write=3.0, pool=2.0)

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

async def worker(mysql_connection: Connection, redis_client: Redis, async_client: AsyncClient):
    update_list = []
    try:
        with mysql_connection.cursor() as cursor:
            rows = get_recent_users(cursor)
            for row in rows:
                if row[3] == 0:
                    continue
                user_config = UserConfig(
                    level=row[1],
                    limit=row[2]
                )
                if row[10] is None:
                    update_list.append([row[0],user_config,None,None])
                else:
                    user_stats = UserStats(
                        is_public=row[4],
                        total_battles=row[5],
                        pve_battles=row[6],
                        pvp_battles=row[7],
                        ranked_battles=row[8],
                        karma=row[9]
                    )
                    update_list.append([row[0],user_config,user_stats,row[10]])
                    
                # 测试用代码
                break
    except Exception:
        logger.error(traceback.format_exc())
        return
    
    for account_id, user_config, user_stats, update_time in update_list:
        lock_key = f"refresh_lock:recent:{account_id}"
        lock_acquired = redis_client.set(lock_key, 1, nx=True, ex=60)

        if not lock_acquired:
            logger.info(f'{account_id} | Failed to acquire lock')
            continue
        
        try:
            current_timestamp = get_current_timestamp()
            result = UserRecentUpdater.need_update(
                account_id=account_id,
                current_timestamp=current_timestamp,
                user_latest_stats=user_stats,
                user_update_time=update_time
            )
            if True:
                await UserRecentUpdater.main(
                    mysql_connection=mysql_connection,
                    redis_client=redis_client,
                    async_client=async_client,
                    account_id=account_id,
                    user_config=user_config,
                    current_timestamp=current_timestamp
                )
        except Exception:
            logger.error(traceback.format_exc())

        redis_client.delete(lock_key)
    # update_ids = get_recent_update_ids(mysql_connection)
    # len_update_ids = len(update_ids)
    # logger.info(f'Recent Update Numbers: {len_update_ids}')
    # for index, update_id in enumerate(update_ids, 1):
    #     result = await update_user_recent(
    #         mysql_connection,redis_client,async_client,update_id[0],update_id[1]
    #     )
    #     logger.info(f"[{index}/{len_update_ids}] {REGION}-{update_id[0]} | {result}")
    # update_ids = get_private_update_ids(mysql_connection, redis_client)
    # len_update_ids = len(update_ids)
    # logger.info(f'Private Update Numbers: {len_update_ids}')
    # for index, update_id in enumerate(update_ids, 1):
    #     result = await update_user_private(mysql_connection,redis_client,async_client,update_id[0],update_id[1])
    #     logger.info(f'[{index}/{len_update_ids}] {REGION}-{update_id[0]} | {result}')
    # update_ids = get_token_update_ids(mysql_connection, redis_client)
    # len_update_ids = len(update_ids)
    # logger.info(f'Token Update Numbers: {len_update_ids}')
    # for index, update_id in enumerate(update_ids, 1):
    #     result = await update_user_token(redis_client, update_id[0],update_id[1],update_id[2])
    #     logger.info(f'[{index}/{len_update_ids}] {update_id[0]}-{update_id[1]} | {result}')
    # db_stats()

async def main():
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

        if LOG_LEVEL == 'debug':
            logger.debug('The process is closing')
            break

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
    os._exit(0)

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