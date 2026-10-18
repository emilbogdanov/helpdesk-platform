import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from helpdesk.infrastructure.db.unit_of_work import SqlUnitOfWork
from tests.unit.application import test_ticket_statistics as against_the_fake

pytestmark = pytest.mark.integration

# The dashboard figures again, from the SQL aggregates: FILTER clauses, percentile_cont and
# the UTC day grouping must agree with the plain-Python counting in the fake.
TestOverview = against_the_fake.TestOverview


@pytest.fixture
async def uow(session_factory: async_sessionmaker[AsyncSession], people: None) -> SqlUnitOfWork:
    sql = SqlUnitOfWork(session_factory)
    await against_the_fake.seed(sql)
    return sql
