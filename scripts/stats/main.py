#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
舰船数据统计服务 —— 主调度模块

# 功能概述：
以后台常驻进程方式运行，周期性从 MySQL 读取用户 PvP 缓存数据，聚合计算三类
统计数据（服务器场次平均、用户场均表现、Rating 百分位分布），并将结果写入
MySQL 统计表和 Redis 排行榜有序集合。

# 模块分工：
- main.py       （本文件）—— 主调度循环、连接管理、进度展示
- analytics.py             —— 数据聚合引擎（ShipStatsAggregator + HistogramBins）
- db_ops.py                —— 数据库读写操作（缓存读取、统计写入、排行榜刷新）
- utils.py                 —— 时间工具、Rating 计算
- logger.py                —— tqdm 兼容日志器
- settings.py              —— 环境变量加载与全局配置常量

# 主循环流程：
    1. 建立 Redis / MySQL 连接，写入服务状态 key
    2. 调用 worker()：
        a. 检查 need_update 追踪状态（UTC 23 点为强制更新时间）
        b. 分析 SQLite 数据库文件状态
        c. 分批次读取 T_user_pvp.ship_cache，喂入 ShipStatsAggregator
        d. 聚合计算后批量写入 T_ship_stats_by_battles / _by_users / _rating_distribution
           及 T_ship_pvp_stats / T_table_meta
        e. 设置维护锁 → 刷新每条船的 MySQL 排行榜 + Redis 排行榜 → 释放锁
           （维护锁防止刷新期间外部读取到不完整数据，有效期 1 小时）
        f. 写入 leaderboard:users 哈希表（上榜用户数）
    3. finally 块释放连接并 gc.collect()
    4. 计算耗时，按 REFRESH_INTERVAL 补齐 sleep
"""

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
from analytics import ShipStatsAggregator
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

def worker(mysql_connection: Connection, redis_client: Redis) -> None:
    """执行统计聚合和排行榜刷新

    Args:
        mysql_connection: MySQL 数据库连接对象
        redis_client: Redis 客户端对象
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
    except Exception:
        logger.error(traceback.format_exc())
        
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
    except Exception:
        mysql_connection.rollback()
        logger.error(traceback.format_exc())

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