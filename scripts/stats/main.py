#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import gc
import time
import redis
import pymysql
import traceback
from tqdm import tqdm
from pymysql import Connection
from typing import Any, Iterator

from logger import TqdmAwareLogger, get_formatted_date, logger
from analytics import ShipStatsAggregator
from exception import write_exception
from db_ops import (
    need_update,
    reset_tracking_time,
    get_max_id,
    read_ship_data,
    get_pvp_cache,
    update_battles_stats_table,
    update_users_stats_table,
    update_rating_distribution_table,
    update_ship_pvp_stats,
    refresh_table_meta
)
from settings import (
    REGION, 
    USE_TQDM,
    CLIENT_NAME, 
    REFRESH_INTERVAL, 
    MYSQL_CONFIG,
    REDIS_CONFIG,
    BATCH_SIZE
)


def progress_iterable(
    items: list[Any], desc: str, logger_obj: TqdmAwareLogger
) -> Iterator[Any]:
    """遍历列表，根据配置选择进度展示方式

    当 USE_TQDM 为 True 时，使用 tqdm 进度条显示实时进度

    Args:
        items: 待遍历的列表
        desc: 进度描述文本
        logger_obj: TqdmAwareLogger 实例

    Yields:
        列表中的每个元素
    """
    if USE_TQDM:
        # tqdm 模式：显示实时进度条
        tqdm_desc = f'{get_formatted_date()} [INFO] {desc}'
        with tqdm(items, desc=tqdm_desc, total=len(items)) as pbar:
            for item in pbar:
                pbar.set_postfix_str(str(item))
                yield item
    else:
        # 日志模式：定期输出当前进度
        total = len(items)
        for idx, item in enumerate(items, 1):
            logger_obj.info('%s - [%d/%d] | Current: %s', desc, idx, total, item)
            yield item

def worker(mysql_connection: Connection) -> None:
    """执行统计聚合和排行榜刷新

    Args:
        mysql_connection: MySQL 数据库连接对象
    """
    if not need_update(mysql_connection, 'ship_stats', 'update_time'):
        logger.info(f'Update time not yet reached')
        return

    # 从 MySQL 读取原始数据并聚合计算
    try:
        with mysql_connection.cursor() as cursor:
            # 获取数据范围
            max_id = get_max_id(cursor)
            if max_id == 0:
                return
        
            # 获取服务器基准数据（用于计算 Rating）
            ship_data = read_ship_data(cursor)
            ship_ids = list(ship_data.keys())
            if len(ship_ids) == 0:
                return

            # 首次运行读取不到已有的服务器数据
            existing_stats = None
            for row in ship_data.values():
                if row:
                    existing_stats = True
                    break

            # 初始化聚合器
            aggregator = ShipStatsAggregator(ship_data)

            # 分批次读取用户缓存数据
            logger.enable_tqdm()
            for batch_offset in progress_iterable(
                items=range(0, max_id, BATCH_SIZE),
                desc="Processing cache",
                logger_obj=logger
            ):
                # 从数据库获取一批原始缓存数据
                rows = get_pvp_cache(cursor, batch_offset, BATCH_SIZE)
                # 将这批数据添加到聚合器
                aggregator.add_batch(rows)
            logger.disable_tqdm()
        
    except Exception as e:
        error_name = type(e).__name__
        logger.error(f"Database operation exception: {error_name}")
        write_exception(
            error_type="DatabaseError",
            error_name=error_name,
            error_info=traceback.format_exc()
        )
        return 
    
    # 3. 更新 MySQL 统计表
    try:
        with mysql_connection.cursor() as cursor:
            # 如果是首次运行则先把刷新时间置空，下个更新轮次再次执行
            if not existing_stats:
                reset_tracking_time(cursor, 'ship_stats', 'update_time')

            # 更新服务器场次平均统计表
            update_battles_stats_table(cursor, aggregator.compute_battle_averages(ship_ids))

            # 更新服务器用户平均统计表
            update_users_stats_table(cursor, aggregator.compute_user_averages(ship_ids))

            # 更新 Rating 分布统计表
            update_rating_distribution_table(cursor, aggregator.compute_rating_percentiles())

            # 更新船只持有统计数据
            update_ship_pvp_stats(cursor, aggregator.compute_ownership_stats(ship_ids))

            # 更新表的统计信息
            refresh_table_meta(cursor, aggregator.aggregation_stats())

            mysql_connection.commit()
    except Exception as e:
        mysql_connection.rollback()
        error_name = type(e).__name__
        logger.error(f"Database operation exception: {error_name}")
        write_exception(
            error_type="DatabaseError",
            error_name=error_name,
            error_info=traceback.format_exc()
        )
        return 

def main():
    """主服务入口，按配置的刷新间隔（REFRESH_INTERVAL）周期执行统计任务"""
    redis_client = None
    mysql_connection = None

    while True:
        start = time.monotonic()

        try:
            # 建立 Redis 连接
            redis_client = redis.Redis(**REDIS_CONFIG)

            # 设置当前服务状态，用于外部监控系统判断服务是否正常运行
            redis_client.set(f'status:{CLIENT_NAME}', 1, ex=int(REFRESH_INTERVAL*1.5))

            # 建立 MySQL 连接
            mysql_connection = pymysql.connect(**MYSQL_CONFIG)
            
            # 执行核心统计任务
            worker(
                mysql_connection=mysql_connection
            )
        except Exception as e:
            # 记录错误信息
            error_name = type(e).__name__
            logger.error(f"A fatal error occurred in the loop: {error_name}")
            write_exception(
                error_type="ProgramError",
                error_name=error_name,
                error_info=traceback.format_exc()
            )

            # 严重错误导致的循环中断，删除用于标记服务状态的key
            try:
                if redis_client:
                    redis_client.delete(f'status:{CLIENT_NAME}')
            except Exception as e:
                error_name = type(e).__name__
                logger.error(f'Failed to delete status key: {error_name}')
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
        logger.info(f'This loop took {round(elapsed,2)} seconds')
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