import fakeredis.aioredis
import httpx
import pytest
from cryptography.fernet import Fernet

from app.config import Settings, get_settings
from app.main import create_app


@pytest.fixture(scope="session")
def settings() -> Settings:
    base = get_settings()
    assert base.test_database_url, "TEST_DATABASE_URL 未设置"
    return base.model_copy(
        update={
            "database_url": base.test_database_url,
            "master_key": Fernet.generate_key().decode(),
        }
    )


@pytest.fixture
async def app(settings):
    app = create_app(settings)
    await app.state.redis.aclose()
    app.state.redis = fakeredis.aioredis.FakeRedis()
    yield app
    await app.state.redis.aclose()
    await app.state.engine.dispose()


@pytest.fixture
async def client(app):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
