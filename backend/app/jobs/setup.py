import asyncio
import re
from sqlalchemy import text
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.store.postgres.aio import AsyncPostgresStore
from app.config import get_settings
from app.db import create_engine
from app.materials.storage import MaterialStorage

async def initialize_agent_state(settings):
    from app.outline.service import checkpoint_url
    if not re.fullmatch(r'[a-z][a-z0-9_]{0,62}',settings.agent_schema): raise ValueError('持久化模式名称无效')
    engine=create_engine(settings.database_url)
    try:
        async with engine.begin() as connection:
            await connection.execute(text('CREATE SCHEMA IF NOT EXISTS '+settings.agent_schema))
        async with AsyncPostgresSaver.from_conn_string(checkpoint_url(settings)) as saver: await saver.setup()
        async with AsyncPostgresStore.from_conn_string(checkpoint_url(settings)) as store: await store.setup()
    finally: await engine.dispose()

async def main():
    settings=get_settings()
    await initialize_agent_state(settings)
    if settings.minio_endpoint: await asyncio.to_thread(MaterialStorage(settings).ensure_bucket)

if __name__=='__main__': asyncio.run(main())
