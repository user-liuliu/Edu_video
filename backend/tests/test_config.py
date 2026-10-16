import pytest
from cryptography.fernet import Fernet
from pydantic import ValidationError

from app.config import Settings

GOOD_SECRET = "s" * 32


def _settings(**overrides) -> Settings:
    kwargs = {
        "database_url": "postgresql+asyncpg://u:p@localhost/db",
        "redis_url": "redis://localhost:6379/0",
        "master_key": Fernet.generate_key().decode(),
        "session_secret": GOOD_SECRET,
    }
    kwargs.update(overrides)
    return Settings(**kwargs)


def test_valid_secrets_accepted():
    assert _settings().session_secret == GOOD_SECRET


@pytest.mark.parametrize("value", ["", "short", " " * 40])
@pytest.mark.parametrize("field", ["session_secret", "master_key"])
def test_blank_or_short_secret_rejected(field, value):
    with pytest.raises(ValidationError):
        _settings(**{field: value})


def test_malformed_master_key_rejected():
    """长度够但不是合法的 Fernet key：启动时就报错，提示里不带 key 本身。"""
    bad = "x" * 44
    with pytest.raises(ValidationError) as exc:
        _settings(master_key=bad)
    assert "MASTER_KEY" in str(exc.value)
    assert bad not in str(exc.value)
