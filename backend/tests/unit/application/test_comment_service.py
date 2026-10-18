from datetime import timedelta

import pytest

from helpdesk.application.actor import Actor
from helpdesk.application.errors import TicketNotFoundError
from helpdesk.application.tickets.comment_service import CommentService
from helpdesk.domain.roles import Role
from helpdesk.domain.tickets.comment import CommentBody, Visibility
from helpdesk.domain.tickets.errors import InternalNoteNotAllowedError, TicketClosedError
from helpdesk.domain.tickets.events import CommentAdded, TicketStatusChanged
from helpdesk.domain.tickets.status import TicketStatus
from tests.unit.application.fakes import FakeUnitOfWork, FixedClock
from tests.unit.domain.tickets.builders import (
    LATER,
    MILA,
    OTHER_CUSTOMER,
    REQUESTER,
    TICKET_ID,
    ticket_in,
)

CUSTOMER = Actor(REQUESTER, Role.CUSTOMER)
AGENT_MILA = Actor(MILA, Role.AGENT)


@pytest.fixture
def uow() -> FakeUnitOfWork:
    return FakeUnitOfWork()


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(LATER)


@pytest.fixture
def service(uow: FakeUnitOfWork, clock: FixedClock) -> CommentService:
    return CommentService(uow, clock)


async def seed(uow: FakeUnitOfWork, status: TicketStatus) -> None:
    await uow.tickets.add(ticket_in(status), idempotency_key=None)


class TestAddComment:
    async def test_stores_the_comment_and_audits_it(
        self, service: CommentService, uow: FakeUnitOfWork
    ) -> None:
        await seed(uow, TicketStatus.IN_PROGRESS)

        comment = await service.add_comment(
            AGENT_MILA,
            TICKET_ID,
            body=CommentBody("Reproduced it. The Invite button needs the Owner role."),
            visibility=Visibility.PUBLIC,
        )

        assert uow.comments.rows == [comment]
        assert comment.author_id == MILA
        assert comment.created_at == LATER
        assert uow.commits == 1
        assert uow.audit.entries == [
            (
                MILA,
                CommentAdded(
                    ticket_id=TICKET_ID,
                    occurred_at=LATER,
                    comment_id=comment.id,
                    author_id=MILA,
                    visibility=Visibility.PUBLIC,
                ),
            )
        ]

    async def test_saves_the_status_change_a_requester_reply_causes(
        self, service: CommentService, uow: FakeUnitOfWork
    ) -> None:
        await seed(uow, TicketStatus.WAITING_ON_CUSTOMER)

        await service.add_comment(
            CUSTOMER,
            TICKET_ID,
            body=CommentBody("I'm the Owner and it's still greyed out. Screenshot attached."),
            visibility=Visibility.PUBLIC,
        )

        ticket = await uow.tickets.get(TICKET_ID)
        assert ticket is not None
        assert ticket.status is TicketStatus.IN_PROGRESS
        assert ticket.updated_at == LATER
        assert [type(event) for _, event in uow.audit.entries] == [
            CommentAdded,
            TicketStatusChanged,
        ]

    async def test_customer_cannot_comment_on_someone_elses_ticket(
        self, service: CommentService, uow: FakeUnitOfWork
    ) -> None:
        await seed(uow, TicketStatus.OPEN)

        with pytest.raises(TicketNotFoundError):
            await service.add_comment(
                Actor(OTHER_CUSTOMER, Role.CUSTOMER),
                TICKET_ID,
                body=CommentBody("Same problem here."),
                visibility=Visibility.PUBLIC,
            )

        assert uow.comments.rows == []

    @pytest.mark.parametrize(
        ("actor", "status", "error"),
        [
            (CUSTOMER, TicketStatus.OPEN, InternalNoteNotAllowedError),
            (AGENT_MILA, TicketStatus.CLOSED, TicketClosedError),
        ],
        ids=["customer-internal-note", "closed-ticket"],
    )
    async def test_rule_violation_stores_nothing(
        self,
        service: CommentService,
        uow: FakeUnitOfWork,
        actor: Actor,
        status: TicketStatus,
        error: type[Exception],
    ) -> None:
        await seed(uow, status)

        with pytest.raises(error):
            await service.add_comment(
                actor,
                TICKET_ID,
                body=CommentBody("Escalating to billing."),
                visibility=Visibility.INTERNAL,
            )

        assert uow.comments.rows == []
        assert uow.audit.entries == []
        assert uow.commits == 0


class TestListComments:
    @pytest.fixture
    async def thread(self, service: CommentService, uow: FakeUnitOfWork, clock: FixedClock) -> None:
        await seed(uow, TicketStatus.IN_PROGRESS)
        for actor, text, visibility in [
            (AGENT_MILA, "Can you confirm your role on the workspace?", Visibility.PUBLIC),
            (AGENT_MILA, "Probably the seat limit on their plan.", Visibility.INTERNAL),
            (CUSTOMER, "I'm the Owner.", Visibility.PUBLIC),
        ]:
            clock.advance(timedelta(minutes=5))
            await service.add_comment(
                actor, TICKET_ID, body=CommentBody(text), visibility=visibility
            )

    @pytest.mark.usefixtures("thread")
    async def test_staff_see_internal_notes_in_order(self, service: CommentService) -> None:
        comments = await service.list_comments(AGENT_MILA, TICKET_ID)

        assert [str(comment.body) for comment in comments] == [
            "Can you confirm your role on the workspace?",
            "Probably the seat limit on their plan.",
            "I'm the Owner.",
        ]

    @pytest.mark.usefixtures("thread")
    async def test_requester_never_sees_internal_notes(self, service: CommentService) -> None:
        comments = await service.list_comments(CUSTOMER, TICKET_ID)

        assert all(comment.visibility is Visibility.PUBLIC for comment in comments)
        assert len(comments) == 2

    @pytest.mark.usefixtures("thread")
    async def test_other_customers_get_not_found(self, service: CommentService) -> None:
        with pytest.raises(TicketNotFoundError):
            await service.list_comments(Actor(OTHER_CUSTOMER, Role.CUSTOMER), TICKET_ID)
