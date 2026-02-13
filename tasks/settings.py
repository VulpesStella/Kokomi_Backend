import os
from pathlib import Path
from celery.app.base import logger


if os.getenv('PLATFORM') is None:
    from dotenv import load_dotenv
    load_result = load_dotenv('.env.dev')
    logger.info(f"Env config loaded: .env.dev")
else:
    logger.info(f"Env config loaded: .env.prod")

LOG_DIR = Path(os.getenv("LOG_DIR"))
MYSQL_CONFIG = {
    "host": os.getenv("MYSQL_HOST"),
    "port": int(os.getenv("MYSQL_PORT", 3306)),
    "user": os.getenv("MYSQL_USERNAME"),
    "password": os.getenv("MYSQL_PASSWORD"),
    "database": os.getenv("MYSQL_DATABASE")
}
REDIS_CONFIG = {
    "host": os.getenv("REDIS_HOST"),
    "port": int(os.getenv("REDIS_PORT", 6379)),
    "db": 0,
    "password": os.getenv("REDIS_PASSWORD"),
    "decode_responses": True
}
RABBITMQ_CONFIG = {
    "host": os.getenv("RABBITMQ_HOST"),
    "user": os.getenv("RABBITMQ_USERNAME"),
    "password": os.getenv("RABBITMQ_PASSWORD")
}