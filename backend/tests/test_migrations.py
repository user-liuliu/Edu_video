import asyncio
import os
import subprocess
import sys
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


async def test_migrations_upgrade_and_check_in_isolated_schema(settings):
    schema = 'migration_test_' + uuid.uuid4().hex
    engine = create_async_engine(settings.test_database_url)
    async with engine.begin() as connection:
        await connection.execute(text(f'CREATE SCHEMA {schema}'))
    env = {**os.environ, 'DATABASE_URL': settings.test_database_url, 'ALEMBIC_TEST_SCHEMA': schema, 'PYTHONIOENCODING':'utf-8'}
    try:
        for command in ('upgrade', 'check'):
            args = [sys.executable, '-m', 'alembic', command] + (['head'] if command == 'upgrade' else [])
            result = await asyncio.to_thread(subprocess.run, args, env=env, capture_output=True, text=True, encoding='utf-8', timeout=60)
            assert result.returncode == 0, result.stdout + result.stderr
    finally:
        async with engine.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA {schema} CASCADE'))
        await engine.dispose()
