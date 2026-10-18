from collections.abc import Callable

import pytest

from helpdesk.domain.tickets.errors import (
    AssigneeRequiredError,
    InvalidStatusTransitionError,
    TicketClosedError,
)
from helpdesk.domain.tickets.events import (
    TicketAssigneeChanged,
    TicketOpened,
    TicketPriorityChanged,
    TicketStatusChanged,
)
from helpdesk.domain.tickets.status import TicketStatus
from helpdesk.domain.tickets.ticket import Ticket
from helpdesk.domain.tickets.values import Description, Priority, Subject
from tests.unit.domain.tickets.builders import (
    LATER,
    MILA,
    MUCH_LATER,
    OPENED_AT,
    REQUESTER,
    STEFAN,
    TICKET_ID,
    open_ticket,
    ticket_in,
)


class TestOpen:
    def test_starts_open_and_unassigned(self) -> None:
        ticket = open_ticket(Priority.HIGH)

        assert ticket.id == TICKET_ID
        assert ticket.requester_id == REQUESTER
        assert ticket.subject == Subject("Invoice PDF shows last month's VAT rate")
        assert str(ticket.description).startswith("Downloaded the October invoice")
        assert ticket.status is TicketStatus.OPEN
        assert ticket.priority is Priority.HIGH
        assert ticket.assignee_id is None
        assert ticket.created_at == ticket.updated_at == OPENED_AT
        assert ticket.resolved_at is None
        assert ticket.closed_at is None
        assert ticket.first_responded_at is None

    def test_records_ticket_opened(self) -> None:
        ticket = open_ticket(Priority.HIGH)

        assert ticket.pull_events() == [
            TicketOpened(
                ticket_id=TICKET_ID,
                occurred_at=OPENED_AT,
                requester_id=REQUESTER,
                priority=Priority.HIGH,
            )
        ]


class TestPullEvents:
    def test_returns_events_once(self) -> None:
        ticket = open_ticket()

        assert len(ticket.pull_events()) == 1
        assert ticket.pull_events() == []


class TestAssignment:
    def test_assign_records_previous_and_new_assignee(self) -> None:
        ticket = ticket_in(TicketStatus.OPEN)

        ticket.assign(STEFAN, at=LATER)

        assert ticket.assignee_id == STEFAN
        assert ticket.updated_at == LATER
        assert ticket.pull_events() == [
            TicketAssigneeChanged(
                ticket_id=TICKET_ID, occurred_at=LATER, previous=MILA, current=STEFAN
            )
        ]

    def test_reassigning_a_ticket_in_progress_is_allowed(self) -> None:
        ticket = ticket_in(TicketStatus.IN_PROGRESS)

        ticket.assign(STEFAN, at=LATER)

        assert ticket.assignee_id == STEFAN
        assert ticket.status is TicketStatus.IN_PROGRESS

    def test_assigning_the_current_assignee_changes_nothing(self) -> None:
        ticket = ticket_in(TicketStatus.OPEN)

        ticket.assign(MILA, at=LATER)

        assert ticket.updated_at == OPENED_AT
        assert ticket.pull_events() == []

    @pytest.mark.parametrize("status", [TicketStatus.OPEN, TicketStatus.RESOLVED])
    def test_unassign_returns_ticket_to_nobody(self, status: TicketStatus) -> None:
        ticket = ticket_in(status)

        ticket.unassign(at=LATER)

        assert ticket.assignee_id is None
        assert ticket.pull_events() == [
            TicketAssigneeChanged(
                ticket_id=TICKET_ID, occurred_at=LATER, previous=MILA, current=None
            )
        ]

    def test_unassign_without_assignee_changes_nothing(self) -> None:
        ticket = open_ticket()
        ticket.pull_events()

        ticket.unassign(at=LATER)

        assert ticket.updated_at == OPENED_AT
        assert ticket.pull_events() == []

    @pytest.mark.parametrize("status", [TicketStatus.IN_PROGRESS, TicketStatus.WAITING_ON_CUSTOMER])
    def test_cannot_unassign_a_ticket_being_worked(self, status: TicketStatus) -> None:
        ticket = ticket_in(status)

        with pytest.raises(AssigneeRequiredError) as excinfo:
            ticket.unassign(at=LATER)

        assert excinfo.value.status is status
        assert ticket.assignee_id == MILA
        assert ticket.pull_events() == []


