from collections.abc import Sequence
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta
from types import TracebackType
from typing import Self

from helpdesk.domain.ids import TicketId, UserId
from helpdesk.domain.tickets.comment import Comment, Visibility
from helpdesk.domain.tickets.events import TicketEvent
from helpdesk.domain.tickets.ticket import Ticket


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
        self.rows[ticket.id] = _stored(ticket)
        if idempotency_key is not None:
            self.idempotency_keys[ticket.requester_id, idempotency_key] = ticket.id

    async def update(self, ticket: Ticket) -> None:
        assert ticket.id in self.rows, f"ticket {ticket.id} updated before it was added"
        self.rows[ticket.id] = _stored(ticket)


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


class InMemoryAuditLog:
    def __init__(self) -> None:
        self.entries: list[tuple[UserId, TicketEvent]] = []

    async def record(self, actor_id: UserId, events: Sequence[TicketEvent]) -> None:
        self.entries.extend((actor_id, event) for event in events)


@dataclass(slots=True)
class _Snapshot:
    tickets: dict[TicketId, Ticket]
    idempotency_keys: dict[tuple[UserId, str], TicketId]
    comments: list[Comment]
    audit: list[tuple[UserId, TicketEvent]]


class FakeUnitOfWork:
    def __init__(self) -> None:
        self.tickets = InMemoryTicketRepository()
        self.comments = InMemoryCommentRepository()
        self.audit = InMemoryAuditLog()
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

    async def commit(self) -> None:
        self.commits += 1
        self._committed_in_block = True


def _stored(ticket: Ticket) -> Ticket:
    # Events are not persisted with the row; the service hands them to the audit log.
    copy = deepcopy(ticket)
    copy.pull_events()
    return copy
