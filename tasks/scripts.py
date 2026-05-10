import os
import random
import requests
from datetime import datetime, timezone

from .exception import handle_program_exception_sync
from .middlewares import redis_client, db_pool
from .syncer import UserStatsSyncer, ClanUsersSyncer
from .settings import (
    VORTEX_API, 
    CLAN_API
)


os.environ['NO_PROXY'] = '127.0.0.1,localhost'

def now_utc_date() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")[0:10]

def fetch_data(url: str, params: dict = None):
    try:
        resp = requests.get(url, params=params, timeout=5)
        if resp.status_code == 200:
            result = resp.json()
            return result
        elif resp.status_code == 404:
            return {}
        return f'HTTP_STATUS_{resp.status_code}'
    except Exception as e:
        return f'ERROR_{type(e).__name__}'

@handle_program_exception_sync
def refresh_user(account_id: int):
    now_date = now_utc_date()
    redis_client.incr(f'metrics:celery:{now_date}')
    # 删除redis的key
    key = f"refresh_lock:user:{account_id}"
    redis_client.delete(key)
    # 请求接口
    redis_key = f"token:ac:{account_id}"
    ac = redis_client.get(redis_key)
    base_url = random.choice(VORTEX_API)
    url = f'{base_url}/api/accounts/{account_id}/' + (f'?ac={ac}' if ac else '')
    response = fetch_data(url)
    key = f"metrics:http_total:{now_date}"
    redis_client.incr(key)
    if isinstance(response, str):
        key = f"metrics:http_error:{now_date}"
        redis_client.incr(key)
        return response  
    # 处理异常情况
    if response.get('status') != 'ok':
        return 'GameAPI Error'
    response = response.get('data', {})
    conn = db_pool.connection()
    result = UserStatsSyncer.refresh(conn, account_id, response)
    return result if isinstance(result, str) else 'Success'

@handle_program_exception_sync
def refresh_clan(clan_id: int):
    # metrics
    now_date = now_utc_date()
    redis_client.incr(f'metrics:celery:{now_date}')
    # 先删除redis的key
    key = f"refresh_lock:clan:{clan_id}"
    redis_client.delete(key)
    url = f'{CLAN_API}/api/members/{clan_id}/'
    response = fetch_data(url)
    key = f"metrics:http_total:{now_date}"
    redis_client.incr(key)
    if isinstance(response, str):
        key = f"metrics:http_error:{now_date}"
        redis_client.incr(key)
        return response
    # 处理异常情况
    if response.get('status') != 'ok':
        return 'GameAPI Error'
    conn = db_pool.connection()
    result = ClanUsersSyncer.refresh(conn, clan_id, response)
    return result if isinstance(result, str) else 'Success'