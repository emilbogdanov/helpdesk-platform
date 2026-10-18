from datetime import timedelta
from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from helpdesk.domain.ids import CommentId
from helpdesk.domain.roles import Role
from helpdesk.domain.tickets.comment import Comment, CommentBody, Visibility
from helpdesk.domain.tickets.events import TicketEvent
from helpdesk.domain.tickets.status import TicketStatus
from helpdesk.infrastructure.db.audit_log import EVENT_TYPES
from helpdesk.infrastructure.db.tables import AuditEntryRow
from helpdesk.infrastructure.db.unit_of_work import SqlUnitOfWork
from tests.unit.domain.tickets.builders import LATER, MILA, REQUESTER, TICKET_ID, ticket_in

pytestmark = pytest.mark.integration


def comment(number: int, visibility: Visibility) -> Comment:
    return Comment(
        id=CommentId(UUID(int=number)),
        ticket_id=TICKET_ID,
        author_id=MILA,
        body=CommentBody(f"Note {number}"),
        visibility=visibility,
        # Inserted out of order on purpose: the thread must come back sorted by time.
        created_at=LATER + timedelta(minutes=10 - number),
    )


@pytest.fixture
async def thread(uow: SqlUnitOfWork) -> None:
    async with uow:
        await uow.tickets.add(ticket_in(TicketStatus.IN_PROGRESS), idempotency_key=None)
        for number, visibility in [
            (1, Visibility.PUBLIC),
            (2, Visibility.INTERNAL),
            (3, Visibility.PUBLIC),
        ]:
            await uow.comments.add(comment(number, visibility))
        await uow.commit()


@pytest.mark.usefixtures("thread")
async def test_staff_thread_is_oldest_first_with_internal_notes(uow: SqlUnitOfWork) -> None:
    async with uow:
        comments = await uow.comments.list_for_ticket(TICKET_ID, include_internal=True)

    assert [str(c.body) for c in comments] == ["Note 3", "Note 2", "Note 1"]
    assert comments[1] == comment(2, Visibility.INTERNAL)


@pytest.mark.usefixtures("thread")
async def test_customer_thread_leaves_out_internal_notes(uow: SqlUnitOfWork) -> None:
    async with uow:
        comments = await uow.comments.list_for_ticket(TICKET_ID, include_internal=False)

    assert [str(c.body) for c in comments] == ["Note 3", "Note 1"]


def test_every_event_has_a_stored_name() -> None:
    assert set(EVENT_TYPES) == set(TicketEvent.__subclasses__())


async def test_audit_entries_keep_actor_type_and_payload(
    uow: SqlUnitOfWork, engine: AsyncEngine
) -> None:
    async with uow:
        await uow.tickets.add(ticket_in(TicketStatus.WAITING_ON_CUSTOMER), idempotency_key=None)
        await uow.commit()

    async with uow:
        ticket = await uow.tickets.get(TICKET_ID)
        assert ticket is not None
        added = ticket.add_comment(
            comment_id=CommentId(UUID(int=7)),
            author_id=REQUESTER,
            author_role=Role.CUSTOMER,
            body=CommentBody("Still broken after the update."),
            visibility=Visibility.PUBLIC,
            at=LATER,
        )
        await uow.comments.add(added)
        await uow.tickets.update(ticket)
        await uow.audit.record(REQUESTER, ticket.pull_events())
        await uow.commit()

    async with engine.connect() as connection:
        rows = (await connection.execute(select(AuditEntryRow).order_by(AuditEntryRow.id))).all()

    assert [(row.event_type, row.actor_id, row.occurred_at) for row in rows] == [
        ("comment_added", REQUESTER, LATER),
        ("status_changed", REQUESTER, LATER),
    ]
    assert rows[0].payload == {
        "comment_id": str(UUID(int=7)),
        "author_id": str(REQUESTER),
        "visibility": "public",
    }
    assert rows[1].payload == {"previous": "waiting_on_customer", "current": "in_progress"}
