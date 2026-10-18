import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from helpdesk.infrastructure.db.unit_of_work import SqlUnitOfWork
from tests.unit.application import test_upkeep as against_the_fake

pytestmark = pytest.mark.integration

# The worker's scenarios again, against Postgres: the SQL prefilters must pick the same
# candidates the in-memory fake does, or one of these fails.
TestOverdueFirstResponses = against_the_fake.TestOverdueFirstResponses
TestAutoClose = against_the_fake.TestAutoClose


@pytest.fixture
async def uow(session_factory: async_sessionmaker[AsyncSession], people: None) -> SqlUnitOfWork:
    sql = SqlUnitOfWork(session_factory)
    await against_the_fake.seed(sql)
    return sql
