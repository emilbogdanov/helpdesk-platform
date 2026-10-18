from uuid import UUID

import pytest

from helpdesk.application.actor import Actor
from helpdesk.application.errors import (
    IdempotencyKeyConflictError,
    IdempotencyKeyReusedError,
    InvalidAssigneeError,
    StaffOnlyError,
    TicketNotFoundError,
)
from helpdesk.application.tickets.ticket_service import TicketService
from helpdesk.domain.ids import UserId
from helpdesk.domain.roles import Role
from helpdesk.domain.tickets.errors import AssigneeRequiredError, InvalidStatusTransitionError
from helpdesk.domain.tickets.events import (
    TicketAssigneeChanged,
    TicketOpened,
    TicketPriorityChanged,
    TicketStatusChanged,
)
from helpdesk.domain.tickets.status import TicketStatus
from helpdesk.domain.tickets.ticket import Ticket
from helpdesk.domain.tickets.values import Description, Priority, Subject
from tests.unit.application.fakes import FakeUnitOfWork, FixedClock, InMemoryTicketRepository
from tests.unit.domain.tickets.builders import (
    LATER,
    MILA,
    OPENED_AT,
    OTHER_CUSTOMER,
    REQUESTER,
    STEFAN,
    TICKET_ID,
    open_ticket,
    ticket_in,
)
from tests.unit.domain.users.builders import everyone

CUSTOMER = Actor(REQUESTER, Role.CUSTOMER)
AGENT_MILA = Actor(MILA, Role.AGENT)
AGENT_STEFAN = Actor(STEFAN, Role.AGENT)

SUBJECT = Subject("Can't add a second admin to our workspace")
DESCRIPTION = Description("The Invite button is greyed out on Settings > Members.")


@pytest.fixture
def uow() -> FakeUnitOfWork:
    return FakeUnitOfWork()


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(LATER)


@pytest.fixture
def service(uow: FakeUnitOfWork, clock: FixedClock) -> TicketService:
    return TicketService(uow, clock)


async def seed(uow: FakeUnitOfWork, ticket: Ticket) -> None:
    await uow.tickets.add(ticket, idempotency_key=None)


async def seed_people(uow: FakeUnitOfWork) -> None:
    for person in everyone():
        await uow.users.add(person)


async def stored(uow: FakeUnitOfWork) -> Ticket:
    ticket = await uow.tickets.get(TICKET_ID)
    assert ticket is not None
    return ticket


