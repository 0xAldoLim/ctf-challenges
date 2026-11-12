import os

from pydantic_settings import BaseSettings


class Config(BaseSettings):
    SECRET_KEY: str = os.urandom(32).hex()
    DATABASE_URL: str = "postgresql://postgres:postgres@cloud-db:5432/task"
    REDIS_URL: str = "redis://cloud-redis:6379/0"
    APP_STORAGE_ROOT: str = "/home/cloud/storages"
    APP_RUNTIME_ROOT: str = "/home/cloud/runtime"


app_config = Config()
