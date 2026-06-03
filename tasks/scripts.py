import random

from .middlewares import redis_client, lock_client, db_pool, session
from .syncer import UserStatsSyncer
from .utils import get_current_iso_time
from .exception import handle_program_exception_sync
from .settings import VORTEX_API


def fetch_data(url: str, params: dict = None):
    try:
        resp = session.get(url, params=params, timeout=5)
        if resp.status_code == 200:
            result = resp.json()
            if result.get('status') == 'ok':
                return result.get('data', {})
            else:
                return "Game_API_Failed"
        elif resp.status_code == 404:
            return {}
        return f'HTTP_STATUS_{resp.status_code}'
    except Exception as e:
        return f'ERROR_{type(e).__name__}'

@handle_program_exception_sync
def refresh_user(account_id: int):
    now_date = get_current_iso_time()[:10]
    redis_client.incr(f"metrics:celery:annual:{now_date[:4]}")
    redis_client.incr(f"metrics:celery:monthly:{now_date[:7]}")
    redis_client.incr(f'metrics:celery:daily:total:{now_date}')

    # 删除redis的key
    lock_client.delete(f"refresh_lock:user:{account_id}")

    # 请求接口
    redis_key = f"token:ac:{account_id}"
    ac = redis_client.get(redis_key)

    base_url = random.choice(VORTEX_API)
    url = f'{base_url}/api/accounts/{account_id}/' + (f'?ac={ac}' if ac else '')
    response = fetch_data(url)

    redis_client.incr(f"metrics:http:annual:{now_date[:4]}")
    redis_client.incr(f"metrics:http:monthly:{now_date[:7]}")
    redis_client.incr(f"metrics:http:daily:total:{now_date}")
    if isinstance(response, str):
        redis_client.incr(f"metrics:http:daily:error:{now_date}")
        return response  

    with db_pool.connection() as conn:
        result = UserStatsSyncer.refresh(conn, account_id, response)
    
    if isinstance(result, str):
        redis_client.incr(f'metrics:celery:daily:error:{now_date}')
        return result
    else:
        return 'Success'