class TestOpenTicket:
    async def test_actor_becomes_the_requester(
        self, service: TicketService, uow: FakeUnitOfWork
    ) -> None:
        ticket = await service.open_ticket(
            CUSTOMER, subject=SUBJECT, description=DESCRIPTION, priority=Priority.HIGH
        )

        saved = await uow.tickets.get(ticket.id)
        assert saved is not None
        assert saved.requester_id == REQUESTER
        assert saved.subject == SUBJECT
        assert saved.status is TicketStatus.OPEN
        assert saved.created_at == LATER
        assert uow.commits == 1
        assert uow.audit.entries == [
            (
                REQUESTER,
                TicketOpened(
                    ticket_id=ticket.id,
                    occurred_at=LATER,
                    requester_id=REQUESTER,
                    priority=Priority.HIGH,
                ),
            )
        ]

    async def test_without_a_key_every_call_opens_a_new_ticket(
        self, service: TicketService, uow: FakeUnitOfWork
    ) -> None:
        for _ in range(2):
            await service.open_ticket(
                CUSTOMER, subject=SUBJECT, description=DESCRIPTION, priority=Priority.NORMAL
            )

        assert len(uow.tickets.rows) == 2

    async def test_retry_with_the_same_key_returns_the_original_ticket(
        self, service: TicketService, uow: FakeUnitOfWork, clock: FixedClock
    ) -> None:
        first = await service.open_ticket(
            CUSTOMER,
            subject=SUBJECT,
            description=DESCRIPTION,
            priority=Priority.NORMAL,
            idempotency_key="b7c1e0d2-retry",
        )
        clock.current = OPENED_AT

        retry = await service.open_ticket(
            CUSTOMER,
            subject=SUBJECT,
            description=DESCRIPTION,
            priority=Priority.NORMAL,
            idempotency_key="b7c1e0d2-retry",
        )

        assert retry.id == first.id
        assert retry.created_at == LATER
        assert len(uow.tickets.rows) == 1
        assert len(uow.audit.entries) == 1
        assert uow.commits == 1

    async def test_reusing_a_key_for_a_different_ticket_is_rejected(
        self, service: TicketService, uow: FakeUnitOfWork
    ) -> None:
        await service.open_ticket(
            CUSTOMER,
            subject=SUBJECT,
            description=DESCRIPTION,
            priority=Priority.NORMAL,
            idempotency_key="b7c1e0d2-retry",
        )

        with pytest.raises(IdempotencyKeyReusedError) as excinfo:
            await service.open_ticket(
                CUSTOMER,
                subject=SUBJECT,
                description=DESCRIPTION,
                priority=Priority.URGENT,
                idempotency_key="b7c1e0d2-retry",
            )

        assert excinfo.value.key == "b7c1e0d2-retry"
        assert len(uow.tickets.rows) == 1

    async def test_keys_are_scoped_to_the_requester(
        self, service: TicketService, uow: FakeUnitOfWork
    ) -> None:
        for actor in (CUSTOMER, Actor(OTHER_CUSTOMER, Role.CUSTOMER)):
            await service.open_ticket(
                actor,
                subject=SUBJECT,
                description=DESCRIPTION,
                priority=Priority.NORMAL,
                idempotency_key="same-key",
            )

        assert len(uow.tickets.rows) == 2


class RacingTicketRepository(InMemoryTicketRepository):
    """Hides stored keys from the first `hidden_lookups` lookups.

    That is what a request sees when a concurrent request with the same key commits after
    its lookup but before its insert.
    """

    def __init__(self, hidden_lookups: int) -> None:
        super().__init__()
        self.hidden_lookups = hidden_lookups

    async def find_by_idempotency_key(self, requester_id: UserId, key: str) -> Ticket | None:
        if self.hidden_lookups > 0:
            self.hidden_lookups -= 1
            return None
        return await super().find_by_idempotency_key(requester_id, key)


class TestIdempotencyKeyRace:
    @pytest.fixture
    async def winner(self, uow: FakeUnitOfWork) -> Ticket:
        uow.tickets = RacingTicketRepository(hidden_lookups=1)
        ticket = Ticket.open(
            ticket_id=TICKET_ID,
            requester_id=REQUESTER,
            subject=SUBJECT,
            description=DESCRIPTION,
            priority=Priority.NORMAL,
            at=OPENED_AT,
        )
        await uow.tickets.add(ticket, idempotency_key="b7c1e0d2-retry")
        return ticket

    async def test_loser_gets_the_winners_ticket(
        self, service: TicketService, uow: FakeUnitOfWork, winner: Ticket
    ) -> None:
        ticket = await service.open_ticket(
            CUSTOMER,
            subject=SUBJECT,
            description=DESCRIPTION,
            priority=Priority.NORMAL,
            idempotency_key="b7c1e0d2-retry",
        )

        assert ticket.id == winner.id
        assert list(uow.tickets.rows) == [winner.id]
        assert uow.audit.entries == []
        assert uow.commits == 0

    async def test_loser_with_a_different_request_is_rejected(
        self, service: TicketService, winner: Ticket
    ) -> None:
        with pytest.raises(IdempotencyKeyReusedError):
            await service.open_ticket(
                CUSTOMER,
                subject=winner.subject,
                description=winner.description,
                priority=Priority.URGENT,
                idempotency_key="b7c1e0d2-retry",
            )

    async def test_conflict_without_a_visible_winner_is_not_swallowed(
        self, service: TicketService, uow: FakeUnitOfWork, winner: Ticket
    ) -> None:
        assert isinstance(uow.tickets, RacingTicketRepository)
        uow.tickets.hidden_lookups = 2

        with pytest.raises(IdempotencyKeyConflictError):
            await service.open_ticket(
                CUSTOMER,
                subject=winner.subject,
                description=winner.description,
                priority=winner.priority,
                idempotency_key="b7c1e0d2-retry",
            )


