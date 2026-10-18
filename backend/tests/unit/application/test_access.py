import pytest

from helpdesk.application.actor import Actor
from helpdesk.application.errors import StaffOnlyError, TicketNotFoundError
from helpdesk.application.tickets.access import load_visible_ticket, require_staff
from helpdesk.domain.roles import Role
from tests.unit.application.fakes import InMemoryTicketRepository
from tests.unit.domain.tickets.builders import (
    MILA,
    OTHER_CUSTOMER,
    REQUESTER,
    TICKET_ID,
    open_ticket,
)


@pytest.fixture
async def tickets() -> InMemoryTicketRepository:
    repository = InMemoryTicketRepository()
    await repository.add(open_ticket(), idempotency_key=None)
    return repository


@pytest.mark.parametrize(
    "actor",
    [
        Actor(REQUESTER, Role.CUSTOMER),
        Actor(MILA, Role.AGENT),
        Actor(MILA, Role.ADMIN),
    ],
    ids=["requester", "agent", "admin"],
)
async def test_requester_and_staff_can_see_the_ticket(
    tickets: InMemoryTicketRepository, actor: Actor
) -> None:
    ticket = await load_visible_ticket(tickets, actor, TICKET_ID)

    assert ticket.id == TICKET_ID


async def test_other_customers_get_not_found(tickets: InMemoryTicketRepository) -> None:
    with pytest.raises(TicketNotFoundError) as excinfo:
        await load_visible_ticket(tickets, Actor(OTHER_CUSTOMER, Role.CUSTOMER), TICKET_ID)

    assert excinfo.value.ticket_id == TICKET_ID


async def test_missing_ticket_is_not_found() -> None:
    with pytest.raises(TicketNotFoundError):
        await load_visible_ticket(InMemoryTicketRepository(), Actor(MILA, Role.AGENT), TICKET_ID)


@pytest.mark.parametrize("role", [Role.AGENT, Role.ADMIN])
def test_require_staff_lets_staff_through(role: Role) -> None:
    require_staff(Actor(MILA, role), "change ticket status")


def test_require_staff_names_the_refused_action() -> None:
    with pytest.raises(StaffOnlyError, match="only agents and admins can change ticket status"):
        require_staff(Actor(REQUESTER, Role.CUSTOMER), "change ticket status")
