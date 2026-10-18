from collections.abc import Sequence
from datetime import datetime
from types import TracebackType
from typing import Protocol, Self

from helpdesk.domain.ids import TicketId, UserId
from helpdesk.domain.tickets.comment import Comment
from helpdesk.domain.tickets.events import TicketEvent
from helpdesk.domain.tickets.ticket import Ticket


class Clock(Protocol):
    def now(self) -> datetime: ...


class TicketRepository(Protocol):
    async def get(self, ticket_id: TicketId) -> Ticket | None: ...

    async def find_by_idempotency_key(self, requester_id: UserId, key: str) -> Ticket | None: ...

    # Raises IdempotencyKeyConflictError if the requester already used the key.
    async def add(self, ticket: Ticket, *, idempotency_key: str | None) -> None: ...

    async def update(self, ticket: Ticket) -> None: ...


class CommentRepository(Protocol):
    async def add(self, comment: Comment) -> None: ...

    # Oldest first: the thread reads top to bottom.
    async def list_for_ticket(
        self, ticket_id: TicketId, *, include_internal: bool
    ) -> list[Comment]: ...


class AuditLog(Protocol):
    # Domain events don't know who caused them; the audit trail needs that, so it's added here.
    async def record(self, actor_id: UserId, events: Sequence[TicketEvent]) -> None: ...


class UnitOfWork(Protocol):
    @property
    def tickets(self) -> TicketRepository: ...

    @property
    def comments(self) -> CommentRepository: ...

    @property
    def audit(self) -> AuditLog: ...

    async def __aenter__(self) -> Self: ...

    # Leaving the block without commit() rolls back.
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...
