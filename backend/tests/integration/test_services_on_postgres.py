import asyncio
from datetime import timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from helpdesk.application.actor import Actor
from helpdesk.application.tickets.comment_service import CommentService
from helpdesk.application.tickets.ticket_service import TicketService
from helpdesk.domain.ids import TicketId
from helpdesk.domain.roles import Role
from helpdesk.domain.tickets.comment import CommentBody, Visibility
from helpdesk.domain.tickets.status import TicketStatus
from helpdesk.domain.tickets.values import Description, Priority, Subject
from helpdesk.infrastructure.db.tables import AuditEntryRow, Base, TicketRow
from helpdesk.infrastructure.db.unit_of_work import SqlUnitOfWork
from tests.unit.application.fakes import FixedClock
from tests.unit.domain.tickets.builders import MILA, OPENED_AT, REQUESTER

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("people")]

CUSTOMER = Actor(REQUESTER, Role.CUSTOMER)
AGENT = Actor(MILA, Role.AGENT)
SUBJECT = Subject("Exported CSV drops rows with commas in the name")
DESCRIPTION = Description("Customer 'Ivanov, Petar' is missing from the March export.")


async def count(engine: AsyncEngine, table: type[Base]) -> int:
    async with engine.connect() as connection:
        return (await connection.execute(select(func.count()).select_from(table))).scalar_one()


async def test_ticket_conversation_end_to_end(
    session_factory: async_sessionmaker[AsyncSession], engine: AsyncEngine
) -> None:
    clock = FixedClock(OPENED_AT)
    uow = SqlUnitOfWork(session_factory)
    tickets = TicketService(uow, clock)
    comments = CommentService(uow, clock)

    ticket = await tickets.open_ticket(
        CUSTOMER, subject=SUBJECT, description=DESCRIPTION, priority=Priority.NORMAL
    )
    clock.advance(timedelta(minutes=12))
    await tickets.take(AGENT, ticket.id)
    await tickets.change_status(AGENT, ticket.id, TicketStatus.IN_PROGRESS)
    await comments.add_comment(
        AGENT,
        ticket.id,
        body=CommentBody("The exporter doesn't quote fields. Fix is in review."),
        visibility=Visibility.INTERNAL,
    )
    await comments.add_comment(
        AGENT,
        ticket.id,
        body=CommentBody("Could you send the export settings you used?"),
        visibility=Visibility.PUBLIC,
    )
    await tickets.change_status(AGENT, ticket.id, TicketStatus.WAITING_ON_CUSTOMER)
    clock.advance(timedelta(hours=3))
    await comments.add_comment(
        CUSTOMER,
        ticket.id,
        body=CommentBody("Default settings, UTF-8, all customers."),
        visibility=Visibility.PUBLIC,
    )

    current = await tickets.get_ticket(CUSTOMER, ticket.id)
    assert current.status is TicketStatus.IN_PROGRESS
    assert current.assignee_id == MILA
    assert current.updated_at == OPENED_AT + timedelta(hours=3, minutes=12)
    assert len(await comments.list_comments(CUSTOMER, ticket.id)) == 2
    assert len(await comments.list_comments(AGENT, ticket.id)) == 3
    # opened, assigned, in_progress, 2 comments, waiting, reply, back to in_progress
    assert await count(engine, AuditEntryRow) == 8


async def test_concurrent_creates_with_one_key_make_one_ticket(
    session_factory: async_sessionmaker[AsyncSession], engine: AsyncEngine
) -> None:
    clock = FixedClock(OPENED_AT)

    async def submit() -> TicketId:
        # One unit of work per request, as the API will do.
        service = TicketService(SqlUnitOfWork(session_factory), clock)
        ticket = await service.open_ticket(
            CUSTOMER,
            subject=SUBJECT,
            description=DESCRIPTION,
            priority=Priority.HIGH,
            idempotency_key="4f1d-double-click",
        )
        return ticket.id

    ids = await asyncio.gather(*(submit() for _ in range(5)))

    assert len(set(ids)) == 1
    assert await count(engine, TicketRow) == 1
    assert await count(engine, AuditEntryRow) == 1
