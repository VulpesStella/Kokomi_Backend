#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import gc
import time
import redis
import pymysql
import traceback
from tqdm import tqdm
from redis import Redis
from pymysql import Connection
from typing import Any, Iterator

from logger import TqdmAwareLogger, get_formatted_date, logger
from syncer import ClanUsersSyncer
from db_ops import get_update_ids
from api import fetch_clan_members
from settings import (
    REGION, 
    USE_TQDM,
    CLIENT_NAME, 
    REFRESH_INTERVAL, 
    MYSQL_CONFIG, 
    REDIS_CONFIG
)

    
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

def worker(mysql_connection: Connection, redis_client: Redis) -> None:
    """单轮维护调度执行体

    执行版本同步、暂存数据聚合、用户/公会刷新 ID 筛选与 Celery 任务分发、
    以及统计数据归档共四个阶段的维护操作。

    Args:
        mysql_connection: MySQL 数据库连接
        redis_client: Redis 客户端
        celery_app: Celery 应用实例
    """
    

    # 更新工会的基本数据
    update_ids = get_update_ids(mysql_connection)

    len_update_ids = len(update_ids)
    if len_update_ids == 0:
        return
    if len_update_ids > REFRESH_INTERVAL * 4:
        update_ids = update_ids[:REFRESH_INTERVAL * 4]
        len_update_ids = len(update_ids)
        
    logger.info(f'Current loop update numbers: {len_update_ids}')

    logger.enable_tqdm()
    for update_data in progress_iterable(
        items=update_ids, 
        desc=f"Processing clan",
        logger_obj=logger
    ):
        response = fetch_clan_members(redis_client, update_data)

        if not response:
            continue
        
        users = {}
        for user_info in response.get('items', []):
            users[user_info['id']] = user_info['name']

        ClanUsersSyncer.refresh(redis_client, mysql_connection, update_data, users)
    logger.disable_tqdm()

def main():
    """主调度循环"""
    redis_client = None
    mysql_connection = None

    while True:
        start = time.monotonic()

        try:
            redis_client = redis.Redis(**REDIS_CONFIG)
            # 设置当前服务状态，用于外部监控系统判断服务是否正常运行
            redis_client.set(f'status:{CLIENT_NAME}', 1, ex=int(REFRESH_INTERVAL*1.5))
            mysql_connection = pymysql.connect(**MYSQL_CONFIG)

            worker(
                mysql_connection=mysql_connection,
                redis_client=redis_client
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
            if redis_client:
                redis_client.close()
            if mysql_connection:
                mysql_connection.close()
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
        main()
    except KeyboardInterrupt:
        # 在Windows系统上，无法捕获SIGTERM信号，但可以通过捕获KeyboardInterrupt异常来实现类似的功能
        handler()