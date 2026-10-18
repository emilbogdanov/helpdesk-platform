from collections.abc import Mapping
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Select, and_, literal, or_, select, text, tuple_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from helpdesk.application.errors import EmailTakenError, IdempotencyKeyConflictError
from helpdesk.application.tickets.queries import UNASSIGNED, TicketQuery
from helpdesk.domain.ids import CommentId, TicketId, UserId
from helpdesk.domain.tickets.comment import Comment, CommentBody, Visibility
from helpdesk.domain.tickets.status import TicketStatus
from helpdesk.domain.tickets.ticket import Ticket
from helpdesk.domain.tickets.values import Description, Priority, Subject
from helpdesk.domain.users.user import User
from helpdesk.domain.users.values import DisplayName, EmailAddress
from helpdesk.infrastructure.db.tables import (
    AWAITING_FIRST_RESPONSE,
    CommentRow,
    TicketRow,
    UserRow,
)


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

    async def find(self, query: TicketQuery) -> list[Ticket]:
        rows = await self._session.scalars(ticket_search(query))
        return [_ticket_from_row(row) for row in rows]

    async def find_awaiting_first_response(
        self, opened_before: Mapping[Priority, datetime], *, limit: int
    ) -> list[TicketId]:
        ids = await self._session.scalars(awaiting_first_response(opened_before, limit=limit))
        return [TicketId(ticket_id) for ticket_id in ids]

    async def find_resolved_before(self, cutoff: datetime, *, limit: int) -> list[TicketId]:
        ids = await self._session.scalars(resolved_before(cutoff, limit=limit))
        return [TicketId(ticket_id) for ticket_id in ids]

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


class SqlUserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        # Same reason as SqlTicketRepository: update() must write the version that was read.
        self._loaded: dict[UserId, UserRow] = {}

    async def get(self, user_id: UserId) -> User | None:
        return self._track(await self._session.get(UserRow, user_id))

    async def get_by_email(self, email: EmailAddress) -> User | None:
        return self._track(
            await self._session.scalar(select(UserRow).where(UserRow.email == str(email)))
        )

    async def add(self, user: User) -> None:
        inserted = await self._session.scalar(
            insert(UserRow)
            .values(**_user_columns(user), version=1)
            .on_conflict_do_nothing(constraint="uq_users_email")
            .returning(UserRow.id)
        )
        if inserted is None:
            raise EmailTakenError(user.email)

    async def update(self, user: User) -> None:
        row = self._loaded.get(user.id)
        if row is None:
            raise LookupError(f"user {user.id} must be loaded in this unit of work to update")
        for column, value in _user_columns(user).items():
            setattr(row, column, value)

    def _track(self, row: UserRow | None) -> User | None:
        if row is None:
            return None
        self._loaded[UserId(row.id)] = row
        return _user_from_row(row)


def ticket_search(query: TicketQuery) -> Select[TicketRow]:
    sort_column = TicketRow.updated_at if query.sort.by_update else TicketRow.created_at
    statement = select(TicketRow)
    if query.statuses:
        statement = statement.where(TicketRow.status.in_(query.statuses))
    if query.priorities:
        statement = statement.where(TicketRow.priority.in_(query.priorities))
    if query.requester_id is not None:
        statement = statement.where(TicketRow.requester_id == query.requester_id)
    if query.assignee == UNASSIGNED:
        statement = statement.where(TicketRow.assignee_id.is_(None))
    elif query.assignee is not None:
        statement = statement.where(TicketRow.assignee_id == query.assignee)
    if query.after is not None:
        # Row-value comparison, so Postgres can seek straight to the cursor in an index on
        # (sort column, id) instead of reading everything before it.
        position = tuple_(sort_column, TicketRow.id)
        cursor = tuple_(literal(query.after.sort_value), literal(query.after.ticket_id))
        statement = statement.where(
            position < cursor if query.sort.descending else position > cursor
        )
    order = (sort_column, TicketRow.id)
    return statement.order_by(
        *(column.desc() if query.sort.descending else column for column in order)
    ).limit(query.limit)


def awaiting_first_response(
    opened_before: Mapping[Priority, datetime], *, limit: int
) -> Select[UUID]:
    overdue_for_its_priority = or_(
        *(
            and_(TicketRow.priority == priority, TicketRow.created_at <= cutoff)
            for priority, cutoff in opened_before.items()
        )
    )
    return (
        select(TicketRow.id)
        .where(text(AWAITING_FIRST_RESPONSE), overdue_for_its_priority)
        .order_by(TicketRow.created_at)
        .limit(limit)
    )


def resolved_before(cutoff: datetime, *, limit: int) -> Select[UUID]:
    return (
        select(TicketRow.id)
        .where(TicketRow.status == TicketStatus.RESOLVED, TicketRow.resolved_at <= cutoff)
        .order_by(TicketRow.resolved_at)
        .limit(limit)
    )


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
        "first_responded_at": ticket.first_responded_at,
        "sla_breached_at": ticket.sla_breached_at,
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
        first_responded_at=row.first_responded_at,
        sla_breached_at=row.sla_breached_at,
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


def _user_columns(user: User) -> dict[str, Any]:
    return {
        "id": user.id,
        "email": str(user.email),
        "display_name": str(user.display_name),
        "role": user.role,
        "password_hash": user.password_hash,
        "is_active": user.is_active,
        "created_at": user.created_at,
    }


def _user_from_row(row: UserRow) -> User:
    return User(
        user_id=UserId(row.id),
        email=EmailAddress(row.email),
        display_name=DisplayName(row.display_name),
        role=row.role,
        password_hash=row.password_hash,
        is_active=row.is_active,
        created_at=row.created_at,
    )
