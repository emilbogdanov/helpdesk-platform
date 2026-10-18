from dataclasses import dataclass
from datetime import datetime

from helpdesk.domain.ids import TicketId, UserId
from helpdesk.domain.tickets.status import TicketStatus
from helpdesk.domain.tickets.values import Priority


@dataclass(frozen=True, slots=True, kw_only=True)
class TicketEvent:
    ticket_id: TicketId
    occurred_at: datetime


@dataclass(frozen=True, slots=True, kw_only=True)
class TicketOpened(TicketEvent):
    requester_id: UserId
    priority: Priority


@dataclass(frozen=True, slots=True, kw_only=True)
class TicketStatusChanged(TicketEvent):
    previous: TicketStatus
    current: TicketStatus


@dataclass(frozen=True, slots=True, kw_only=True)
class TicketAssigneeChanged(TicketEvent):
    previous: UserId | None
    current: UserId | None


@dataclass(frozen=True, slots=True, kw_only=True)
class TicketPriorityChanged(TicketEvent):
    previous: Priority
    current: Priority
