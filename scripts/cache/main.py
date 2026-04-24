#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import time
import httpx
import redis
import pymysql
import asyncio
from tqdm import tqdm
from datetime import datetime

from logger import logger
from settings import (
    CLIENT_NAME, REFRESH_INTERVAL, USE_TQDM, 
    MYSQL_CONFIG, REDIS_CONFIG,
    REGION, DATE_FMT
)
from utils import (
    get_update_ids,
    get_version,
    get_refresh,
    read_metric_level,
    read_ship_record,
    read_ship_data,
    refresh_leaderboard,
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
            redis_key = f"leaderboard:refresh_time"
            refresh_time = redis_client.get(redis_key)
            refresh_time = 0 if refresh_time is None else int(refresh_time)
            if int(time.time()) - refresh_time >= 24*60*60:
                refresh_result = refresh_leaderboard(
                    mysql_connection=mysql_connection,
                    redis_client=redis_client,
                    ship_ids=list(ship_tier.keys())
                )
                logger.info(f'Leaderboard Refresh: {refresh_result}')
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
                if USE_TQDM:
                    iterator = tqdm(
                        update_ids, 
                        total=len_update_ids, 
                        desc=f"{datetime.now().strftime(DATE_FMT)} [INFO] Updating"
                    )
                else:
                    iterator = enumerate(update_ids, 1)
                for item in iterator:
                    if USE_TQDM:
                        update_id = item
                        index = iterator.n
                    else:
                        index, update_id = item
                    result = await update_user_cache(
                        mysql_connection,
                        redis_client,
                        async_client,
                        update_id,
                        game_version,
                        ship_record,
                        ship_tier,
                        metric_level
                    )
                    if USE_TQDM:
                        iterator.set_postfix_str(f"{REGION}-{update_id} | {result}")
                    else:
                        logger.info(f'[{index}/{len_update_ids}] {REGION}-{update_id} | {result}')
        except Exception:
            pass
        finally:
            await async_client.aclose()
            redis_client.close()
            mysql_connection.close()
        elapsed = time.monotonic() - start
        logger.info(f'This loop took {round(elapsed,2)} seconds')
        sleep_time = max(0, round(REFRESH_INTERVAL - elapsed, 2))
        if sleep_time != 0:
            logger.info(f'The process sleeps for {sleep_time} seconds')
            time.sleep(sleep_time)
        logger.info('-'*70)

def handler(_signum, _frame):
    logger.info('The process is closing')
    exit(0)

if __name__ == "__main__":
    logger.info(f'Start running service: {CLIENT_NAME}')
    logger.info(f'Service refresh interval: {REFRESH_INTERVAL} seconds')
    logger.info(f'Current node region: {REGION.upper()}')
    if os.name != "nt":
        import signal
        signal.signal(signal.SIGTERM, handler)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info('The process is closing')