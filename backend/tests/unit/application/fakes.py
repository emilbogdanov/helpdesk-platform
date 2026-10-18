from collections.abc import Collection, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta
from types import TracebackType
from typing import Self
from uuid import UUID

from helpdesk.application.errors import (
    EmailTakenError,
    IdempotencyKeyConflictError,
    InvalidTokenError,
)
from helpdesk.application.ports import TokenClaims
from helpdesk.application.tickets.queries import UNASSIGNED, TicketQuery
from helpdesk.domain.ids import TicketId, UserId
from helpdesk.domain.tickets.comment import Comment, Visibility
from helpdesk.domain.tickets.events import TicketEvent
from helpdesk.domain.tickets.status import TicketStatus
from helpdesk.domain.tickets.ticket import Ticket
from helpdesk.domain.tickets.values import Priority
from helpdesk.domain.users.user import User
from helpdesk.domain.users.values import EmailAddress, Password


class FixedClock:
    def __init__(self, now: datetime) -> None:
        self.current = now

    def now(self) -> datetime:
        return self.current

    def advance(self, delta: timedelta) -> None:
        self.current += delta


# Repositories hand out copies, like a database would: a service that mutates a ticket and
# forgets to save it must fail the tests instead of passing by accident.
class InMemoryTicketRepository:
    def __init__(self) -> None:
        self.rows: dict[TicketId, Ticket] = {}
        self.idempotency_keys: dict[tuple[UserId, str], TicketId] = {}

    async def get(self, ticket_id: TicketId) -> Ticket | None:
        ticket = self.rows.get(ticket_id)
        return deepcopy(ticket) if ticket is not None else None

    async def find_by_idempotency_key(self, requester_id: UserId, key: str) -> Ticket | None:
        ticket_id = self.idempotency_keys.get((requester_id, key))
        return await self.get(ticket_id) if ticket_id is not None else None

    async def add(self, ticket: Ticket, *, idempotency_key: str | None) -> None:
        assert ticket.id not in self.rows, f"ticket {ticket.id} added twice"
        if idempotency_key is not None:
            if (ticket.requester_id, idempotency_key) in self.idempotency_keys:
                raise IdempotencyKeyConflictError(idempotency_key)
            self.idempotency_keys[ticket.requester_id, idempotency_key] = ticket.id
        self.rows[ticket.id] = _stored(ticket)

    async def update(self, ticket: Ticket) -> None:
        assert ticket.id in self.rows, f"ticket {ticket.id} updated before it was added"
        self.rows[ticket.id] = _stored(ticket)

    async def find(self, query: TicketQuery) -> list[Ticket]:
        matching = [ticket for ticket in self.rows.values() if _matches(ticket, query)]
        matching.sort(
            key=lambda ticket: (query.sort.key_of(ticket), ticket.id),
            reverse=query.sort.descending,
        )
        if query.after is not None:
            cursor = (query.after.sort_value, query.after.ticket_id)
            matching = [t for t in matching if _beyond(query, (query.sort.key_of(t), t.id), cursor)]
        return [deepcopy(ticket) for ticket in matching[: query.limit]]

    async def find_awaiting_first_response(
        self, opened_before: Mapping[Priority, datetime], *, limit: int
    ) -> list[TicketId]:
        waiting = sorted(
            (
                ticket
                for ticket in self.rows.values()
                if ticket.first_responded_at is None
                and ticket.sla_breached_at is None
                and ticket.status
                in {TicketStatus.OPEN, TicketStatus.IN_PROGRESS, TicketStatus.WAITING_ON_CUSTOMER}
                and ticket.created_at <= opened_before[ticket.priority]
            ),
            key=lambda ticket: ticket.created_at,
        )
        return [ticket.id for ticket in waiting[:limit]]

    async def find_resolved_before(self, cutoff: datetime, *, limit: int) -> list[TicketId]:
        resolved = sorted(
            (
                ticket
                for ticket in self.rows.values()
                if ticket.status is TicketStatus.RESOLVED
                and ticket.resolved_at is not None
                and ticket.resolved_at <= cutoff
            ),
            key=lambda ticket: ticket.resolved_at or cutoff,
        )
        return [ticket.id for ticket in resolved[:limit]]


class InMemoryCommentRepository:
    def __init__(self) -> None:
        self.rows: list[Comment] = []

    async def add(self, comment: Comment) -> None:
        self.rows.append(comment)

    async def list_for_ticket(
        self, ticket_id: TicketId, *, include_internal: bool
    ) -> list[Comment]:
        thread = [
            comment
            for comment in self.rows
            if comment.ticket_id == ticket_id
            and (include_internal or comment.visibility is Visibility.PUBLIC)
        ]
        return sorted(thread, key=lambda comment: comment.created_at)


