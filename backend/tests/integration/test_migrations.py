import asyncio

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Connection, inspect
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from helpdesk.infrastructure.db.tables import Base

pytestmark = pytest.mark.integration


def _schema_drift(connection: Connection) -> list[object]:
    return list(compare_metadata(MigrationContext.configure(connection), Base.metadata))


def _table_names(connection: Connection) -> set[str]:
    return set(inspect(connection).get_table_names())


async def _tables_in(database_url: str) -> set[str]:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            return await connection.run_sync(_table_names)
    finally:
        await engine.dispose()


async def test_migrations_produce_the_schema_the_models_expect(engine: AsyncEngine) -> None:
    async with engine.connect() as connection:
        drift = await connection.run_sync(_schema_drift)

    assert drift == []


# Sync on purpose: Alembic's env.py starts its own event loop.
def test_downgrade_removes_everything_and_upgrade_restores_it(
    alembic_config: Config, database_url: str
) -> None:
    command.downgrade(alembic_config, "base")
    assert asyncio.run(_tables_in(database_url)) == {"alembic_version"}

    command.upgrade(alembic_config, "head")
    assert asyncio.run(_tables_in(database_url)) == {
        "alembic_version",
        "users",
        "tickets",
        "comments",
        "audit_entries",
    }
