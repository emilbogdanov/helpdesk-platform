from datetime import timedelta
from uuid import UUID

from helpdesk.domain.ids import TicketId, UserId
from helpdesk.domain.tickets.status import TicketStatus
from helpdesk.domain.tickets.ticket import Ticket
from helpdesk.domain.tickets.values import Description, Priority, Subject
from tests.unit.domain.tickets.builders import MILA, OPENED_AT, OTHER_CUSTOMER, REQUESTER, STEFAN

SUBJECTS = [
    "Can't add a second admin to our workspace",
    "Invoice PDF shows last month's VAT rate",
    "SSO login loops back to the sign-in page",
    "CSV export drops rows with commas in the name",
    "Webhook retries stopped after the outage",
    "Two-factor codes arrive after they expire",
    "Dark mode resets on every login",
]


def catalogue_ticket(
    number: int,
    *,
    requester: UserId,
    status: TicketStatus = TicketStatus.OPEN,
    priority: Priority = Priority.NORMAL,
    assignee: UserId | None = None,
    opened_minutes_in: int,
    updated_minutes_in: int | None = None,
) -> Ticket:
    opened = OPENED_AT + timedelta(minutes=opened_minutes_in)
    return Ticket(
        ticket_id=TicketId(UUID(int=number)),
        requester_id=requester,
        subject=Subject(SUBJECTS[number - 1]),
        description=Description("Details in the first comment."),
        priority=priority,
        status=status,
        assignee_id=assignee,
        created_at=opened,
        updated_at=OPENED_AT + timedelta(minutes=updated_minutes_in or opened_minutes_in),
        resolved_at=None,
        closed_at=None,
        first_responded_at=None,
    )


def catalogue() -> list[Ticket]:
    """Seven tickets with a spread of owners, states and times, including tied timestamps."""
    return [
        catalogue_ticket(1, requester=REQUESTER, opened_minutes_in=0, updated_minutes_in=90),
        catalogue_ticket(
            2,
            requester=REQUESTER,
            status=TicketStatus.IN_PROGRESS,
            priority=Priority.HIGH,
            assignee=MILA,
            opened_minutes_in=10,
            updated_minutes_in=20,
        ),
        catalogue_ticket(
            3, requester=OTHER_CUSTOMER, priority=Priority.URGENT, opened_minutes_in=20
        ),
        catalogue_ticket(
            4,
            requester=OTHER_CUSTOMER,
            status=TicketStatus.WAITING_ON_CUSTOMER,
            assignee=STEFAN,
            opened_minutes_in=30,
        ),
        # 5 and 6 are opened in the same instant, so only the id orders them.
        catalogue_ticket(5, requester=REQUESTER, priority=Priority.LOW, opened_minutes_in=40),
        catalogue_ticket(
            6,
            requester=OTHER_CUSTOMER,
            status=TicketStatus.RESOLVED,
            assignee=MILA,
            opened_minutes_in=40,
            updated_minutes_in=60,
        ),
        catalogue_ticket(7, requester=REQUESTER, priority=Priority.HIGH, opened_minutes_in=50),
    ]


def numbers(tickets: list[Ticket]) -> list[int]:
    return [ticket.id.int for ticket in tickets]
