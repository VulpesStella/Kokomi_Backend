#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
公会战数据刷新服务 —— 主调度模块

# 功能概述：
以后台常驻进程方式运行，周期性从 WoWS Clan API 拉取各联赛分段（共 13 个）
的公会排行榜列表，根据赛季活跃状态和数据变化判断是否需要拉取详细数据，
更新公会联赛段位和战斗统计，并将最新排行榜缓存到 Redis 有序集合。

# 模块分工：
- main.py    （本文件）—— 主调度循环、连接管理、进度展示
- api.py                —— 外部 Clan API 请求封装（排行榜列表 + 单公会详情）
- updater.py            —— 单公会赛季数据解析、对战记录增量计算
- db_ops.py             —— 数据库读写（赛季表创建、缓存读写、联赛刷新、排行榜同步）
- utils.py              —— 时间工具、赛季配置读取、活动窗口判断
- logger.py             —— tqdm 兼容日志器
- settings.py           —— 环境变量加载与全局配置常量

# 主循环流程：
    1. 建立 Redis / MySQL 连接，写入服务状态 key
    2. 调用 worker()：
        a. 读取赛季配置，确保赛季战表 S_clan_battle_{id} 已创建
        b. 检查 need_update（最低每天一次）或 is_cb_active（赛季活跃期）
        c. 遍历 13 个联赛分段，拉取公会排行榜列表
        d. 处理赛季切换（season_id 变化时重新确定赛季）
        e. 全部 13 个分段拉取成功后，全量刷新公会 league 字段
        f. 对比排行数据与数据库记录，筛选需更新的公会
        g. 逐公会拉取详细数据 → 写入 MySQL → 更新 Redis 排行
        h. 全量重建 Redis 公会排行榜有序集合（防脏数据残留）
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
    read_season_data
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
EXPECTED_LEAGUE_COUNT = 13  # 联赛分段的预期数量（League 1-4 + Division 1-3 + League 4 Division 1 = 3*4 + 1 = 13）

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
    """单轮公会赛季数据刷新执行体

    读取赛季配置，确保赛季战表存在后，从 API 拉取全部 13 个联赛分段的公会列表，
    全量刷新 league 字段，对比筛选需更新的公会后逐条拉取详情写入 MySQL，
    最后全量重建 Redis 排行榜缓存。

    Args:
        mysql_connection: MySQL 数据库连接
        redis_client: Redis 客户端
    """
    # 1. 读取当前赛季信息
    season_data = read_season_data()
    season_id = season_data.get('id', 0)
    if season_id == 0:
        logger.warning('Season_ID not configured')
        return
    logger.info(f"Current Season ID: {season_id}")

    # 2. 确保当前赛季的工会战数据表存在
    table_status = ensure_clan_battle_table(mysql_connection, season_id)
    if table_status is None:
        logger.warning(f'Failed to check if Table T_clan_battle_s{season_id} exists')
    if table_status:
        logger.debug(f'Table T_clan_battle_s{season_id} is already exists')
    else:
        logger.info(f'New table T_clan_battle_s{season_id} has been successfully created.')
    
    # 3. 为确保首次运行时能立即获取数据，最低每天刷新一次
    if (
        need_update(mysql_connection, 'clan_season', 'refresh_time') or 
        is_cb_active(season_data['start'], season_data['finish'])
    ):
        success_count = 0
        total_list = []
        league_count = {'0': 0, '1': 0, '2': 0, '3': 0, '4': 0}

        # 读取13个分段中所有工会的数据
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
                if not league_data:
                    success_count += 1
                    continue 

                latest_season_id = league_data[0][4]
                # 赛季变化处理
                if latest_season_id != season_id:
                    if total_list:
                        logger.warning('Clan battle season changed')
                        return
                    # 首次遇到新赛季，更新season_id
                    season_id = latest_season_id
                    logger.info(f"Latest Season ID: {season_id}")

                success_count += 1
                league_count[league] += len(league_data)
                total_list.extend(league_data)
        logger.disable_tqdm()

        logger.info('Current active clans: 0(%d), 1(%d), 2(%d), 3(%d), 4(%d)', league_count["0"], league_count["1"], league_count["2"], league_count["3"], league_count["4"])
        if success_count == EXPECTED_LEAGUE_COUNT:
            # 成功读取全部13个 league 数据后，更新所有工会的league字段
            refresh_clan_league(mysql_connection, total_list)

        # 比较最新数据和数据库数据，确定需要更新的工会ID列表
        update_ids = get_update_ids(mysql_connection, season_id, total_list)
        len_update_ids = len(update_ids)
        
        if len_update_ids > 0:
            # 更新需要更新的工会数据
            logger.info(f'Clans update numbers: {len_update_ids}')
            logger.enable_tqdm()
            for update_data in progress_iterable(
                items=update_ids, 
                desc=f"Processing Clan",
                logger_obj=logger
            ):
                update_clan_season(redis_client, mysql_connection, season_id, update_data)
            logger.disable_tqdm()
        
        # 全量刷新工会排行榜缓存，防止脏数据污染
        refresh_clan_cache(redis_client, mysql_connection, season_id)
    else:
        logger.info(f'Update time not yet reached')

def main():
    """主调度循环

    无限循环执行：建立连接 → worker() 更新公会赛季数据 →
    释放连接资源 → 按 REFRESH_INTERVAL 补齐 sleep。
    异常不会中断循环，但会清理服务状态 key 以便外部监控感知。
    """
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