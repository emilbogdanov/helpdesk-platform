from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from helpdesk.application.errors import IdempotencyKeyConflictError
from helpdesk.domain.ids import CommentId, TicketId, UserId
from helpdesk.domain.tickets.comment import Comment, CommentBody, Visibility
from helpdesk.domain.tickets.ticket import Ticket
from helpdesk.domain.tickets.values import Description, Subject
from helpdesk.infrastructure.db.tables import CommentRow, TicketRow


class SqlTicketRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        # The session's identity map holds rows weakly. Keeping the rows we handed out alive
        # means update() writes against the version that was read, not a fresh re-select
        # that would let a concurrent change be silently overwritten.
        self._loaded: dict[TicketId, TicketRow] = {}

    async def get(self, ticket_id: TicketId) -> Ticket | None:
        return self._track(await self._session.get(TicketRow, ticket_id))

    async def find_by_idempotency_key(self, requester_id: UserId, key: str) -> Ticket | None:
        return self._track(
            await self._session.scalar(
                select(TicketRow).where(
                    TicketRow.requester_id == requester_id,
                    TicketRow.idempotency_key == key,
                )
            )
        )

    async def add(self, ticket: Ticket, *, idempotency_key: str | None) -> None:
        statement = insert(TicketRow).values(
            **_ticket_columns(ticket), idempotency_key=idempotency_key, version=1
        )
        if idempotency_key is None:
            await self._session.execute(statement)
            return
        # ON CONFLICT instead of catching IntegrityError: a duplicate key leaves the
        # transaction usable, so the caller can still look up the ticket that won.
        inserted = await self._session.scalar(
            statement.on_conflict_do_nothing(
                constraint="uq_tickets_requester_id_idempotency_key"
            ).returning(TicketRow.id)
        )
        if inserted is None:
            raise IdempotencyKeyConflictError(idempotency_key)

    async def update(self, ticket: Ticket) -> None:
        row = self._loaded.get(ticket.id)
        if row is None:
            raise LookupError(f"ticket {ticket.id} must be loaded in this unit of work to update")
        for column, value in _ticket_columns(ticket).items():
            setattr(row, column, value)

    def _track(self, row: TicketRow | None) -> Ticket | None:
        if row is None:
            return None
        self._loaded[TicketId(row.id)] = row
        return _ticket_from_row(row)


class SqlCommentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, comment: Comment) -> None:
        self._session.add(
            CommentRow(
                id=comment.id,
                ticket_id=comment.ticket_id,
                author_id=comment.author_id,
                body=str(comment.body),
                visibility=comment.visibility,
                created_at=comment.created_at,
            )
        )

    async def list_for_ticket(
        self, ticket_id: TicketId, *, include_internal: bool
    ) -> list[Comment]:
        statement = (
            select(CommentRow)
            .where(CommentRow.ticket_id == ticket_id)
            .order_by(CommentRow.created_at, CommentRow.id)
        )
        if not include_internal:
            statement = statement.where(CommentRow.visibility == Visibility.PUBLIC)
        rows = await self._session.scalars(statement)
        return [_comment_from_row(row) for row in rows]


def _ticket_columns(ticket: Ticket) -> dict[str, Any]:
    return {
        "id": ticket.id,
        "requester_id": ticket.requester_id,
        "subject": str(ticket.subject),
        "description": str(ticket.description),
        "priority": ticket.priority,
        "status": ticket.status,
        "assignee_id": ticket.assignee_id,
        "created_at": ticket.created_at,
        "updated_at": ticket.updated_at,
        "resolved_at": ticket.resolved_at,
        "closed_at": ticket.closed_at,
    }


def _ticket_from_row(row: TicketRow) -> Ticket:
    return Ticket(
        ticket_id=TicketId(row.id),
        requester_id=UserId(row.requester_id),
        subject=Subject(row.subject),
        description=Description(row.description),
        priority=row.priority,
        status=row.status,
        assignee_id=UserId(row.assignee_id) if row.assignee_id is not None else None,
        created_at=row.created_at,
        updated_at=row.updated_at,
        resolved_at=row.resolved_at,
        closed_at=row.closed_at,
    )


def _comment_from_row(row: CommentRow) -> Comment:
    return Comment(
        id=CommentId(row.id),
        ticket_id=TicketId(row.ticket_id),
        author_id=UserId(row.author_id),
        body=CommentBody(row.body),
        visibility=row.visibility,
        created_at=row.created_at,
    )