class TestGetTicket:
    async def test_requester_sees_their_ticket(
        self, service: TicketService, uow: FakeUnitOfWork
    ) -> None:
        await seed(uow, open_ticket())

        ticket = await service.get_ticket(CUSTOMER, TICKET_ID)

        assert ticket.id == TICKET_ID

    async def test_other_customers_get_not_found(
        self, service: TicketService, uow: FakeUnitOfWork
    ) -> None:
        await seed(uow, open_ticket())

        with pytest.raises(TicketNotFoundError):
            await service.get_ticket(Actor(OTHER_CUSTOMER, Role.CUSTOMER), TICKET_ID)


class TestChangeStatus:
    async def test_persists_and_audits_the_change(
        self, service: TicketService, uow: FakeUnitOfWork
    ) -> None:
        await seed(uow, ticket_in(TicketStatus.OPEN))

        ticket = await service.change_status(AGENT_MILA, TICKET_ID, TicketStatus.IN_PROGRESS)

        assert ticket.status is TicketStatus.IN_PROGRESS
        assert (await stored(uow)).status is TicketStatus.IN_PROGRESS
        assert uow.commits == 1
        assert uow.audit.entries == [
            (
                MILA,
                TicketStatusChanged(
                    ticket_id=TICKET_ID,
                    occurred_at=LATER,
                    previous=TicketStatus.OPEN,
                    current=TicketStatus.IN_PROGRESS,
                ),
            )
        ]

    async def test_customers_are_refused_before_the_ticket_is_looked_up(
        self, service: TicketService
    ) -> None:
        # Nothing is seeded: a customer must not learn whether the ticket exists.
        with pytest.raises(StaffOnlyError):
            await service.change_status(CUSTOMER, TICKET_ID, TicketStatus.RESOLVED)

    async def test_rule_violation_leaves_the_ticket_untouched(
        self, service: TicketService, uow: FakeUnitOfWork
    ) -> None:
        await seed(uow, ticket_in(TicketStatus.WAITING_ON_CUSTOMER))

        with pytest.raises(InvalidStatusTransitionError):
            await service.change_status(AGENT_MILA, TICKET_ID, TicketStatus.CLOSED)

        assert (await stored(uow)).status is TicketStatus.WAITING_ON_CUSTOMER
        assert uow.commits == 0
        assert uow.audit.entries == []

    async def test_missing_ticket_is_not_found(self, service: TicketService) -> None:
        with pytest.raises(TicketNotFoundError):
            await service.change_status(AGENT_MILA, TICKET_ID, TicketStatus.RESOLVED)


