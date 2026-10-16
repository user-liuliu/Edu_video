from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """从环境变量读取配置（本地用 `uv run --env-file ../.env` 注入 .env）。"""

    model_config = SettingsConfigDict(extra="ignore")

    database_url: str
    test_database_url: str = ""
    redis_url: str
    master_key: str
    session_secret: str
    cookie_secure: bool = False
    initial_admin_username: str | None = None
    initial_admin_password: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
