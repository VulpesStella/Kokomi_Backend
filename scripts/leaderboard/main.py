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
    get_season,
    read_ship_tier,
    read_ship_server,
    get_update_ids,
    process_clan,
    process_user,
    update_user_cache
)


async def main():
    while True:
        start = time.monotonic()
        redis_client = redis.Redis(**REDIS_CONFIG)
        redis_client.set(f'status:{CLIENT_NAME}', 1, ex=int(REFRESH_INTERVAL*1.1))
        conn = pymysql.connect(**MYSQL_CONFIG)
        try:
            SEASON_ID = get_season(conn)
            ship_tier_data = read_ship_tier()
            ship_server_data = read_ship_server()
            # update_ids = get_update_ids(conn)
            # len_update_ids = len(update_ids)
            # logger.info(f'Update Numbers: {len_update_ids}')
            # for index, update_id in enumerate(update_ids, 1):
            #     result = update_user_cache(conn, ship_tier_data, update_id[0], update_id[1])
            #     logger.info(f"[{index}/{len_update_ids}] {update_id[0]}-{update_id[1]} | {result}")
            # result = process_clan(conn, SEASON_ID)
            # logger.info(f"Leaderboard(Clan): {result}")
            result = process_user(ship_server_data)
            logger.info(f"Leaderboard(User): {result}")
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