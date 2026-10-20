from functools import lru_cache

from cryptography.fernet import Fernet
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """从环境变量读取配置（本地用 `uv run --env-file ../.env` 注入 .env）。"""

    # hide_input_in_errors：配置校验失败时错误信息里不带原值（主密钥、会话密钥会出现在容器日志里）
    model_config = SettingsConfigDict(extra="ignore", hide_input_in_errors=True)

    database_url: str = Field(repr=False)
    test_database_url: str = Field(default='',repr=False)
    redis_url: str = Field(repr=False)
    # 会话 cookie 靠 session_secret 签名，主密钥（Fernet key，44 位）用来加密模型 key：
    # 都不能为空或过短，否则启动时直接报错
    master_key: str = Field(min_length=32,repr=False)
    session_secret: str = Field(min_length=32,repr=False)
    cookie_secure: bool = False
    minio_endpoint: str = ''
    minio_access_key: str = Field(default='',repr=False)
    minio_secret_key: str = Field(default='',repr=False)
    minio_secure: bool = False
    minio_bucket: str = 'edu-materials'
    temp_dir: str = '/tmp'
    renderer_url: str = ''
    agent_schema: str = 'agent_state'
    upload_file_bytes: int = 25 * 1024 * 1024
    upload_project_bytes: int = 100 * 1024 * 1024
    upload_project_files: int = 10
    initial_admin_username: str | None = None
    initial_admin_password: str | None = Field(default=None,repr=False)

    @field_validator("master_key", "session_secret")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("不能为空白")
        return v

    @field_validator("master_key")
    @classmethod
    def _valid_fernet_key(cls, v: str) -> str:
        # 格式不对时 SecretBox 会在启动后才报错，容器反复重启；这里提前给出明确提示（不带 key 本身）
        try:
            Fernet(v)
        except (ValueError, TypeError):
            raise ValueError("MASTER_KEY 不是有效的 Fernet key，请用 .env.example 中的命令重新生成") from None
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
