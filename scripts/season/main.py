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
from updater import update_clan_season
from api import fetch_clan_leagues
from db_ops import (
    need_update,
    get_update_ids,
    refresh_clan_cache,
    refresh_clan_league,
    ensure_clan_battle_table
)
from utils import (
    is_cb_active,
    read_season_data,
    get_current_timestamp
)
from settings import (
    CLIENT_NAME, 
    REGION, 
    USE_TQDM,
    REFRESH_INTERVAL, 
    MYSQL_CONFIG, 
    REDIS_CONFIG, 
    CLAN_REALM_MAP, 
    CLAN_LEAGUE_LIST
)


SECONDS_PER_DAY = 24 * 60 * 60
EXPECTED_LEAGUE_COUNT = 13

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

def worker(mysql_connection: Connection, redis_client: Redis, created_season: int) -> None:
    # 1. 读取当前赛季信息
    season_data = read_season_data()
    season_id = season_data['id']
    logger.info(f"Current Season ID: {season_id}")

    # 2. 确保当前赛季的工会战数据表存在
    if created_season != season_id and ensure_clan_battle_table(mysql_connection, season_id):
        created_season = season_id
        logger.debug(f'Table T_clan_battle_s{season_id} is already exists')
    
    now_ts = get_current_timestamp()
    # 3. 最低每天刷新一次并确保首次运行时能立即获取数据
    if (
        need_update(mysql_connection, 'clan_season', 'refresh_time') or 
        is_cb_active(now_ts, season_data['start'], season_data['finish'])
    ):
        success_count = 0
        total_list = []
        league_count = {'0': 0, '1': 0, '2': 0, '3': 0, '4': 0}

        logger.enable_tqdm()
        for update_data in progress_iterable(
            items=CLAN_LEAGUE_LIST, 
            desc=f"Processing Leagues",
            logger_obj=logger
        ):
            league, division = update_data.split('-')
            league_data = fetch_clan_leagues(
                redis_client=redis_client,
                realm=CLAN_REALM_MAP.get(REGION),
                league=league,
                division=division
            )
            if type(league_data) == list:
                success_count += 1
                league_count[league] += len(league_data)
                total_list.extend(league_data)
        logger.disable_tqdm()

        logger.info('Current active clans: 1(%d), 2(%d), 3(%d), 4(%d)', league_count["1"], league_count["2"], league_count["3"], league_count["4"])
        if success_count == EXPECTED_LEAGUE_COUNT:
            # 成功读取全部13个 league 数据后，更新所有工会的league字段
            refresh_clan_league(mysql_connection, total_list)

        # 比较最新数据和数据库数据，确定需要更新的工会ID列表
        update_ids = get_update_ids(mysql_connection, season_id, total_list)
        len_update_ids = len(update_ids)
        if len_update_ids > 0:
            # 更新需要更新的工会数据
            logger.info(f'Clans to update: {len_update_ids}')
            for update_data in progress_iterable(
                items=update_ids, 
                desc=f"Processing Clan",
                logger_obj=logger
            ):
                update_clan_season(redis_client, mysql_connection, season_id, update_data)
        
        # 全量刷新工会排行榜缓存，防止脏数据污染
        refresh_clan_cache(redis_client, mysql_connection, season_id)
    else:
        logger.info(f'Update time not yet reached')

def main():
    redis_client = None
    mysql_connection = None
    created_season = 0
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
                created_season=created_season
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