class TestStatusChanges:
    def test_records_previous_and_new_status(self) -> None:
        ticket = ticket_in(TicketStatus.OPEN)

        ticket.change_status(TicketStatus.IN_PROGRESS, at=LATER)

        assert ticket.status is TicketStatus.IN_PROGRESS
        assert ticket.updated_at == LATER
        assert ticket.pull_events() == [
            TicketStatusChanged(
                ticket_id=TICKET_ID,
                occurred_at=LATER,
                previous=TicketStatus.OPEN,
                current=TicketStatus.IN_PROGRESS,
            )
        ]

    def test_cannot_start_work_without_an_assignee(self) -> None:
        ticket = open_ticket()
        ticket.pull_events()

        with pytest.raises(AssigneeRequiredError):
            ticket.change_status(TicketStatus.IN_PROGRESS, at=LATER)

        assert ticket.status is TicketStatus.OPEN
        assert ticket.pull_events() == []

    def test_rejects_transition_outside_the_lifecycle(self) -> None:
        ticket = ticket_in(TicketStatus.WAITING_ON_CUSTOMER)

        with pytest.raises(InvalidStatusTransitionError) as excinfo:
            ticket.change_status(TicketStatus.CLOSED, at=LATER)

        assert excinfo.value.current is TicketStatus.WAITING_ON_CUSTOMER
        assert excinfo.value.target is TicketStatus.CLOSED
        assert ticket.status is TicketStatus.WAITING_ON_CUSTOMER
        assert ticket.updated_at == OPENED_AT
        assert ticket.pull_events() == []

    def test_resolving_stamps_resolved_at(self) -> None:
        ticket = ticket_in(TicketStatus.IN_PROGRESS)

        ticket.change_status(TicketStatus.RESOLVED, at=LATER)

        assert ticket.resolved_at == LATER

    def test_reopening_clears_resolved_at(self) -> None:
        ticket = ticket_in(TicketStatus.RESOLVED)

        ticket.change_status(TicketStatus.OPEN, at=LATER)

        assert ticket.status is TicketStatus.OPEN
        assert ticket.resolved_at is None
        assert ticket.assignee_id == MILA

    def test_closing_a_resolved_ticket_keeps_its_resolution_time(self) -> None:
        ticket = ticket_in(TicketStatus.IN_PROGRESS)
        ticket.change_status(TicketStatus.RESOLVED, at=LATER)

        ticket.change_status(TicketStatus.CLOSED, at=MUCH_LATER)

        assert ticket.resolved_at == LATER
        assert ticket.closed_at == MUCH_LATER

    def test_closing_straight_from_open_leaves_it_unresolved(self) -> None:
        ticket = open_ticket()

        ticket.change_status(TicketStatus.CLOSED, at=LATER)

        assert ticket.closed_at == LATER
        assert ticket.resolved_at is None


class TestPriority:
    def test_change_records_previous_and_new_priority(self) -> None:
        ticket = ticket_in(TicketStatus.OPEN)

        ticket.change_priority(Priority.URGENT, at=LATER)

        assert ticket.priority is Priority.URGENT
        assert ticket.updated_at == LATER
        assert ticket.pull_events() == [
            TicketPriorityChanged(
                ticket_id=TICKET_ID,
                occurred_at=LATER,
                previous=Priority.NORMAL,
                current=Priority.URGENT,
            )
        ]

    def test_setting_the_same_priority_changes_nothing(self) -> None:
        ticket = ticket_in(TicketStatus.OPEN)

        ticket.change_priority(Priority.NORMAL, at=LATER)

        assert ticket.updated_at == OPENED_AT
        assert ticket.pull_events() == []


class TestClosedTicket:
    @pytest.mark.parametrize(
        "change",
        [
            pytest.param(lambda t: t.change_status(TicketStatus.OPEN, at=LATER), id="reopen"),
            pytest.param(lambda t: t.assign(STEFAN, at=LATER), id="assign"),
            pytest.param(lambda t: t.unassign(at=LATER), id="unassign"),
            pytest.param(lambda t: t.change_priority(Priority.URGENT, at=LATER), id="priority"),
        ],
    )
    def test_rejects_every_change(self, change: Callable[[Ticket], None]) -> None:
        ticket = ticket_in(TicketStatus.CLOSED)

        with pytest.raises(TicketClosedError) as excinfo:
            change(ticket)

        assert excinfo.value.ticket_id == TICKET_ID
        assert ticket.updated_at == OPENED_AT
        assert ticket.pull_events() == []


class TestRehydration:
    def test_rejects_a_worked_status_without_assignee(self) -> None:
        with pytest.raises(AssigneeRequiredError):
            Ticket(
                ticket_id=TICKET_ID,
                requester_id=REQUESTER,
                subject=Subject("VPN drops every 20 minutes"),
                description=Description("Started after the 4.2 client update."),
                priority=Priority.HIGH,
                status=TicketStatus.WAITING_ON_CUSTOMER,
                assignee_id=None,
                created_at=OPENED_AT,
                updated_at=LATER,
                resolved_at=None,
                closed_at=None,
                first_responded_at=None,
            )

    def test_records_no_events(self) -> None:
        ticket = Ticket(
            ticket_id=TICKET_ID,
            requester_id=REQUESTER,
            subject=Subject("VPN drops every 20 minutes"),
            description=Description("Started after the 4.2 client update."),
            priority=Priority.HIGH,
            status=TicketStatus.IN_PROGRESS,
            assignee_id=STEFAN,
            created_at=OPENED_AT,
            updated_at=LATER,
            resolved_at=None,
            closed_at=None,
            first_responded_at=None,
        )

        assert ticket.pull_events() == []


class TestIdentity:
    def test_tickets_with_the_same_id_are_equal(self) -> None:
        first = open_ticket()
        second = open_ticket(Priority.URGENT)

        assert first == second
        assert len({first, second}) == 1

    def test_never_equal_to_other_types(self) -> None:
        assert open_ticket() != TICKET_ID

    def test_repr_identifies_the_ticket_in_logs(self) -> None:
        assert repr(open_ticket()) == f"Ticket(id={TICKET_ID}, status=open, assignee_id=None)"
