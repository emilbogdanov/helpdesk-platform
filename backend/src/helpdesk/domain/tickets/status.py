from __future__ import annotations

from enum import StrEnum


class TicketStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    WAITING_ON_CUSTOMER = "waiting_on_customer"
    RESOLVED = "resolved"
    CLOSED = "closed"

    def can_transition_to(self, target: TicketStatus) -> bool:
        return target in _TRANSITIONS[self]

    @property
    def requires_assignee(self) -> bool:
        return self in _WORKED_STATUSES


_TRANSITIONS: dict[TicketStatus, frozenset[TicketStatus]] = {
    # Closing straight from open covers spam and duplicates; everything else goes through resolved.
    TicketStatus.OPEN: frozenset(
        {TicketStatus.IN_PROGRESS, TicketStatus.RESOLVED, TicketStatus.CLOSED}
    ),
    # Back to open releases the ticket to the shared queue.
    TicketStatus.IN_PROGRESS: frozenset(
        {TicketStatus.OPEN, TicketStatus.WAITING_ON_CUSTOMER, TicketStatus.RESOLVED}
    ),
    TicketStatus.WAITING_ON_CUSTOMER: frozenset({TicketStatus.IN_PROGRESS, TicketStatus.RESOLVED}),
    # Reopening is allowed until the ticket closes; after that a follow-up needs a new ticket.
    TicketStatus.RESOLVED: frozenset({TicketStatus.OPEN, TicketStatus.CLOSED}),
    TicketStatus.CLOSED: frozenset(),
}

_WORKED_STATUSES = frozenset({TicketStatus.IN_PROGRESS, TicketStatus.WAITING_ON_CUSTOMER})
