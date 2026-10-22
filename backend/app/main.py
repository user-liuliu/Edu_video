from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.exceptions import RequestValidationError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.sessions import SessionMiddleware

from app.admin import settings_router as admin_settings_router
from app.admin import users_router as admin_users_router
from app.account.router import router as account_router
from app.auth import router as auth_router
from app.credits.router import router as credits_router
from app.config import Settings, get_settings
from app.db import create_engine, create_sessionmaker, get_session
from app.errors import validation_error_handler
from app.http_client import create_http
from app.model_configs import router as model_configs_router
from app.public import router as public_router
from app.projects import router as projects_router
from app.materials.router import router as materials_router
from app.jobs.service import router as jobs_router
from app.outline.router import router as outline_router
from app.preferences.router import router as preferences_router
from app.videos.router import router as videos_router
from app.redis_client import create_redis
from app.security import SecretBox


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield
    await app.state.http.aclose()
    await app.state.redis.aclose()
    await app.state.engine.dispose()


def create_app(settings: Settings | None = None) -> FastAPI:
    """应用工厂。启动：uvicorn app.main:create_app --factory"""
    settings = settings or get_settings()

    app = FastAPI(title="教学视频 agent", lifespan=lifespan)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.state.settings = settings
    app.state.engine = create_engine(settings.database_url)
    app.state.sessionmaker = create_sessionmaker(app.state.engine)
    app.state.redis = create_redis(settings.redis_url)
    app.state.secret_box = SecretBox(settings.master_key)
    app.state.http = create_http()

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
    app.include_router(account_router)
    app.include_router(credits_router)
    app.include_router(admin_users_router)
    app.include_router(admin_settings_router)
    app.include_router(model_configs_router)
    app.include_router(public_router)
    app.include_router(projects_router)
    app.include_router(materials_router)
    app.include_router(jobs_router)
    app.include_router(outline_router)
    app.include_router(preferences_router)
    app.include_router(videos_router)

    return app
