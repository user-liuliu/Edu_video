from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.sessions import SessionMiddleware

from app.auth import router as auth_router
from app.config import Settings, get_settings
from app.db import create_engine, create_sessionmaker, get_session
from app.redis_client import create_redis


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield
    await app.state.redis.aclose()
    await app.state.engine.dispose()


def create_app(settings: Settings | None = None) -> FastAPI:
    """应用工厂。启动：uvicorn app.main:create_app --factory"""
    settings = settings or get_settings()

    app = FastAPI(title="教学视频 agent", lifespan=lifespan)
    app.state.settings = settings
    app.state.engine = create_engine(settings.database_url)
    app.state.sessionmaker = create_sessionmaker(app.state.engine)
    app.state.redis = create_redis(settings.redis_url)

    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret,
        session_cookie="ev_session",
        same_site="lax",
        https_only=settings.cookie_secure,
        max_age=14 * 24 * 3600,
    )

    @app.get("/api/health")
    async def health(db: Annotated[AsyncSession, Depends(get_session)]) -> dict:
        await db.execute(text("SELECT 1"))
        return {"status": "ok", "db": True}

    app.include_router(auth_router)

    return app
