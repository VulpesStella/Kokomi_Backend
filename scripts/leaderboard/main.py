#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import redis
import pymysql
import asyncio

from logger import logger
from settings import (
    CLIENT_NAME, REFRESH_INTERVAL, 
    MYSQL_CONFIG, REDIS_CONFIG,
    REGION
)
from utils import (
    read_ship_tier,
    read_ship_server,
    get_update_ids,
    process_user,
    update_user_cache
)


async def main():
    while True:
        start = time.monotonic()
        redis_client = redis.Redis(**REDIS_CONFIG)
        redis_client.set(f'status:{CLIENT_NAME}', 1, ex=int(REFRESH_INTERVAL*1.1))
        mysql_connection = pymysql.connect(**MYSQL_CONFIG)
        try:
            ship_tier_data = read_ship_tier()
            ship_server_data = read_ship_server()
            update_ids = get_update_ids(mysql_connection)
            len_update_ids = len(update_ids)
            logger.info(f'Update Numbers: {len_update_ids}')
            for index, update_id in enumerate(update_ids, 1):
                result = update_user_cache(mysql_connection, ship_tier_data, update_id)
                logger.info(f"[{index}/{len_update_ids}] {REGION.upper()}-{update_id} | {result}")
            result = process_user(ship_server_data)
            logger.info(f"Leaderboard(User): {result}")
        finally:
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
    logger.info(f'Start running service {CLIENT_NAME}')
    if os.name != "nt":
        import signal
        signal.signal(signal.SIGTERM, handler)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info('The process is closing')