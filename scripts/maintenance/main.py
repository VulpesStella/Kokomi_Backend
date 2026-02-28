#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import time
import redis
import pymysql
import asyncio
from celery import Celery

from logger import logger
from settings import (
    CLIENT_NAME, REFRESH_INTERVAL, 
    MYSQL_CONFIG, REDIS_CONFIG,
    RABBITMQ_CONFIG, REGION, DATA_DIR
)
from utils import (
    maintenance_database,
    get_user_update_ids,
    get_clan_update_ids,
    get_version,
    process_region_stats
)

async def main():
    celery_app = Celery(
        'producer',
        broker=f"pyamqp://{RABBITMQ_CONFIG['user']}:{RABBITMQ_CONFIG['password']}@{RABBITMQ_CONFIG['host']}//",
        broker_connection_retry_on_startup=True
    )
    version_refresh_time = 0
    stats_refresh_time = 0
    while True:
        start = time.monotonic()
        redis_client = redis.Redis(**REDIS_CONFIG)
        redis_client.set(f'status:{CLIENT_NAME}', 1, ex=int(REFRESH_INTERVAL*1.1))
        mysql_connection = pymysql.connect(**MYSQL_CONFIG)
        try:
            fixed_count = maintenance_database(mysql_connection)
            logger.info(f'Fixed Row Counts: {fixed_count}')
            update_ids = get_user_update_ids(mysql_connection, redis_client)
            logger.info(f'User Update Numbers: {len(update_ids)}')
            for update_id in update_ids:
                celery_app.send_task(
                    name='user_refresh', 
                    args=[{'account_id': update_id}], 
                    queue='refresh_queue'
                )
            logger.info(f'Task sent complete')
            update_ids = get_clan_update_ids(mysql_connection, redis_client)
            logger.info(f'Clan Update Numbers: {len(update_ids)}')
            for update_id in update_ids:
                celery_app.send_task(
                    name='clan_refresh', 
                    args=[{'clan_id': update_id}], 
                    queue='refresh_queue'
                )
            logger.info(f'Task sent complete')
            now_ts = int(time.time())
            if now_ts - version_refresh_time > 3600:
                version_data = get_version(redis_client)
                if isinstance(version_data, str):
                    logger.info(f'Game Version: {version_data}')
                else:
                    file_path = DATA_DIR / f"json/version.json"
                    with open(file_path, "w", encoding="utf-8") as f:
                        json.dump(version_data, f, ensure_ascii=False)
                    logger.info(f"Game Version: {version_data['version']}")
                    version_refresh_time = now_ts
            # if now_ts - stats_refresh_time > 6*3600:
            #     process_region_stats(mysql_connection)
            #     stats_refresh_time = now_ts
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
    logger.info(f'Current region: {REGION.upper()}')
    if os.name != "nt":
        import signal
        signal.signal(signal.SIGTERM, handler)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info('The process is closing')