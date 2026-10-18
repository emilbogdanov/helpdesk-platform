import asyncio
from datetime import UTC, datetime

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Connection, inspect, text
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


def test_first_responses_are_backfilled_from_existing_replies(
    alembic_config: Config, database_url: str
) -> None:
    command.downgrade(alembic_config, "9e41b7d2c6a0")
    asyncio.run(_seed_conversation(database_url))

    command.upgrade(alembic_config, "head")

    assert asyncio.run(_first_responses(database_url)) == {
        "answered": datetime(2026, 10, 12, 9, 40, tzinfo=UTC),
        "only-internal-note": None,
    }
    asyncio.run(_empty_tables(database_url))


async def _seed_conversation(database_url: str) -> None:
    await _execute(
        database_url,
        """
        INSERT INTO users
            (id, email, display_name, role, password_hash, is_active, created_at, version)
        VALUES
            ('00000000-0000-0000-0000-00000000000a', 'mila@helpdesk.test', 'Mila', 'agent',
             'x', true, '2026-10-01T00:00Z', 1),
            ('00000000-0000-0000-0000-00000000000c', 'petar@northwind.bg', 'Petar', 'customer',
             'x', true, '2026-10-01T00:00Z', 1)
        """,
        """
        INSERT INTO tickets (id, requester_id, subject, description, priority, status,
                             created_at, updated_at, version)
        VALUES
            ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-00000000000c',
             'answered', 'd', 'normal', 'open', '2026-10-12T09:00Z', '2026-10-12T09:00Z', 1),
            ('00000000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-00000000000c',
             'only-internal-note', 'd', 'normal', 'open', '2026-10-12T09:00Z',
             '2026-10-12T09:00Z', 1)
        """,
        """
        INSERT INTO comments (id, ticket_id, author_id, body, visibility, created_at)
        VALUES
            -- The requester's own comment and a later staff reply: only the reply counts.
            ('00000000-0000-0000-0000-000000000101', '00000000-0000-0000-0000-000000000001',
             '00000000-0000-0000-0000-00000000000c', 'hello?', 'public', '2026-10-12T09:10Z'),
            ('00000000-0000-0000-0000-000000000102', '00000000-0000-0000-0000-000000000001',
             '00000000-0000-0000-0000-00000000000a', 'on it', 'public', '2026-10-12T09:40Z'),
            ('00000000-0000-0000-0000-000000000103', '00000000-0000-0000-0000-000000000001',
             '00000000-0000-0000-0000-00000000000a', 'again', 'public', '2026-10-12T10:00Z'),
            ('00000000-0000-0000-0000-000000000104', '00000000-0000-0000-0000-000000000002',
             '00000000-0000-0000-0000-00000000000a', 'note', 'internal', '2026-10-12T09:20Z')
        """,
    )


async def _first_responses(database_url: str) -> dict[str, datetime | None]:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            rows = await connection.execute(text("SELECT subject, first_responded_at FROM tickets"))
            return {row.subject: row.first_responded_at for row in rows}
    finally:
        await engine.dispose()


async def _empty_tables(database_url: str) -> None:
    await _execute(database_url, "TRUNCATE users, tickets, comments, audit_entries")


async def _execute(database_url: str, *statements: str) -> None:
    engine = create_async_engine(database_url)
    try:
        async with engine.begin() as connection:
            for statement in statements:
                await connection.execute(text(statement))
    finally:
        await engine.dispose()
