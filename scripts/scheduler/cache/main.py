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
    get_versions,
    update_user_cahce
)


async def main():
    while True:
        start = time.monotonic()
        redis_client = redis.Redis(**REDIS_CONFIG)
        redis_client.set(f'status:{CLIENT_NAME}', 1, ex=int(REFRESH_INTERVAL*1.1))
        conn = pymysql.connect(**MYSQL_CONFIG)
        try:
            update_ids = get_update_ids(conn)
            len_update_ids = len(update_ids)
            logger.info(f'Update Numbers: {len_update_ids}')
            versions = get_versions(conn)
            for index, user_info in enumerate(update_ids, 1):
                    region_id = user_info[0]
                    account_id = user_info[1]
                    result = await update_user_cahce(conn,redis_client,region_id,account_id,versions.get(region_id))
                    logger.info(f'[{index}/{len_update_ids}] {region_id}-{account_id} | {result}')
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
        logger.info('The process is closing')