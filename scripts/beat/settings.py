import os
from dotenv import load_dotenv


load_dotenv()

LOG_LEVEL = 'debug'
CLIENT_NAME = 'Beat'
LOG_DIR = '/app/logs'
DATA_DIR = '/app/data'
REFRESH_INTERVAL = 300

MYSQL_HOST = os.getenv("MYSQL_HOST")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", 3306))
MYSQL_USERNAME = os.getenv("MYSQL_USERNAME")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD")

MAIN_DB = os.getenv("MAIN_DB")

REDIS_HOST = os.getenv("REDIS_HOST")
REDIS_PORT = os.getenv("REDIS_PORT")
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")

WG_API_TOKEN = os.getenv("WG_API_TOKEN")
LESTA_API_TOKEN = os.getenv("LESTA_API_TOKEN")