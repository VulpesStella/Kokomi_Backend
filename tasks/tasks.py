from .main import celery_app
from .scripts import refresh_user


@celery_app.task(name="user_refresh")
def task_update_user_data(user_id: dict):
    """更新用户数据库的数据"""
    account_id = user_id['uid']
    result = refresh_user(account_id)
    return f'{account_id} | {result}'