import pytest

from helpdesk.application.tickets.ticket_service import TicketService
from helpdesk.infrastructure.db.unit_of_work import SqlUnitOfWork
from tests.unit.application import test_ticket_listing as against_the_fake
from tests.unit.application.fakes import FixedClock
from tests.unit.application.ticket_catalogue import catalogue
from tests.unit.domain.tickets.builders import OPENED_AT

pytestmark = pytest.mark.integration

# The listing scenarios from the unit tests, run again against Postgres. If the SQL and the
# in-memory fake ever disagree on filtering, ordering or paging, one of these fails.
TestVisibility = against_the_fake.TestVisibility
TestFilters = against_the_fake.TestFilters
TestSorting = against_the_fake.TestSorting
TestPagination = against_the_fake.TestPagination


@pytest.fixture
async def service(uow: SqlUnitOfWork) -> TicketService:
    async with uow:
        for ticket in catalogue():
            await uow.tickets.add(ticket, idempotency_key=None)
        await uow.commit()
    return TicketService(uow, FixedClock(OPENED_AT))
