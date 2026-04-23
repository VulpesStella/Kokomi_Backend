#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import pymysql
import asyncio

from logger import logger
from settings import (
    CLIENT_NAME, REFRESH_INTERVAL, 
    MYSQL_CONFIG, REGION
)
from utils import (
    read_version,
    analyze_db_files,
    process_region_stats
)

async def main():
    while True:
        start = time.monotonic()
        mysql_connection = pymysql.connect(**MYSQL_CONFIG)
        try:
            game_version = read_version()
            logger.info('Analyzing SQLite3 Files...')
            db_result = analyze_db_files()
            logger.info(db_result)
            process_region_stats(mysql_connection, game_version)
        except Exception:
            pass
        finally:
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