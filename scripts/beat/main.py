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
    MYSQL_CONFIG, REDIS_CONFIG
)
from utils import (
    get_update_ids, 
    get_expiring_ids, 
    update_user_private, 
    update_user_token, 
    process_region_stats
)


async def main():
    while True:
        start = time.monotonic()
        redis_client = redis.Redis(**REDIS_CONFIG)
        redis_client.set(f'status:{CLIENT_NAME}', 1, ex=int(REFRESH_INTERVAL*1.1))
        conn = pymysql.connect(**MYSQL_CONFIG)
        try:
            update_ids = get_update_ids(conn, redis_client)
            len_update_ids = len(update_ids)
            logger.info(f'Private Update Numbers: {len_update_ids}')
            for index, update_id in enumerate(update_ids, 1):
                result = await update_user_private(conn, redis_client,update_id[0],update_id[1],update_id[2])
                logger.info(f'[{index}/{len_update_ids}] {update_id[0]}-{update_id[1]} | {result}')
            update_ids = get_expiring_ids(conn, redis_client)
            len_update_ids = len(update_ids)
            logger.info(f'Token Update Numbers: {len_update_ids}')
            for index, update_id in enumerate(update_ids, 1):
                result = await update_user_token(redis_client, update_id[0],update_id[1],update_id[2])
                logger.info(f'[{index}/{len_update_ids}] {update_id[0]}-{update_id[1]} | {result}')
            process_region_stats(conn, redis_client)
        finally:
            redis_client.close()
            conn.close()
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
        print('The process is closing')