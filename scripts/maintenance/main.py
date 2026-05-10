#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
数据更新调度服务主程序

定期检测游戏版本变化、修复数据库脏数据、聚合暂存数据，
并根据用户和公会的活跃度策略，通过 Celery 向消息队列分发数据刷新任务，
最后将当前统计数据归档留存

工作流程：
    1. 检测游戏版本是否更新，同步最新版本信息
    2. 修复基础表中缺失的关联数据行，聚合暂存中的 Recent 数据
    3. 分批扫描用户和公会基础表，筛选需要刷新的 ID
    4. 通过 Celery 将刷新任务发送到消息队列，由 Worker 异步执行
    5. 归档用户/公会数量和船只统计数据到 ARCH 表
    6. 等待下一个刷新周期
"""

import os
import gc
import time
import redis
import pymysql
import traceback
from tqdm import tqdm
from redis import Redis
from celery import Celery
from pymysql import Connection
from typing import Any, Iterator

from logger import TqdmAwareLogger, get_formatted_date, logger
from settings import (
    CLIENT_NAME, 
    REGION, 
    USE_TQDM,
    REFRESH_INTERVAL, 
    MYSQL_CONFIG, 
    REDIS_CONFIG,
    RABBITMQ_CONFIG
)
from db_ops import (
    maintenance_database,
    aggregate_recent_data,
    refresh_version,
    get_update_ids,
    archive_statistics
)


def send_task(celery_app: Celery, task_name: str, entity_id: int, queue: str) -> bool:
    """向指定队列发送 Celery 任务。

    Args:
        celery_app: Celery 应用实例。
        task_name: 任务名称。
        entity_id: 实体 ID（用户或公会 ID）。
        queue: 目标队列名。

    Returns:
        True 表示发送成功，False 表示失败。
    """
    try:
        celery_app.send_task(
            name=task_name, 
            args=[{'uid': entity_id}], 
            queue=queue
        )
        return True
    except Exception as e:
        logger.error(f"Send Task failed: {entity_id} | {type(e).__name__}")
        return False
    
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
        # total = len(items)
        for idx, item in enumerate(items, 1):
            # logger_obj.info('%s - [%d/%d] | Current: %s', desc, idx, total, item)
            yield item

def worker(mysql_connection: Connection, redis_client: Redis, celery_app: Celery) -> None:
    # 1.每小时检测游戏版本是否更新
    try:
        with mysql_connection.cursor() as cursor:
            refresh_version(cursor, redis_client)

        mysql_connection.commit()
    except Exception:
        mysql_connection.rollback()
        logger.error(traceback.format_exc())

    # 2.检测数据库是否存在脏数据行，把待写入的recent数据写入归档表
    try:
        with mysql_connection.cursor() as cursor:
            maintenance_database(cursor)

        mysql_connection.commit()
    except Exception:
        mysql_connection.rollback()
        logger.error(traceback.format_exc())

    try:
        with mysql_connection.cursor() as cursor:
            aggregate_recent_data(cursor)

        mysql_connection.commit()
    except Exception:
        mysql_connection.rollback()
        logger.error(traceback.format_exc())

    # 3.更新玩家/工会的基本数据
    for index in ['user', 'clan']:
        update_ids = get_update_ids(mysql_connection, redis_client, index)
        len_update_ids = len(update_ids)
        if len_update_ids == 0:
            continue
        logger.info(f'{index.capitalize()} update numbers: {len_update_ids}')

        failed_count = 0
        logger.enable_tqdm()
        for update_data in progress_iterable(
            items=update_ids, 
            desc=f"Processing {index}",
            logger_obj=logger
        ):
            if not send_task(celery_app, f'{index}_refresh', update_data, 'refresh_queue'):
                redis_client.delete(f"refresh_lock:{index}:{update_data}")
                failed_count += 1
        logger.disable_tqdm()
        logger.info(f'Task sent completed - Success: {len_update_ids - failed_count} | Failed: {failed_count}')
        
    # 4.归档统计数据到归档表
    try:
        with mysql_connection.cursor() as cursor:
            archive_statistics(cursor)

        mysql_connection.commit()
    except Exception:
        mysql_connection.rollback()
        logger.error(traceback.format_exc())

def main():
    redis_client = None
    mysql_connection = None
    broker_url = f"pyamqp://{RABBITMQ_CONFIG['user']}:{RABBITMQ_CONFIG['password']}@{RABBITMQ_CONFIG['host']}/"
    celery_app = Celery(
        'producer',
        broker=broker_url,
        broker_connection_retry_on_startup=True
    )
    while True:
        start = time.monotonic()

        try:
            redis_client = redis.Redis(**REDIS_CONFIG)
            # 设置当前服务状态，用于外部监控系统判断服务是否正常运行
            redis_client.set(f'status:{CLIENT_NAME}', 1, ex=int(REFRESH_INTERVAL*1.5))
            mysql_connection = pymysql.connect(**MYSQL_CONFIG)

            worker(
                mysql_connection=mysql_connection,
                redis_client=redis_client,
                celery_app=celery_app
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
        main()
    except KeyboardInterrupt:
        # 在Windows系统上，无法捕获SIGTERM信号，但可以通过捕获KeyboardInterrupt异常来实现类似的功能
        handler()