#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import redis
import pymysql
from tqdm import tqdm
from datetime import datetime

from logger import logger
from settings import (
    CLIENT_NAME, REFRESH_INTERVAL, 
    MYSQL_CONFIG, REDIS_CONFIG, REGION, DATE_FMT, USE_TQDM, CLAN_REALM_MAP, CLAN_LEAGUE_LIST
)
from utils import (
    read_season_data,
    ensure_clan_battle_table,
    is_cb_active, 
    get_update_ids, 
    get_clan_rank_data,
    regresh_clan_league, 
    update_clan_season
)


def main():
    last_refresh_time = 0
    while True:
        start = time.monotonic()
        redis_client = redis.Redis(**REDIS_CONFIG)
        redis_client.set(f'status:{CLIENT_NAME}', 1, ex=int(REFRESH_INTERVAL*1.1))
        conn = pymysql.connect(**MYSQL_CONFIG)
        try:
            # 俄服clan battle在s28后被rating战所替代
            # SEASON_ID, SEASON_FINISH, SEASON_START = 28, 1739944800, 1744005600
            season_data = read_season_data()
            SEASON_ID = season_data['id']
            ensure_clan_battle_table(conn, SEASON_ID)
            logger.info(f"Current Season ID: {SEASON_ID}")
            now_ts = int(time.time())
            # 最低每天刷新一次
            if (
                now_ts - last_refresh_time > 24*60*60 or 
                is_cb_active(now_ts, season_data['start'], season_data['finish'])
            ):
                total_list = []
                success_count = 0
                len_update_ids = len(CLAN_LEAGUE_LIST)
                if USE_TQDM:
                    iterator = tqdm(
                        CLAN_LEAGUE_LIST, 
                        total=len_update_ids, 
                        desc=f"{datetime.now().strftime(DATE_FMT)} [INFO] Clan Updating"
                    )
                else:
                    iterator = enumerate(CLAN_LEAGUE_LIST, 1)
                for item in iterator:
                    if USE_TQDM:
                        update_data = item
                        index = iterator.n
                    else:
                        index, update_data = item
                    league_data = get_clan_rank_data(
                        redis_client=redis_client,
                        realm=CLAN_REALM_MAP.get(REGION),
                        league=update_data[0],
                        division=update_data[1]
                    )
                    if type(league_data) == str:
                        result = league_data
                    else:
                        success_count += 1
                        result = f'+ {len(league_data)}'
                    total_list = total_list + league_data
                    if USE_TQDM:
                        iterator.set_postfix_str(f"{REGION}-{update_data[0]}-{update_data[1]} | {result}")
                    else:
                        logger.info(f'[{index}/{len_update_ids}] {REGION}-{update_data[0]}-{update_data[1]} | {result}')
                logger.info(f'Total Clan: {len(total_list)}')
                update_ids = get_update_ids(conn, SEASON_ID, total_list)
                len_update_ids = len(update_ids)
                logger.info(f'Update Numbers: {len_update_ids}')
                if len_update_ids > 0:
                    if USE_TQDM:
                        iterator = tqdm(
                            update_ids, 
                            total=len_update_ids, 
                            desc=f"{datetime.now().strftime(DATE_FMT)} [INFO] Clan Updating"
                        )
                    else:
                        iterator = enumerate(update_ids, 1)
                    for item in iterator:
                        if USE_TQDM:
                            update_id = item
                            index = iterator.n
                        else:
                            index, update_id = item
                        result = update_clan_season(redis_client, conn, SEASON_ID, update_id)
                        if USE_TQDM:
                            iterator.set_postfix_str(f"{REGION}-{update_id} | {result}")
                        else:
                            logger.info(f'[{index}/{len_update_ids}] {REGION}-{update_id} | {result}')
                if success_count == 13:
                    refresh_count = regresh_clan_league(conn, total_list)
                    logger.info(f'Refresh Clan: {refresh_count}')
                last_refresh_time = now_ts
            else:
                logger.info(f'Update time not yet reached')
        except Exception:
            pass
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
    logger.info(f'Start running service: {CLIENT_NAME}')
    logger.info(f'Service refresh interval: {REFRESH_INTERVAL} seconds')
    logger.info(f'Current node region: {REGION.upper()}')
    if os.name != "nt":
        import signal
        signal.signal(signal.SIGTERM, handler)
    try:
        main()
    except KeyboardInterrupt:
        logger.info('The process is closing')