class TestAssignment:
    async def test_admin_assigns_a_ticket_to_an_agent(
        self, service: TicketService, uow: FakeUnitOfWork
    ) -> None:
        await seed_people(uow)
        await seed(uow, open_ticket())

        ticket = await service.assign(Actor(STEFAN, Role.ADMIN), TICKET_ID, MILA)

        assert ticket.assignee_id == MILA
        assert (await stored(uow)).assignee_id == MILA
        assert uow.audit.entries == [
            (
                STEFAN,
                TicketAssigneeChanged(
                    ticket_id=TICKET_ID, occurred_at=LATER, previous=None, current=MILA
                ),
            )
        ]

    @pytest.mark.parametrize(
        "assignee",
        [REQUESTER, MILA, UserId(UUID(int=404))],
        ids=["customer", "deactivated-agent", "unknown-user"],
    )
    async def test_assignee_must_be_active_staff(
        self, service: TicketService, uow: FakeUnitOfWork, assignee: UserId
    ) -> None:
        await seed_people(uow)
        uow.users.rows[MILA].deactivate()
        await seed(uow, open_ticket())

        with pytest.raises(InvalidAssigneeError) as excinfo:
            await service.assign(AGENT_STEFAN, TICKET_ID, assignee)

        assert excinfo.value.user_id == assignee
        assert (await stored(uow)).assignee_id is None
        assert uow.commits == 0

    async def test_customers_cannot_assign_tickets(self, service: TicketService) -> None:
        with pytest.raises(StaffOnlyError, match="assign tickets"):
            await service.assign(CUSTOMER, TICKET_ID, MILA)

    async def test_agent_takes_an_unassigned_ticket(
        self, service: TicketService, uow: FakeUnitOfWork
    ) -> None:
        await seed(uow, open_ticket())

        ticket = await service.take(AGENT_STEFAN, TICKET_ID)

        assert ticket.assignee_id == STEFAN
        assert (await stored(uow)).assignee_id == STEFAN
        assert uow.audit.entries == [
            (
                STEFAN,
                TicketAssigneeChanged(
                    ticket_id=TICKET_ID, occurred_at=LATER, previous=None, current=STEFAN
                ),
            )
        ]

    async def test_taking_a_ticket_you_already_own_commits_nothing(
        self, service: TicketService, uow: FakeUnitOfWork
    ) -> None:
        await seed(uow, ticket_in(TicketStatus.IN_PROGRESS))

        await service.take(AGENT_MILA, TICKET_ID)

        assert uow.commits == 0
        assert uow.audit.entries == []

    async def test_customers_cannot_take_tickets(self, service: TicketService) -> None:
        with pytest.raises(StaffOnlyError, match="take tickets"):
            await service.take(CUSTOMER, TICKET_ID)

    async def test_unassign_releases_an_open_ticket(
        self, service: TicketService, uow: FakeUnitOfWork
    ) -> None:
        await seed(uow, ticket_in(TicketStatus.OPEN))

        await service.unassign(AGENT_MILA, TICKET_ID)

        assert (await stored(uow)).assignee_id is None
        assert uow.commits == 1

    async def test_unassigning_a_ticket_in_progress_is_refused(
        self, service: TicketService, uow: FakeUnitOfWork
    ) -> None:
        await seed(uow, ticket_in(TicketStatus.IN_PROGRESS))

        with pytest.raises(AssigneeRequiredError):
            await service.unassign(AGENT_MILA, TICKET_ID)

        assert (await stored(uow)).assignee_id == MILA
        assert uow.commits == 0


class TestChangePriority:
    async def test_persists_and_audits_the_change(
        self, service: TicketService, uow: FakeUnitOfWork
    ) -> None:
        await seed(uow, open_ticket())

        await service.change_priority(AGENT_MILA, TICKET_ID, Priority.URGENT)

        assert (await stored(uow)).priority is Priority.URGENT
        assert uow.audit.entries == [
            (
                MILA,
                TicketPriorityChanged(
                    ticket_id=TICKET_ID,
                    occurred_at=LATER,
                    previous=Priority.NORMAL,
                    current=Priority.URGENT,
                ),
            )
        ]

    async def test_same_priority_commits_nothing(
        self, service: TicketService, uow: FakeUnitOfWork
    ) -> None:
        await seed(uow, open_ticket())

        await service.change_priority(AGENT_MILA, TICKET_ID, Priority.NORMAL)

        assert uow.commits == 0

    async def test_customers_cannot_change_priority(self, service: TicketService) -> None:
        with pytest.raises(StaffOnlyError, match="change ticket priority"):
            await service.change_priority(CUSTOMER, TICKET_ID, Priority.URGENT)
