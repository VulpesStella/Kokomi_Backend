#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import redis
import httpx
import pymysql
import asyncio

from logger import logger
from settings import (
    CLIENT_NAME, REFRESH_INTERVAL, 
    MYSQL_CONFIG, REDIS_CONFIG,
    REGION
)
from update import update_user_recent
from utils import (
    get_recent_update_ids,
    get_private_update_ids,
    update_user_private,
    get_token_update_ids,
    update_user_token,
    db_stats
)

async def main():
    while True:
        start = time.monotonic()
        TIMEOUT = httpx.Timeout(connect = 2.0,read = 10.0,write = 3.0,pool = 2.0)
        async_client = httpx.AsyncClient(timeout=TIMEOUT)
        redis_client = redis.Redis(**REDIS_CONFIG)
        redis_client.set(f'status:{CLIENT_NAME}', 1, ex=int(REFRESH_INTERVAL*1.1))
        mysql_connection = pymysql.connect(**MYSQL_CONFIG)
        try:
            update_ids = get_recent_update_ids(mysql_connection)
            len_update_ids = len(update_ids)
            logger.info(f'Recent Update Numbers: {len_update_ids}')
            for index, update_id in enumerate(update_ids, 1):
                result = await update_user_recent(
                    mysql_connection,redis_client,async_client,update_id[0],update_id[1]
                )
                logger.info(f"[{index}/{len_update_ids}] {REGION}-{update_id[0]} | {result}")
            update_ids = get_private_update_ids(mysql_connection, redis_client)
            len_update_ids = len(update_ids)
            logger.info(f'Private Update Numbers: {len_update_ids}')
            for index, update_id in enumerate(update_ids, 1):
                result = await update_user_private(mysql_connection,redis_client,async_client,update_id[0],update_id[1])
                logger.info(f'[{index}/{len_update_ids}] {REGION}-{update_id[0]} | {result}')
            update_ids = get_token_update_ids(mysql_connection, redis_client)
            len_update_ids = len(update_ids)
            logger.info(f'Token Update Numbers: {len_update_ids}')
            for index, update_id in enumerate(update_ids, 1):
                result = await update_user_token(redis_client, update_id[0],update_id[1],update_id[2])
                logger.info(f'[{index}/{len_update_ids}] {update_id[0]}-{update_id[1]} | {result}')
            db_stats()
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
    logger.info(f'Start running service {CLIENT_NAME}')
    logger.info(f'Current region: {REGION.upper()}')
    if os.name != "nt":
        import signal
        signal.signal(signal.SIGTERM, handler)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info('The process is closing')