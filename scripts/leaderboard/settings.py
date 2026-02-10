import os
from dotenv import load_dotenv


load_dotenv()

CLIENT_NAME = 'Leaderboard'
LOG_LEVEL = 'debug'
LOG_DIR = '/app/logs'
DATA_DIR = '/app/data'
REFRESH_INTERVAL = 600
BATCH_SIZE = 1000

SEASON_ID=32
SEASON_START=1764568800
SEASON_FINISH=1770616800

LOG_DIR = r'F:\Kokomi_PJ_API\logs'
DATA_DIR = r'F:\Kokomi_PJ_API\data'

MYSQL_HOST = '127.0.0.1'
MYSQL_PORT = 3306
MYSQL_USERNAME = 'root'
MYSQL_PASSWORD = 'qazwsxedc0258'

MAIN_DB = 'game_test'

REDIS_HOST = '127.0.0.1'
REDIS_PORT = 6379
REDIS_PASSWORD = 'qazwsxedc0258'

# SEASON_ID = os.getenv("SEASON_ID")
# SEASON_START = os.getenv("SEASON_START")
# SEASON_FINISH = os.getenv("SEASON_FINISH")

# MYSQL_HOST = os.getenv("MYSQL_HOST")
# MYSQL_PORT = int(os.getenv("MYSQL_PORT", 3306))
# MYSQL_USERNAME = os.getenv("MYSQL_USERNAME")
# MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD")

# MAIN_DB = os.getenv("MAIN_DB")

# REDIS_HOST = os.getenv("REDIS_HOST")
# REDIS_PORT = os.getenv("REDIS_PORT")
# REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")