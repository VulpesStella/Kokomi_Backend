#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import redis
import pymysql
import asyncio
from celery import Celery

from logger import logger
from settings import (
    CLIENT_NAME, REFRESH_INTERVAL, 
    MYSQL_CONFIG, REDIS_CONFIG,
    RABBITMQ_CONFIG
)
from utils import (
    get_update_ids,
    refresh_online_player,
    refresh_game_version
)

async def main():
    celery_app = Celery(
        'producer',
        broker=f"pyamqp://{RABBITMQ_CONFIG['user']}:{RABBITMQ_CONFIG['password']}@{RABBITMQ_CONFIG['host']}//",
        broker_connection_retry_on_startup=True
    )
    while True:
        start = time.monotonic()
        redis_client = redis.Redis(**REDIS_CONFIG)
        redis_client.set(f'status:{CLIENT_NAME}', 1, ex=int(REFRESH_INTERVAL*1.1))
        conn = pymysql.connect(**MYSQL_CONFIG)
        try:
            update_ids = get_update_ids(conn, redis_client)
            logger.info(f'Update Numbers: {len(update_ids)}')
            for update_id in update_ids:
                celery_app.send_task(
                    name='user_refresh', 
                    args=[{'region_id': update_id[0], 'account_id': update_id[1]}], 
                    queue='refresh_queue'
                )
            logger.info(f'Task sent complete')
            data = refresh_online_player(redis_client)
            if data:
                logger.info(f'Currently online: {data[0]}')
                logger.info(f'Asia({data[1]}) Eu({data[2]}) Na({data[3]}) Ru({data[4]}) Cn({data[5]})')
            data = refresh_game_version(conn, redis_client)
            if data:
                logger.info(f'Asia({data[0]}) Eu({data[1]}) Na({data[2]}) Ru({data[3]}) Cn({data[4]})')
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