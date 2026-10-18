import pytest

from helpdesk.domain.tickets.status import TicketStatus

OPEN = TicketStatus.OPEN
IN_PROGRESS = TicketStatus.IN_PROGRESS
WAITING = TicketStatus.WAITING_ON_CUSTOMER
RESOLVED = TicketStatus.RESOLVED
CLOSED = TicketStatus.CLOSED

ALLOWED = {
    (OPEN, IN_PROGRESS),
    (OPEN, RESOLVED),
    (OPEN, CLOSED),
    (IN_PROGRESS, OPEN),
    (IN_PROGRESS, WAITING),
    (IN_PROGRESS, RESOLVED),
    (WAITING, IN_PROGRESS),
    (WAITING, RESOLVED),
    (RESOLVED, OPEN),
    (RESOLVED, CLOSED),
}

ALL_PAIRS = [(current, target) for current in TicketStatus for target in TicketStatus]


@pytest.mark.parametrize(("current", "target"), sorted(ALLOWED))
def test_allowed_transition(current: TicketStatus, target: TicketStatus) -> None:
    assert current.can_transition_to(target)


@pytest.mark.parametrize(
    ("current", "target"),
    [pair for pair in ALL_PAIRS if pair not in ALLOWED],
)
def test_every_other_transition_is_rejected(current: TicketStatus, target: TicketStatus) -> None:
    assert not current.can_transition_to(target)


def test_closed_is_final() -> None:
    assert not any(CLOSED.can_transition_to(target) for target in TicketStatus)


@pytest.mark.parametrize("status", list(TicketStatus))
def test_no_status_transitions_to_itself(status: TicketStatus) -> None:
    assert not status.can_transition_to(status)


@pytest.mark.parametrize("status", [IN_PROGRESS, WAITING])
def test_worked_statuses_require_an_assignee(status: TicketStatus) -> None:
    assert status.requires_assignee


@pytest.mark.parametrize("status", [OPEN, RESOLVED, CLOSED])
def test_other_statuses_allow_no_assignee(status: TicketStatus) -> None:
    assert not status.requires_assignee
