from typing import Annotated

import fakeredis.aioredis
import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi import Depends
from sqlalchemy import text

from app.auth import UserOut, require_active_user
from app.config import Settings, get_settings
from app.db import create_engine, create_sessionmaker
from app.main import create_app
from app.models import Base, User, UserRole, UserStatus
from app.security import hash_password


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


async def login(client: httpx.AsyncClient, username: str, password: str) -> None:
    """用账号密码登录；登录失败直接让测试失败。会话 cookie 保存在 client 上。"""
    r = await client.post("/api/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text


@pytest.fixture
async def app(settings):
    app = create_app(settings)
    await app.state.redis.aclose()
    app.state.redis = fakeredis.aioredis.FakeRedis()

    # 只用于测试的路由：检查 require_active_user 的拦截效果（生产代码里没有）
    @app.get("/api/_test/active")
    async def _test_active(user: Annotated[User, Depends(require_active_user)]) -> UserOut:
        return UserOut.model_validate(user)

    yield app
    await app.state.redis.aclose()
    await app.state.engine.dispose()


@pytest.fixture
async def client(app):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture(scope="session")
async def db_engine(settings):
    """整个测试会话建一次表：先 drop_all 再 create_all。"""
    engine = create_engine(settings.database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db(db_engine):
    """每个测试一个 AsyncSession；结束后清空所有表。"""
    async with create_sessionmaker(db_engine)() as session:
        try:
            yield session
        finally:
            await session.rollback()
    async with db_engine.begin() as conn:
        await conn.execute(text("TRUNCATE users, system_settings, model_configs CASCADE"))


@pytest.fixture
def make_user(db):
    """建用户并提交；用户名冲突时回滚会话后把 IntegrityError 抛出去。"""

    async def _make_user(
        username: str = "t1",
        password: str = "pass1234",
        role: str = "teacher",
        status: str = "active",
    ) -> User:
        user = User(
            username=username,
            password_hash=hash_password(password),
            role=UserRole(role),
            status=UserStatus(status),
        )
        db.add(user)
        try:
            await db.commit()
        except Exception:
            await db.rollback()
            raise
        return user

    return _make_user
