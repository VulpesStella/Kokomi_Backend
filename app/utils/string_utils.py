import secrets
import string
import re


class StringUtils:
    @staticmethod
    def parse_insignias(insignia_str: str | None) -> dict:
        """从标识字符串解析回 DogTag 数据"""
        if insignia_str is None:
            return None
        
        parts = insignia_str.split("-")
        
        keys = [
            "texture_id",
            "symbol_id",
            "border_color_id",
            "background_color_id",
            "background_id"
        ]
        
        if len(parts) != len(keys):
            return None
        
        return {key: int(part) for key, part in zip(keys, parts)}

    @staticmethod
    def generate_activation_code(length=12):
        # 生成激活码(不效验)
        chars = string.ascii_uppercase + string.digits  # 大写字母 + 数字
        return ''.join(secrets.choice(chars) for _ in range(length))

    @staticmethod
    def is_valid_activation_code(code: str) -> bool:
        # 效验激活码格式
        if not code:
            return False
        return bool(re.compile(r'^[A-Z0-9]{12}$').fullmatch(code))