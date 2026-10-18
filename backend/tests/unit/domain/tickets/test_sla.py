from datetime import timedelta

import pytest

from helpdesk.domain.errors import InvalidValueError
from helpdesk.domain.roles import Role
from helpdesk.domain.tickets.comment import Visibility
from helpdesk.domain.tickets.events import FirstResponseOverdue, TicketStatusChanged
from helpdesk.domain.tickets.sla import DEFAULT_FIRST_RESPONSE_TARGETS, FirstResponseTargets
from helpdesk.domain.tickets.status import TicketStatus
from helpdesk.domain.tickets.values import Priority
from tests.unit.domain.tickets.builders import MILA, OPENED_AT, TICKET_ID, open_ticket, ticket_in
from tests.unit.domain.tickets.test_comments import comment_on

TARGETS = DEFAULT_FIRST_RESPONSE_TARGETS
DAY_LATER = OPENED_AT + timedelta(days=1)


class TestTargets:
    @pytest.mark.parametrize(
        ("priority", "wait"),
        [
            (Priority.URGENT, timedelta(hours=1)),
            (Priority.HIGH, timedelta(hours=4)),
            (Priority.NORMAL, timedelta(days=1)),
            (Priority.LOW, timedelta(days=3)),
        ],
    )
    def test_default_due_times(self, priority: Priority, wait: timedelta) -> None:
        assert TARGETS.due_at(priority, OPENED_AT) == OPENED_AT + wait

    def test_every_priority_needs_a_target(self) -> None:
        with pytest.raises(InvalidValueError, match="every priority"):
            FirstResponseTargets({Priority.URGENT: timedelta(hours=1)})


class TestOverdueFirstResponse:
    def test_unanswered_ticket_past_its_target_is_flagged(self) -> None:
        ticket = open_ticket(Priority.NORMAL)
        ticket.pull_events()

        ticket.flag_overdue_first_response(TARGETS, at=DAY_LATER)

        assert ticket.sla_breached_at == DAY_LATER
        assert ticket.updated_at == OPENED_AT
        assert ticket.pull_events() == [
            FirstResponseOverdue(ticket_id=TICKET_ID, occurred_at=DAY_LATER, due_at=DAY_LATER)
        ]

    def test_not_flagged_before_the_target(self) -> None:
        ticket = open_ticket(Priority.NORMAL)

        ticket.flag_overdue_first_response(TARGETS, at=DAY_LATER - timedelta(seconds=1))

        assert ticket.sla_breached_at is None

    def test_raising_the_priority_brings_the_deadline_forward(self) -> None:
        ticket = open_ticket(Priority.LOW)
        five_hours_in = OPENED_AT + timedelta(hours=5)
        ticket.change_priority(Priority.HIGH, at=OPENED_AT + timedelta(minutes=30))

        ticket.flag_overdue_first_response(TARGETS, at=five_hours_in)

        assert ticket.sla_breached_at == five_hours_in

    def test_answered_tickets_are_never_flagged(self) -> None:
        ticket = ticket_in(TicketStatus.IN_PROGRESS)
        comment_on(ticket, author_id=MILA, author_role=Role.AGENT, visibility=Visibility.PUBLIC)

        ticket.flag_overdue_first_response(TARGETS, at=DAY_LATER + timedelta(days=30))

        assert ticket.sla_breached_at is None

    @pytest.mark.parametrize("status", [TicketStatus.RESOLVED, TicketStatus.CLOSED])
    def test_finished_tickets_are_not_flagged(self, status: TicketStatus) -> None:
        ticket = ticket_in(status)

        ticket.flag_overdue_first_response(TARGETS, at=DAY_LATER + timedelta(days=30))

        assert ticket.sla_breached_at is None

    def test_a_breach_is_flagged_once(self) -> None:
        ticket = open_ticket(Priority.NORMAL)
        ticket.flag_overdue_first_response(TARGETS, at=DAY_LATER)
        ticket.pull_events()

        ticket.flag_overdue_first_response(TARGETS, at=DAY_LATER + timedelta(hours=1))

        assert ticket.sla_breached_at == DAY_LATER
        assert ticket.pull_events() == []

    def test_a_late_reply_keeps_the_breach_on_record(self) -> None:
        ticket = ticket_in(TicketStatus.IN_PROGRESS)
        ticket.flag_overdue_first_response(TARGETS, at=DAY_LATER)

        comment_on(ticket, author_id=MILA, author_role=Role.AGENT)

        assert ticket.sla_breached_at == DAY_LATER
        assert ticket.first_responded_at is not None


class TestAutoClose:
    def test_resolved_before_the_cutoff_closes(self) -> None:
        ticket = ticket_in(TicketStatus.RESOLVED)

        ticket.close_if_resolved_before(OPENED_AT, at=DAY_LATER)

        assert ticket.status is TicketStatus.CLOSED
        assert ticket.closed_at == DAY_LATER
        assert ticket.pull_events() == [
            TicketStatusChanged(
                ticket_id=TICKET_ID,
                occurred_at=DAY_LATER,
                previous=TicketStatus.RESOLVED,
                current=TicketStatus.CLOSED,
            )
        ]

    def test_resolved_after_the_cutoff_stays_resolved(self) -> None:
        ticket = ticket_in(TicketStatus.RESOLVED)

        ticket.close_if_resolved_before(OPENED_AT - timedelta(seconds=1), at=DAY_LATER)

        assert ticket.status is TicketStatus.RESOLVED

    @pytest.mark.parametrize("status", [TicketStatus.OPEN, TicketStatus.IN_PROGRESS])
    def test_reopened_tickets_stay_open(self, status: TicketStatus) -> None:
        ticket = ticket_in(status)

        ticket.close_if_resolved_before(DAY_LATER, at=DAY_LATER)

        assert ticket.status is status
        assert ticket.pull_events() == []
