import sqlite3
from pathlib import Path
from sqlite3 import Connection

from app.core import EnvConfig

class SQLiteConnection:
    def get_recent_db_path(self, account_id: int,region_id: int) -> str:
        "获取db文件path"
        config = EnvConfig.config
        if config.SQLITE_PATH == 'default':
            return EnvConfig.DATA_DIR / f'db/{region_id}/{account_id}.db'
        else:
            return Path(config.SQLITE_PATH)
    