class InMemoryUserRepository:
    def __init__(self) -> None:
        self.rows: dict[UserId, User] = {}

    async def get(self, user_id: UserId) -> User | None:
        user = self.rows.get(user_id)
        return deepcopy(user) if user is not None else None

    async def get_many(self, user_ids: Collection[UserId]) -> list[User]:
        return [deepcopy(self.rows[user_id]) for user_id in user_ids if user_id in self.rows]

    async def get_by_email(self, email: EmailAddress) -> User | None:
        for user in self.rows.values():
            if user.email == email:
                return deepcopy(user)
        return None

    async def add(self, user: User) -> None:
        assert user.id not in self.rows, f"user {user.id} added twice"
        if any(existing.email == user.email for existing in self.rows.values()):
            raise EmailTakenError(user.email)
        self.rows[user.id] = deepcopy(user)

    async def update(self, user: User) -> None:
        assert user.id in self.rows, f"user {user.id} updated before it was added"
        self.rows[user.id] = deepcopy(user)


class FakePasswordHasher:
    async def hash(self, password: Password) -> str:
        return f"hashed:{password.value}"

    async def verify(self, password_hash: str | None, candidate: str) -> bool:
        return password_hash == f"hashed:{candidate}"


class FakeTokenCodec:
    def encode(self, claims: TokenClaims) -> str:
        return f"{claims.user_id}|{claims.expires_at.isoformat()}"

    def decode(self, token: str) -> TokenClaims:
        user_id, _, expires_at = token.partition("|")
        try:
            return TokenClaims(
                user_id=UserId(UUID(user_id)), expires_at=datetime.fromisoformat(expires_at)
            )
        except ValueError as error:
            raise InvalidTokenError from error


class InMemoryAuditLog:
    def __init__(self) -> None:
        self.entries: list[tuple[UserId | None, TicketEvent]] = []

    async def record(self, actor_id: UserId | None, events: Sequence[TicketEvent]) -> None:
        self.entries.extend((actor_id, event) for event in events)


@dataclass(slots=True)
class _Snapshot:
    tickets: dict[TicketId, Ticket]
    idempotency_keys: dict[tuple[UserId, str], TicketId]
    comments: list[Comment]
    audit: list[tuple[UserId | None, TicketEvent]]
    users: dict[UserId, User]


class FakeUnitOfWork:
    def __init__(self) -> None:
        self.tickets = InMemoryTicketRepository()
        self.comments = InMemoryCommentRepository()
        self.audit = InMemoryAuditLog()
        self.users = InMemoryUserRepository()
        self.commits = 0
        self._committed_in_block = False
        self._snapshot: _Snapshot | None = None

    async def __aenter__(self) -> Self:
        self._committed_in_block = False
        self._snapshot = deepcopy(
            _Snapshot(
                tickets=self.tickets.rows,
                idempotency_keys=self.tickets.idempotency_keys,
                comments=self.comments.rows,
                audit=self.audit.entries,
                users=self.users.rows,
            )
        )
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._committed_in_block or self._snapshot is None:
            return
        self.tickets.rows = self._snapshot.tickets
        self.tickets.idempotency_keys = self._snapshot.idempotency_keys
        self.comments.rows = self._snapshot.comments
        self.audit.entries = self._snapshot.audit
        self.users.rows = self._snapshot.users

    async def commit(self) -> None:
        self.commits += 1
        self._committed_in_block = True


def _beyond(
    query: TicketQuery, position: tuple[datetime, UUID], cursor: tuple[datetime, UUID]
) -> bool:
    return position < cursor if query.sort.descending else position > cursor


def _matches(ticket: Ticket, query: TicketQuery) -> bool:
    if query.statuses and ticket.status not in query.statuses:
        return False
    if query.priorities and ticket.priority not in query.priorities:
        return False
    if query.requester_id is not None and ticket.requester_id != query.requester_id:
        return False
    if query.assignee == UNASSIGNED:
        return ticket.assignee_id is None
    return query.assignee is None or ticket.assignee_id == query.assignee


def _stored(ticket: Ticket) -> Ticket:
    # Events are not persisted with the row; the service hands them to the audit log.
    copy = deepcopy(ticket)
    copy.pull_events()
    return copy
