from datetime import UTC, date, datetime, timedelta
from uuid import UUID

import pytest

from helpdesk.application.actor import Actor
from helpdesk.application.errors import AdminOnlyError
from helpdesk.application.ports import UnitOfWork
from helpdesk.application.tickets.statistics import TicketStatistics
from helpdesk.domain.errors import InvalidValueError
from helpdesk.domain.ids import TicketId
from helpdesk.domain.roles import Role
from helpdesk.domain.tickets.status import TicketStatus
from helpdesk.domain.tickets.ticket import Ticket
from helpdesk.domain.tickets.values import Description, Priority, Subject
from tests.unit.application.fakes import FakeUnitOfWork, FixedClock
from tests.unit.domain.tickets.builders import MILA, REQUESTER, STEFAN

NOW = datetime(2026, 10, 18, 14, 0, tzinfo=UTC)
ADMIN = Actor(STEFAN, Role.ADMIN)


def ticket(
    number: int,
    *,
    opened: datetime,
    status: TicketStatus = TicketStatus.OPEN,
    assigned: bool = False,
    replied_after: timedelta | None = None,
    resolved: datetime | None = None,
    breached: bool = False,
) -> Ticket:
    return Ticket(
        ticket_id=TicketId(UUID(int=number)),
        requester_id=REQUESTER,
        subject=Subject(f"Ticket {number}"),
        description=Description("Details in the first comment."),
        priority=Priority.NORMAL,
        status=status,
        assignee_id=MILA if assigned else None,
        created_at=opened,
        updated_at=opened,
        resolved_at=resolved,
        closed_at=resolved if status is TicketStatus.CLOSED else None,
        first_responded_at=opened + replied_after if replied_after else None,
        sla_breached_at=opened + timedelta(days=1) if breached else None,
    )


# Each ticket is here for one reason, given on its line.
WORKLOAD = [
    ticket(1, opened=NOW - timedelta(hours=2)),  # new: unassigned, waiting for a reply
    ticket(
        2,
        opened=NOW - timedelta(days=1),
        status=TicketStatus.IN_PROGRESS,
        assigned=True,
        replied_after=timedelta(minutes=30),
    ),
    ticket(
        3,
        opened=NOW - timedelta(days=3),
        status=TicketStatus.WAITING_ON_CUSTOMER,
        assigned=True,
        replied_after=timedelta(hours=2),
    ),
    ticket(4, opened=NOW - timedelta(days=2), breached=True),  # flagged by the worker
    ticket(
        5,
        opened=NOW - timedelta(days=5),
        status=TicketStatus.RESOLVED,
        assigned=True,
        replied_after=timedelta(hours=1),
        resolved=NOW - timedelta(days=1),
    ),
    ticket(  # old: counted by status, but outside the window for the median and the chart
        6,
        opened=NOW - timedelta(days=30),
        status=TicketStatus.CLOSED,
        assigned=True,
        replied_after=timedelta(hours=10),
        resolved=NOW - timedelta(days=20),
    ),
    ticket(7, opened=NOW - timedelta(days=4), status=TicketStatus.CLOSED),  # spam, closed unread
    # 01:30 in Sofia on 5 October is still 4 October in UTC, the day before the window.
    ticket(8, opened=datetime(2026, 10, 4, 22, 30, tzinfo=UTC), status=TicketStatus.CLOSED),
]


async def seed(uow: UnitOfWork) -> None:
    async with uow:
        for each in WORKLOAD:
            await uow.tickets.add(each, idempotency_key=None)
        await uow.commit()


@pytest.fixture
async def uow() -> UnitOfWork:
    fake = FakeUnitOfWork()
    await seed(fake)
    return fake


class TestOverview:
    async def test_counts_the_queue_as_it_stands(self, uow: UnitOfWork) -> None:
        totals = (await TicketStatistics(uow, FixedClock(NOW)).overview(ADMIN, days=14)).totals

        assert dict(totals.by_status) == {
            TicketStatus.OPEN: 2,
            TicketStatus.IN_PROGRESS: 1,
            TicketStatus.WAITING_ON_CUSTOMER: 1,
            TicketStatus.RESOLVED: 1,
            TicketStatus.CLOSED: 3,
        }
        assert totals.unassigned == 2
        assert totals.awaiting_first_response == 2
        assert totals.first_response_overdue == 1

    async def test_median_first_response_covers_tickets_opened_in_the_window(
        self, uow: UnitOfWork
    ) -> None:
        totals = (await TicketStatistics(uow, FixedClock(NOW)).overview(ADMIN, days=14)).totals

        # 30 minutes, 1 hour and 2 hours; the 10-hour reply is from before the window.
        assert totals.median_first_response == timedelta(hours=1)

    async def test_charts_every_day_in_the_window_including_quiet_ones(
        self, uow: UnitOfWork
    ) -> None:
        days = (await TicketStatistics(uow, FixedClock(NOW)).overview(ADMIN, days=14)).days

        assert len(days) == 14
        assert days[0].day == date(2026, 10, 5)
        assert days[-1].day == date(2026, 10, 18)
        assert {day.day.day: day.opened for day in days if day.opened} == {
            13: 1,
            14: 1,
            15: 1,
            16: 1,
            17: 1,
            18: 1,
        }
        assert {day.day.day: day.resolved for day in days if day.resolved} == {17: 1}

    async def test_is_for_admins_only(self, uow: UnitOfWork) -> None:
        with pytest.raises(AdminOnlyError):
            await TicketStatistics(uow, FixedClock(NOW)).overview(Actor(MILA, Role.AGENT), days=14)

    @pytest.mark.parametrize("days", [0, 91])
    async def test_the_window_is_bounded(self, uow: UnitOfWork, days: int) -> None:
        with pytest.raises(InvalidValueError):
            await TicketStatistics(uow, FixedClock(NOW)).overview(ADMIN, days=days)
