#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import redis
import pymysql

from logger import logger
from settings import (
    CLIENT_NAME, REFRESH_INTERVAL, 
    MYSQL_CONFIG, REDIS_CONFIG
)
from utils import (
    Status,
    get_region,
    get_season,
    is_cb_active, 
    get_update_ids, 
    get_clan_rank_data, 
    get_clan_cvc_data, 
    update_clan_season
)


def main():
    while True:
        start = time.monotonic()
        redis_client = redis.Redis(**REDIS_CONFIG)
        redis_client.set(f'status:{CLIENT_NAME}', 1, ex=int(REFRESH_INTERVAL*1.1))
        conn = pymysql.connect(**MYSQL_CONFIG)
        try:
            # 俄服clan battle在s28后被rating战所替代
            # SEASON_ID, SEASON_FINISH, SEASON_START = 28, 1739944800, 1744005600
            # logger.info(f"Season ID: {SEASON_ID}")
            # if is_cb_active(int(time.time()), SEASON_START, SEASON_FINISH):
            #     total_list = []
            #     for region_id in [4]:
            #         region_list = get_clan_rank_data(redis_client, region_id)
            #         logger.info(f'Regional clan: {get_region(region_id).capitalize()}({len(region_list)})')
            #         total_list = total_list + region_list
            #     logger.info(f'Total Clan: {len(total_list)}')
            #     update_ids = get_update_ids(conn, SEASON_ID, total_list)
            #     len_update_ids = len(update_ids)
            #     logger.info(f'Update Numbers: {len_update_ids}')

            SEASON_ID, SEASON_FINISH, SEASON_START = get_season(conn)
            logger.info(f"Season ID: {SEASON_ID}")
            if is_cb_active(int(time.time()), SEASON_START, SEASON_FINISH):
                total_list = []
                # 俄服不计入
                for region_id in [1,2,3,5]:
                    region_list = get_clan_rank_data(redis_client, region_id)
                    logger.info(f'Regional clan: {get_region(region_id).capitalize()}({len(region_list)})')
                    total_list = total_list + region_list
                logger.info(f'Total Clan: {len(total_list)}')
                update_ids = get_update_ids(conn, SEASON_ID, total_list)
                len_update_ids = len(update_ids)
                logger.info(f'Update Numbers: {len_update_ids}')
                for index, clan_info in enumerate(update_ids, 1):
                    region_id = clan_info[0]
                    clan_id = clan_info[1]
                    result = get_clan_cvc_data(redis_client, SEASON_ID, region_id, clan_id)
                    if type(result) == str:
                        logger.info(f'[{index}/{len_update_ids}] {region_id}-{clan_id} | {result}')
                    else:
                        update_result = update_clan_season(conn, SEASON_ID, result)
                        logger.info(f'[{index}/{len_update_ids}] {region_id}-{clan_id} | {update_result}')
            else:
                logger.info(f'Update time not yet reached')
        finally:
            redis_client.close()
            conn.close()
        if Status.FirstLoop == True:
            Status.set_status()
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
        main()
    except KeyboardInterrupt:
        logger.info('The process is closing')