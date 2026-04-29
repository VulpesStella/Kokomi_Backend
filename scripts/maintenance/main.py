#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import redis
import pymysql
import traceback
from celery import Celery

from logger import logger
from settings import (
    CLIENT_NAME, 
    REFRESH_INTERVAL, 
    REGION, 
    MYSQL_CONFIG, 
    REDIS_CONFIG,
    RABBITMQ_CONFIG
)
from utils import (
    progress_iterable,
    send_task,
    refresh_version,
    maintenance_database,
    get_user_update_ids,
    get_clan_update_ids,
    archive_statistics
)

def main():
    broker_url = f"pyamqp://{RABBITMQ_CONFIG['user']}:{RABBITMQ_CONFIG['password']}@{RABBITMQ_CONFIG['host']}/"
    celery_app = Celery(
        'producer',
        broker=broker_url,
        broker_connection_retry_on_startup=True
    )
    while True:
        start = time.monotonic()
        conn = pymysql.connect(**MYSQL_CONFIG)
        redis_client = redis.Redis(**REDIS_CONFIG)
        # 设置当前服务状态，用于外部监控系统判断服务是否正常运行
        redis_client.set(f'status:{CLIENT_NAME}', 1, ex=int(REFRESH_INTERVAL*1.5))
        try:
            # 1.检测数据库是否存在脏数据行
            fixed_count = maintenance_database(conn)
            if fixed_count != 0:
                logger.info(f'Fixed Row Counts: {fixed_count}')
            
            # 2.每小时检测游戏版本是否更新
            refresh_version(conn, redis_client)

            # 3.更新玩家的基本数据
            update_ids = get_user_update_ids(conn, redis_client)
            len_update_ids = len(update_ids)
            if len_update_ids > 0:
                logger.info(f'User Update Numbers: {len_update_ids}')
                failed_count = 0
                for update_data in progress_iterable(
                    items=update_ids, 
                    desc="Processing Users",
                    logger_obj=logger
                ):
                    if not send_task(celery_app, 'user_refresh', update_data, 'refresh_queue'):
                        failed_count += 1
                logger.info(f'Task sent complete, Success: {len_update_ids - failed_count}  Failed: {failed_count}')

            # 4.更新工会的会内玩家数据
            update_ids = get_clan_update_ids(conn, redis_client)
            len_update_ids = len(update_ids)
            if len_update_ids > 0:
                logger.info(f'Clan Update Numbers: {len_update_ids}')
                failed_count = 0
                for update_data in progress_iterable(
                    items=update_ids, 
                    desc="Processing Clans",
                    logger_obj=logger
                ):
                    if not send_task(celery_app, 'clan_refresh', update_data, 'refresh_queue'):
                        failed_count += 1
                logger.info(f'Task sent complete, Success: {len_update_ids - failed_count}  Failed: {failed_count}')
            
            # 5.归档统计数据到归档表
            archive_statistics(conn)

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
            conn.close()

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