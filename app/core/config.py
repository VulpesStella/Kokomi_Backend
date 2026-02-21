import os
import json
from pathlib import Path
from dataclasses import dataclass

@dataclass(frozen=True)
class RuntimeConfig:
    PLATFORM: str

    API_URL: str
    API_TOKEN: str
    BIND_HOST: list

    MYSQL_HOST: str
    MYSQL_PORT: int
    MYSQL_USERNAME: str
    MYSQL_PASSWORD: str
    MYSQL_DATABASE: str

    SQLITE_PATH: str
    
    REDIS_HOST: str
    REDIS_PORT: int
    REDIS_PASSWORD: str
    
    RABBITMQ_HOST: str
    RABBITMQ_USERNAME: int
    RABBITMQ_PASSWORD: str

    WG_API_TOKEN: str
    LESTA_API_TOKEN: str

@dataclass(frozen=True)
class EndpointsConfig:
    VORTEX_API: list
    CLAN_API: str
    OFFICIAL_API: str | None

class EnvConfig:
    config = None
    endpoints = None
    REGION = None
    DATA_DIR = Path('/app/data')
    LOG_DIR = Path('/app/logs')

    @classmethod
    def init(cls) -> str | None:
        env_file = 'env.prod'
        if os.getenv('PLATFORM') is None:
            from dotenv import load_dotenv
            load_result = load_dotenv('.env.dev')
            if load_result is False:
                return None
            env_file = '.env.dev'
        # 加载config
        cls.config = RuntimeConfig(
            PLATFORM = os.getenv('PLATFORM'),
            API_URL = os.getenv('API_URL'),
            API_TOKEN = os.getenv('API_TOKEN'),
            BIND_HOST = os.getenv('BIND_HOST').split('_'),
            MYSQL_HOST = os.getenv("MYSQL_HOST"),
            MYSQL_PORT = int(os.getenv("MYSQL_PORT", 3306)),
            MYSQL_USERNAME = os.getenv("MYSQL_USERNAME"),
            MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD"),
            MYSQL_DATABASE = os.getenv("MYSQL_DATABASE"),
            SQLITE_PATH = os.getenv("SQLITE_PATH"),
            REDIS_HOST = os.getenv("REDIS_HOST"),
            REDIS_PORT = os.getenv("REDIS_PORT"),
            REDIS_PASSWORD = os.getenv("REDIS_PASSWORD"),
            WG_API_TOKEN = os.getenv("WG_API_TOKEN"),
            LESTA_API_TOKEN = os.getenv("LESTA_API_TOKEN"),
            RABBITMQ_HOST = os.getenv("RABBITMQ_HOST"),
            RABBITMQ_USERNAME = os.getenv("RABBITMQ_USERNAME"),
            RABBITMQ_PASSWORD = os.getenv("RABBITMQ_PASSWORD")
        )
        cls.DATA_DIR = Path(os.getenv("DATA_DIR"))
        cls.LOG_DIR = Path(os.getenv("LOG_DIR"))
        file_path = cls.DATA_DIR / 'json/init_marker.json'
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            cls.REGION = data['region']
        file_path = cls.DATA_DIR / 'json/endpoints.json'
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            cls.endpoints = EndpointsConfig(
                VORTEX_API=data['vortex_api'],
                CLAN_API=data['clan_api'],
                OFFICIAL_API=data['official_api']
            )
        return env_file
