import time
import json
import shutil
from typing import Any

from app.core import EnvConfig



class JsonUtils:
    """
    负责读取和写入json文件
    """
    @staticmethod
    def read(filename: str) -> dict:
        """读取json文件数据"""
        file_path = EnvConfig.DATA_DIR / f"json/{filename}.json"
        if not file_path.exists():
            return {}
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)

    # @staticmethod
    # def write(filename: str, data: Any) -> None:
    #     """刷新json文件数据，写入前备份一份旧数据到备份文件夹内"""
    #     file_path = file_path = EnvConfig.DATA_DIR / f"json/{filename}.json"
    #     if file_path.exists():
    #         backup_name = f"{filename}_{int(time.time())}.json"
    #         backup_path = EnvConfig.DATA_DIR / f"backup/{backup_name}"
    #         shutil.copy2(file_path, backup_path)
    #     with open(file_path, "w", encoding="utf-8") as f:
    #         json.dump(data, f, ensure_ascii=False)
