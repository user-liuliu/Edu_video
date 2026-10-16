from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """从环境变量读取配置（本地用 `uv run --env-file ../.env` 注入 .env）。"""

    model_config = SettingsConfigDict(extra="ignore")

    database_url: str
    test_database_url: str = ""
    redis_url: str
    # 会话 cookie 靠 session_secret 签名，主密钥（Fernet key，44 位）用来加密模型 key：
    # 都不能为空或过短，否则启动时直接报错
    master_key: str = Field(min_length=32)
    session_secret: str = Field(min_length=32)
    cookie_secure: bool = False
    initial_admin_username: str | None = None
    initial_admin_password: str | None = None

    @field_validator("master_key", "session_secret")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("不能为空白")
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
