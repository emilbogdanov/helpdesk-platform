import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from helpdesk.application.errors import ConcurrentUpdateError, IdempotencyKeyConflictError
from helpdesk.domain.ids import TicketId
from helpdesk.domain.tickets.status import TicketStatus
from helpdesk.domain.tickets.ticket import Ticket
from helpdesk.domain.tickets.values import Priority
from helpdesk.infrastructure.db.unit_of_work import SqlUnitOfWork
from tests.unit.domain.tickets.builders import (
    LATER,
    OTHER_CUSTOMER,
    REQUESTER,
    STEFAN,
    TICKET_ID,
    open_ticket,
    ticket_in,
)

pytestmark = pytest.mark.integration


def state_of(ticket: Ticket) -> dict[str, object]:
    return {
        "id": ticket.id,
        "requester_id": ticket.requester_id,
        "subject": ticket.subject,
        "description": ticket.description,
        "priority": ticket.priority,
        "status": ticket.status,
        "assignee_id": ticket.assignee_id,
        "created_at": ticket.created_at,
        "updated_at": ticket.updated_at,
        "resolved_at": ticket.resolved_at,
        "closed_at": ticket.closed_at,
    }


async def save(uow: SqlUnitOfWork, ticket: Ticket, idempotency_key: str | None = None) -> None:
    async with uow:
        await uow.tickets.add(ticket, idempotency_key=idempotency_key)
        await uow.commit()


async def load(uow: SqlUnitOfWork, ticket_id: TicketId = TICKET_ID) -> Ticket:
    async with uow:
        ticket = await uow.tickets.get(ticket_id)
    assert ticket is not None
    return ticket


@pytest.mark.parametrize("status", list(TicketStatus))
async def test_round_trip_keeps_every_field(uow: SqlUnitOfWork, status: TicketStatus) -> None:
    ticket = ticket_in(status)

    await save(uow, ticket)

    assert state_of(await load(uow)) == state_of(ticket)


async def test_missing_ticket_is_none(uow: SqlUnitOfWork) -> None:
    async with uow:
        assert await uow.tickets.get(TICKET_ID) is None


async def test_update_persists_changes(uow: SqlUnitOfWork) -> None:
    await save(uow, ticket_in(TicketStatus.OPEN))

    async with uow:
        ticket = await uow.tickets.get(TICKET_ID)
        assert ticket is not None
        ticket.change_status(TicketStatus.IN_PROGRESS, at=LATER)
        ticket.change_priority(Priority.URGENT, at=LATER)
        await uow.tickets.update(ticket)
        await uow.commit()

    stored = await load(uow)
    assert stored.status is TicketStatus.IN_PROGRESS
    assert stored.priority is Priority.URGENT
    assert stored.updated_at == LATER


async def test_leaving_without_commit_rolls_back(uow: SqlUnitOfWork) -> None:
    async with uow:
        await uow.tickets.add(open_ticket(), idempotency_key=None)

    async with uow:
        assert await uow.tickets.get(TICKET_ID) is None


async def test_updating_a_ticket_that_was_never_added_fails(uow: SqlUnitOfWork) -> None:
    async with uow:
        with pytest.raises(LookupError):
            await uow.tickets.update(open_ticket())


class TestIdempotencyKey:
    async def test_finds_the_ticket_by_requester_and_key(self, uow: SqlUnitOfWork) -> None:
        await save(uow, open_ticket(), idempotency_key="b7c1e0d2-retry")

        async with uow:
            found = await uow.tickets.find_by_idempotency_key(REQUESTER, "b7c1e0d2-retry")
            other = await uow.tickets.find_by_idempotency_key(OTHER_CUSTOMER, "b7c1e0d2-retry")

        assert found is not None
        assert found.id == TICKET_ID
        assert other is None

    async def test_duplicate_key_raises_and_leaves_the_transaction_usable(
        self, uow: SqlUnitOfWork
    ) -> None:
        await save(uow, open_ticket(), idempotency_key="b7c1e0d2-retry")
        duplicate = Ticket.open(
            ticket_id=TicketId(STEFAN),
            requester_id=REQUESTER,
            subject=open_ticket().subject,
            description=open_ticket().description,
            priority=Priority.NORMAL,
            at=LATER,
        )

        async with uow:
            with pytest.raises(IdempotencyKeyConflictError):
                await uow.tickets.add(duplicate, idempotency_key="b7c1e0d2-retry")
            found = await uow.tickets.find_by_idempotency_key(REQUESTER, "b7c1e0d2-retry")

        assert found is not None
        assert found.id == TICKET_ID


async def test_concurrent_update_is_detected(
    uow: SqlUnitOfWork, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await save(uow, ticket_in(TicketStatus.OPEN))
    other_agent = SqlUnitOfWork(session_factory)

    async with uow, other_agent:
        mine = await uow.tickets.get(TICKET_ID)
        theirs = await other_agent.tickets.get(TICKET_ID)
        assert mine is not None
        assert theirs is not None

        theirs.assign(STEFAN, at=LATER)
        await other_agent.tickets.update(theirs)
        await other_agent.commit()

        mine.change_status(TicketStatus.IN_PROGRESS, at=LATER)
        await uow.tickets.update(mine)
        with pytest.raises(ConcurrentUpdateError):
            await uow.commit()

    stored = await load(uow)
    assert stored.assignee_id == STEFAN
    assert stored.status is TicketStatus.OPEN


class TestUnitOfWorkMisuse:
    def test_repositories_are_unavailable_outside_a_block(self, uow: SqlUnitOfWork) -> None:
        with pytest.raises(RuntimeError, match="outside 'async with'"):
            _ = uow.tickets

    async def test_blocks_cannot_be_nested(self, uow: SqlUnitOfWork) -> None:
        async with uow:
            with pytest.raises(RuntimeError, match="already in use"):
                await uow.__aenter__()
