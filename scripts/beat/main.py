#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import time
import signal
import asyncio
import traceback

from logger import logger
from settings import CLIENT_NAME, REFRESH_INTERVAL
from middlewares import redis_client
from utils import get_update_ids, get_expiring_ids, update_user_private, update_user_token, process_region_stats


async def main():
    while True:
        # 设置一个key标记程序正在运行
        redis_client.set(f'status:{CLIENT_NAME}', 1, ex=REFRESH_INTERVAL+60)
        st = time.time() # 程序开始运行时间，计算后续休眠时间
        
        try:
            update_ids = get_update_ids()
            len_update_ids = len(update_ids)
            logger.info(f'Private Update Numbers: {len_update_ids}')
            index = 1
            for update_id in update_ids:
                result = await update_user_private(update_id[0],update_id[1],update_id[2])
                logger.info(f'[{index}/{len_update_ids}] {update_id[0]}-{update_id[1]} | {result}')
                index += 1
            update_ids = get_expiring_ids()
            len_update_ids = len(update_ids)
            logger.info(f'Token Update Numbers: {len_update_ids}')
            index = 1
            for update_id in update_ids:
                result = await update_user_token(update_id[0],update_id[1],update_id[2])
                logger.info(f'[{index}/{len_update_ids}] {update_id[0]}-{update_id[1]} | {result}')
                index += 1
        except:
            logger.error((f"{traceback.format_exc()}"))

        process_region_stats()
        
        ct = time.time() - st
        if ct < REFRESH_INTERVAL:
            logger.info(f'This loop took {round(ct,2)} seconds')
            logger.info(f'The process sleeps for {round(REFRESH_INTERVAL-ct,2)} seconds')
            logger.info('-'*70)
            time.sleep(REFRESH_INTERVAL-ct)

def handler(signum, frame):
    logger.info('The process is closing')
    exit(0)

if __name__ == "__main__":
    logger.info(f'Start running service {CLIENT_NAME}')
    signal.signal(signal.SIGTERM, handler)
    asyncio.run(main())