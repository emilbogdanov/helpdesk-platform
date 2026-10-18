from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import override
from uuid import UUID

import pytest

from helpdesk.application.errors import ConcurrentUpdateError
from helpdesk.application.ports import UnitOfWork
from helpdesk.application.tickets.upkeep import TicketUpkeep
from helpdesk.domain.ids import TicketId
from helpdesk.domain.tickets.events import FirstResponseOverdue, TicketStatusChanged
from helpdesk.domain.tickets.sla import DEFAULT_FIRST_RESPONSE_TARGETS
from helpdesk.domain.tickets.status import TicketStatus
from helpdesk.domain.tickets.ticket import Ticket
from helpdesk.domain.tickets.values import Description, Priority, Subject
from tests.unit.application.fakes import FakeUnitOfWork, FixedClock, InMemoryTicketRepository
from tests.unit.domain.tickets.builders import MILA, OPENED_AT, REQUESTER

NOW = OPENED_AT + timedelta(days=10)


def ticket(
    number: int,
    *,
    opened: timedelta,
    priority: Priority = Priority.NORMAL,
    status: TicketStatus = TicketStatus.OPEN,
    first_responded: timedelta | None = None,
    breached: timedelta | None = None,
    resolved: timedelta | None = None,
) -> Ticket:
    def ago(delta: timedelta | None) -> datetime | None:
        return NOW - delta if delta is not None else None

    return Ticket(
        ticket_id=TicketId(UUID(int=number)),
        requester_id=REQUESTER,
        subject=Subject(f"Ticket {number}"),
        description=Description("Details in the first comment."),
        priority=priority,
        status=status,
        assignee_id=MILA if status.requires_assignee or resolved else None,
        created_at=NOW - opened,
        updated_at=NOW - opened,
        resolved_at=ago(resolved),
        closed_at=None,
        first_responded_at=ago(first_responded),
        sla_breached_at=ago(breached),
    )


# Each ticket is here for one reason, given on its line.
WORKLOAD = [
    ticket(1, opened=timedelta(hours=2), priority=Priority.URGENT),  # overdue
    ticket(2, opened=timedelta(hours=2)),  # normal: not due for a day
    ticket(3, opened=timedelta(days=2), status=TicketStatus.WAITING_ON_CUSTOMER),  # overdue
    ticket(4, opened=timedelta(days=2), first_responded=timedelta(days=1)),  # answered
    ticket(5, opened=timedelta(days=3), breached=timedelta(days=2)),  # already flagged
    ticket(6, opened=timedelta(days=9), status=TicketStatus.RESOLVED, resolved=timedelta(days=8)),
    ticket(7, opened=timedelta(days=9), status=TicketStatus.RESOLVED, resolved=timedelta(days=6)),
    ticket(8, opened=timedelta(days=5), priority=Priority.LOW),  # overdue: low waits 3 days
]


async def seed(uow: UnitOfWork) -> None:
    async with uow:
        for each in WORKLOAD:
            await uow.tickets.add(each, idempotency_key=None)
        await uow.commit()


def upkeep(uow: UnitOfWork, *, batch_size: int = 200) -> TicketUpkeep:
    return TicketUpkeep(
        uow,
        FixedClock(NOW),
        targets=DEFAULT_FIRST_RESPONSE_TARGETS,
        close_resolved_after=timedelta(days=7),
        batch_size=batch_size,
    )


async def load(uow: UnitOfWork, number: int) -> Ticket:
    async with uow:
        found = await uow.tickets.get(TicketId(UUID(int=number)))
    assert found is not None
    return found


@pytest.fixture
async def uow() -> UnitOfWork:
    fake = FakeUnitOfWork()
    await seed(fake)
    return fake


class TestOverdueFirstResponses:
    async def test_flags_exactly_the_overdue_unanswered_tickets(self, uow: UnitOfWork) -> None:
        flagged = await upkeep(uow).flag_overdue_first_responses()

        assert flagged == 3
        flagged_now = {n for n in range(1, 9) if (await load(uow, n)).sla_breached_at == NOW}
        assert flagged_now == {1, 3, 8}

    async def test_a_second_pass_finds_nothing_new(self, uow: UnitOfWork) -> None:
        await upkeep(uow).flag_overdue_first_responses()

        assert await upkeep(uow).flag_overdue_first_responses() == 0

    async def test_large_backlogs_are_worked_off_over_several_passes(self, uow: UnitOfWork) -> None:
        passes = [await upkeep(uow, batch_size=2).flag_overdue_first_responses() for _ in range(3)]

        assert passes == [2, 1, 0]


class TestAutoClose:
    async def test_closes_tickets_resolved_longer_than_the_grace_period(
        self, uow: UnitOfWork
    ) -> None:
        closed = await upkeep(uow).close_resolved_tickets()

        assert closed == 1
        assert (await load(uow, 6)).status is TicketStatus.CLOSED
        assert (await load(uow, 7)).status is TicketStatus.RESOLVED


class TestAudit:
    async def test_system_changes_are_audited_without_an_actor(self) -> None:
        fake = FakeUnitOfWork()
        await seed(fake)

        await upkeep(fake).flag_overdue_first_responses()
        await upkeep(fake).close_resolved_tickets()

        assert {actor for actor, _ in fake.audit.entries} == {None}
        assert sorted(type(event).__name__ for _, event in fake.audit.entries) == sorted(
            [FirstResponseOverdue.__name__] * 3 + [TicketStatusChanged.__name__]
        )

    async def test_a_ticket_changed_meanwhile_is_skipped_and_retried(self) -> None:
        fake = LosesOneRace()
        await seed(fake)

        first_pass = await upkeep(fake).flag_overdue_first_responses()
        second_pass = await upkeep(fake).flag_overdue_first_responses()

        assert (first_pass, second_pass) == (2, 1)


class LosesOneRace(FakeUnitOfWork):
    """The first commit after seeding fails as if an agent saved the same ticket first."""

    def __init__(self) -> None:
        super().__init__()
        self.races_to_lose = 1

    @override
    async def commit(self) -> None:
        if self.commits and self.races_to_lose:
            self.races_to_lose -= 1
            raise ConcurrentUpdateError
        await super().commit()


class StaleSweep(InMemoryTicketRepository):
    """A sweep query that ran just before someone replied, and before a ticket vanished."""

    @override
    async def find_awaiting_first_response(
        self, opened_before: Mapping[Priority, datetime], *, limit: int
    ) -> list[TicketId]:
        return [TicketId(UUID(int=4)), TicketId(UUID(int=404))]


async def test_candidates_that_no_longer_qualify_are_left_alone() -> None:
    fake = FakeUnitOfWork()
    fake.tickets = StaleSweep()
    await seed(fake)

    flagged = await upkeep(fake).flag_overdue_first_responses()

    assert flagged == 0
    assert (await load(fake, 4)).sla_breached_at is None
    assert fake.audit.entries == []
