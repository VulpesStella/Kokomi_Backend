import json

from app.core import EnvConfig



class JsonUtils:
    """
    负责读取和写入json文件
    """
    def read(filename: str) -> dict:
        """读取json文件数据"""
        file_path = EnvConfig.DATA_DIR / f"json/{filename}.json"
        if not file_path.exists():
            return {}
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
