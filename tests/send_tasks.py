import os
from celery import Celery
from dotenv import load_dotenv


load_dotenv('env.dev')

RABBITMQ_CONFIG = {
    "host": os.getenv("RABBITMQ_HOST"),
    "user": os.getenv("RABBITMQ_DEFAULT_USER"),
    "password": os.getenv("RABBITMQ_DEFAULT_PASS")
}

if __name__ == '__main__':
    celery_app = Celery(
        'producer',
        broker=f"pyamqp://{RABBITMQ_CONFIG['user']}:{RABBITMQ_CONFIG['password']}@{RABBITMQ_CONFIG['host']}//",
        broker_connection_retry_on_startup=True
    )
    # update_ids = [7059908736]
    # for update_id in update_ids:
    #     celery_app.send_task(
    #         name='user_refresh', 
    #         args=[{'account_id': update_id}], 
    #         queue='refresh_queue'
    #     )
    update_ids = [7000002516]
    for update_id in update_ids:
        celery_app.send_task(
            name='clan_refresh', 
            args=[{'clan_id': update_id}], 
            queue='refresh_queue'
        )
    print('Success')
    celery_app.close()