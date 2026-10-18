from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Final, Literal

from helpdesk.domain.ids import TicketId, UserId
from helpdesk.domain.tickets.status import TicketStatus
from helpdesk.domain.tickets.ticket import Ticket
from helpdesk.domain.tickets.values import Priority

UNASSIGNED: Final = "unassigned"
MAX_PAGE_SIZE = 100


class TicketSort(StrEnum):
    NEWEST = "newest"
    OLDEST = "oldest"
    RECENTLY_UPDATED = "recently_updated"

    @property
    def descending(self) -> bool:
        return self is not TicketSort.OLDEST

    @property
    def by_update(self) -> bool:
        return self is TicketSort.RECENTLY_UPDATED

    def key_of(self, ticket: Ticket) -> datetime:
        return ticket.updated_at if self.by_update else ticket.created_at


# Keyset pagination: a page starts after the last ticket of the previous one, identified by
# its sort timestamp with the id as tie-breaker. Unlike OFFSET, pages don't skip or repeat
# rows when tickets are added while someone is paging, and deep pages cost the same.
@dataclass(frozen=True, slots=True)
class TicketCursor:
    sort_value: datetime
    ticket_id: TicketId


@dataclass(frozen=True, slots=True, kw_only=True)
class TicketQuery:
    # Empty sets mean "any".
    statuses: frozenset[TicketStatus] = frozenset()
    priorities: frozenset[Priority] = frozenset()
    requester_id: UserId | None = None
    assignee: UserId | Literal["unassigned"] | None = None
    sort: TicketSort = TicketSort.NEWEST
    after: TicketCursor | None = None
    limit: int = 25


@dataclass(frozen=True, slots=True)
class TicketPage:
    tickets: list[Ticket]
    next_cursor: TicketCursor | None
