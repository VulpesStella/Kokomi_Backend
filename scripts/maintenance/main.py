#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import time
import redis
import pymysql
import asyncio
from tqdm import tqdm
from celery import Celery
from datetime import datetime

from logger import logger
from settings import (
    CLIENT_NAME, REFRESH_INTERVAL, 
    MYSQL_CONFIG, REDIS_CONFIG,
    RABBITMQ_CONFIG, REGION, DATA_DIR, DATE_FMT, USE_TQDM
)
from utils import (
    read_version_data,
    maintenance_database,
    get_user_update_ids,
    get_clan_update_ids,
    get_least_version
)

async def main():
    broker_url = f"pyamqp://{RABBITMQ_CONFIG['user']}:{RABBITMQ_CONFIG['password']}@{RABBITMQ_CONFIG['host']}/"
    celery_app = Celery(
        'producer',
        broker=broker_url,
        broker_connection_retry_on_startup=True
    )
    while True:
        start = time.monotonic()
        redis_client = redis.Redis(**REDIS_CONFIG)
        redis_client.set(f'status:{CLIENT_NAME}', 1, ex=int(REFRESH_INTERVAL*1.1))
        mysql_connection = pymysql.connect(**MYSQL_CONFIG)
        try:
            now_ts = int(time.time())
            # 1.检测数据库是否存在脏数据行
            fixed_count = maintenance_database(mysql_connection)
            if fixed_count != 0:
                logger.info(f'Fixed Row Counts: {fixed_count}')
            # 2.每小时检测游戏版本是否更新
            local_version = read_version_data()
            version_refresh_time = local_version.get('update_time', 0)
            if now_ts - version_refresh_time > 3600:
                version_data = get_least_version(redis_client)
                if isinstance(version_data, str):
                    logger.info(f'Read version error: {version_data}')
                elif local_version.get('short') != version_data['short']:
                    version_result = {
                        'update_time': now_ts,
                        'short': version_data['short'],
                        'full': version_data['full'],
                        'start': now_ts
                    }
                    file_path = DATA_DIR / f"json/game_version.json"
                    with open(file_path, "w", encoding="utf-8") as f:
                        json.dump(version_result, f, ensure_ascii=False)
                    logger.info(f"Game Version: {local_version.get('short')} -> {version_data['short']}")
                else:
                    version_result = {
                        'update_time': now_ts,
                        'short': version_data['short'],
                        'full': version_data['full'],
                        'start': local_version.get('start')
                    }
                    file_path = DATA_DIR / f"json/game_version.json"
                    with open(file_path, "w", encoding="utf-8") as f:
                        json.dump(version_result, f, ensure_ascii=False)
                    logger.info(f"Game Version: {version_data['short']} -> Latest")
            else:
                logger.debug('Skip to refresh version data step')
            # 3.更新玩家的基本数据
            update_ids = get_user_update_ids(mysql_connection, redis_client)
            len_update_ids = len(update_ids)
            logger.info(f'User Update Numbers: {len_update_ids}')
            if len_update_ids > 0:
                failed_count = 0
                if USE_TQDM:
                    iterator = tqdm(
                        update_ids, 
                        total=len_update_ids, 
                        desc=f"{datetime.now().strftime(DATE_FMT)} [INFO] User Updating"
                    )
                else:
                    iterator = enumerate(update_ids, 1)
                for item in iterator:
                    if USE_TQDM:
                        update_id = item
                        _ = iterator.n
                    else:
                        _, update_id = item
                    try:
                        celery_app.send_task(
                            name='user_refresh',
                            args=[{'uid': update_id}],
                            queue='refresh_queue'
                        )
                        if USE_TQDM:
                            iterator.set_postfix_str(f"{REGION}-{update_id} | Success")
                    except Exception as e:
                        # 发送失败，释放锁
                        fixed_count += 1
                        redis_client.delete(f"refresh_lock:user:{update_id}")
                        if USE_TQDM:
                            iterator.set_postfix_str(f"{REGION}-{update_id} | Failed")
                logger.info(f'Task sent complete, Success: {len_update_ids - failed_count}  Failed: {failed_count}')
            # 4.更新工会的会内玩家数据
            update_ids = get_clan_update_ids(mysql_connection, redis_client)
            len_update_ids = len(update_ids)
            logger.info(f'Clan Update Numbers: {len_update_ids}')
            if len_update_ids > 0:
                failed_count = 0
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
                        _ = iterator.n
                    else:
                        _, update_id = item
                    try:
                        celery_app.send_task(
                            name='clan_refresh',
                            args=[{'uid': update_id}],
                            queue='refresh_queue'
                        )
                        if USE_TQDM:
                            iterator.set_postfix_str(f"{REGION}-{update_id} | Success")
                    except Exception as e:
                        # 发送失败，释放锁
                        fixed_count += 1
                        redis_client.delete(f"refresh_lock:clan:{update_id}")
                        if USE_TQDM:
                            iterator.set_postfix_str(f"{REGION}-{update_id} | Failed")
                logger.info(f'Task sent complete, Success: {len_update_ids - failed_count}  Failed: {failed_count}')
        except Exception:
            pass
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
    logger.info(f'Start running service: {CLIENT_NAME}')
    logger.info(f'Service refresh interval: {REFRESH_INTERVAL} seconds')
    logger.info(f'Current node region: {REGION.upper()}')
    if os.name != "nt":
        import signal
        signal.signal(signal.SIGTERM, handler)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info('The process is closing')