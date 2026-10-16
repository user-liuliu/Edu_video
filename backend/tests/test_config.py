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
