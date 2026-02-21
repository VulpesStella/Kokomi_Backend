from .main import celery_app
from .scripts import refresh_user, refresh_clan


@celery_app.task(name="user_refresh")
def task_update_user_data(user_id: dict):
    """更新用户数据库的数据"""
    account_id = user_id['account_id']
    result = refresh_user(account_id)
    return f'U_{account_id} | {result}'

@celery_app.task(name="clan_refresh")
def task_update_user_data(user_id: dict):
    """更新工会数据库的数据"""
    clan_id = user_id['clan_id']
    result = refresh_clan(clan_id)
    return f'C_{clan_id} | {result}'