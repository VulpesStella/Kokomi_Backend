import sqlite3
from pathlib import Path
from sqlite3 import Connection

from app.core import EnvConfig

class SQLiteConnection:
    def get_recent_db_path(self, account_id: int) -> str:
        "获取db文件path"
        return EnvConfig.SQLITE_DIR / f'{account_id}.db'
    