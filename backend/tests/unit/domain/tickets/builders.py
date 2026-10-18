from datetime import UTC, datetime, timedelta
from uuid import UUID

from helpdesk.domain.ids import TicketId, UserId
from helpdesk.domain.tickets.status import TicketStatus
from helpdesk.domain.tickets.ticket import Ticket
from helpdesk.domain.tickets.values import Description, Priority, Subject

TICKET_ID = TicketId(UUID("0b6d3c1e-5f0a-4a52-9a43-7f3e2d18c901"))
REQUESTER = UserId(UUID("4c2f8e71-93d4-4b6a-8e15-2a9b7c3d5f10"))
OTHER_CUSTOMER = UserId(UUID("7e9a1c3b-2d4f-4a6e-9c8b-0f1e2d3c4b5a"))
MILA = UserId(UUID("a81e4b2c-6d37-4f95-b0c8-1e2d3f4a5b6c"))
STEFAN = UserId(UUID("d5c4b3a2-1f0e-4d9c-8b7a-6f5e4d3c2b1a"))

OPENED_AT = datetime(2026, 10, 12, 9, 14, tzinfo=UTC)
LATER = OPENED_AT + timedelta(minutes=40)
MUCH_LATER = OPENED_AT + timedelta(days=2)

_PATH_FROM_OPEN = {
    TicketStatus.OPEN: [],
    TicketStatus.IN_PROGRESS: [TicketStatus.IN_PROGRESS],
    TicketStatus.WAITING_ON_CUSTOMER: [TicketStatus.IN_PROGRESS, TicketStatus.WAITING_ON_CUSTOMER],
    TicketStatus.RESOLVED: [TicketStatus.IN_PROGRESS, TicketStatus.RESOLVED],
    TicketStatus.CLOSED: [TicketStatus.IN_PROGRESS, TicketStatus.RESOLVED, TicketStatus.CLOSED],
}


def open_ticket(priority: Priority = Priority.NORMAL) -> Ticket:
    return Ticket.open(
        ticket_id=TICKET_ID,
        requester_id=REQUESTER,
        subject=Subject("Invoice PDF shows last month's VAT rate"),
        description=Description("Downloaded the October invoice from Billing; it still uses 19%."),
        priority=priority,
        at=OPENED_AT,
    )


def ticket_in(status: TicketStatus) -> Ticket:
    """An assigned ticket walked to `status` at OPENED_AT, with its events already drained."""
    ticket = open_ticket()
    ticket.assign(MILA, at=OPENED_AT)
    for step in _PATH_FROM_OPEN[status]:
        ticket.change_status(step, at=OPENED_AT)
    ticket.pull_events()
    return ticket
