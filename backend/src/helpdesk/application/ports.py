from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from types import TracebackType
from typing import Protocol, Self

from helpdesk.application.tickets.queries import TicketQuery
from helpdesk.domain.ids import TicketId, UserId
from helpdesk.domain.tickets.comment import Comment
from helpdesk.domain.tickets.events import TicketEvent
from helpdesk.domain.tickets.ticket import Ticket
from helpdesk.domain.tickets.values import Priority
from helpdesk.domain.users.user import User
from helpdesk.domain.users.values import EmailAddress, Password


class Clock(Protocol):
    def now(self) -> datetime: ...


class TicketRepository(Protocol):
    async def get(self, ticket_id: TicketId) -> Ticket | None: ...

    async def find_by_idempotency_key(self, requester_id: UserId, key: str) -> Ticket | None: ...

    # Raises IdempotencyKeyConflictError if the requester already used the key.
    async def add(self, ticket: Ticket, *, idempotency_key: str | None) -> None: ...

    async def update(self, ticket: Ticket) -> None: ...

    # At most query.limit tickets in the query's sort order, starting after query.after.
    async def find(self, query: TicketQuery) -> list[Ticket]: ...

    # Candidates for the worker, oldest first. Only a prefilter: the Ticket itself decides,
    # after it is loaded, whether anything applies.
    async def find_awaiting_first_response(
        self, opened_before: Mapping[Priority, datetime], *, limit: int
    ) -> list[TicketId]: ...

    async def find_resolved_before(self, cutoff: datetime, *, limit: int) -> list[TicketId]: ...


class CommentRepository(Protocol):
    async def add(self, comment: Comment) -> None: ...

    # Oldest first: the thread reads top to bottom.
    async def list_for_ticket(
        self, ticket_id: TicketId, *, include_internal: bool
    ) -> list[Comment]: ...


class UserRepository(Protocol):
    async def get(self, user_id: UserId) -> User | None: ...

    # Unknown ids are left out rather than raising.
    async def get_many(self, user_ids: Collection[UserId]) -> list[User]: ...

    async def get_by_email(self, email: EmailAddress) -> User | None: ...

    # Raises EmailTakenError if another account already uses the address.
    async def add(self, user: User) -> None: ...

    async def update(self, user: User) -> None: ...


class PasswordHasher(Protocol):
    async def hash(self, password: Password) -> str: ...

    # With no hash (unknown account) it still spends the time of a real check and returns
    # False, so response times don't reveal which email addresses have accounts.
    async def verify(self, password_hash: str | None, candidate: str) -> bool: ...


@dataclass(frozen=True, slots=True)
class TokenClaims:
    user_id: UserId
    expires_at: datetime


class TokenCodec(Protocol):
    def encode(self, claims: TokenClaims) -> str: ...

    # Raises InvalidTokenError unless we signed the token. Expiry is left to the caller,
    # which owns the clock.
    def decode(self, token: str) -> TokenClaims: ...


class AuditLog(Protocol):
    # Domain events don't know who caused them; the audit trail needs that, so it's added here.
    # No actor means the system did it, e.g. the worker closing a ticket.
    async def record(self, actor_id: UserId | None, events: Sequence[TicketEvent]) -> None: ...


class UnitOfWork(Protocol):
    @property
    def tickets(self) -> TicketRepository: ...

    @property
    def comments(self) -> CommentRepository: ...

    @property
    def audit(self) -> AuditLog: ...

    @property
    def users(self) -> UserRepository: ...

    async def __aenter__(self) -> Self: ...

    # Leaving the block without commit() rolls back.
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...

    # Raises ConcurrentUpdateError if a ticket changed since it was loaded in this block.
    async def commit(self) -> None: ...
