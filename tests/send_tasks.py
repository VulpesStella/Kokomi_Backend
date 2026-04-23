import os
import argparse
from celery import Celery
from dotenv import load_dotenv


load_dotenv('env.dev')

RABBITMQ_CONFIG = {
    "host": os.getenv("RABBITMQ_HOST"),
    "user": os.getenv("RABBITMQ_DEFAULT_USER"),
    "password": os.getenv("RABBITMQ_DEFAULT_PASS")
}

def create_celery():
    return Celery(
        'producer',
        broker=f"pyamqp://{RABBITMQ_CONFIG['user']}:{RABBITMQ_CONFIG['password']}@{RABBITMQ_CONFIG['host']}//",
        broker_connection_retry_on_startup=True
    )

def send_task(task_name: str, task_id: int):
    celery_app = create_celery()
    if task_name == 'user':
        task_tag = 'user_refresh'
        args = [{'uid': task_id}]
    elif task_name == 'clan':
        task_tag = 'clan_refresh'
        args = [{'uid': task_id}]
    else:
        raise ValueError(f"Unknown task name: {task_name}")
    celery_app.send_task(
        name=task_tag,
        args=args,
        queue='refresh_queue'
    )
    print(f'Success: {task_tag} -> {task_id}')
    celery_app.close()

if __name__ == '__main__':
    """用于在本地开发环境中，手动发送 Celery 任务。

    参数说明：
    -t / --task  : Celery 任务名
    -i / --id    : 任务 UID

    使用示例：
    python tests/send_tasks.py -t clan -i 7000005269
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('-t', '--task', required=True, help='Task name, `user` or `clan`')
    parser.add_argument('-i', '--id', required=True, type=int, help='Task UID')
    args = parser.parse_args()
    send_task(args.task, args.id)