from uuid import UUID

import pytest

from helpdesk.domain.errors import InvalidValueError
from helpdesk.domain.ids import CommentId, UserId
from helpdesk.domain.roles import Role
from helpdesk.domain.tickets.comment import (
    COMMENT_BODY_MAX_LENGTH,
    Comment,
    CommentBody,
    Visibility,
)
from helpdesk.domain.tickets.errors import (
    InternalNoteNotAllowedError,
    NotTicketRequesterError,
    TicketClosedError,
)
from helpdesk.domain.tickets.events import CommentAdded, TicketStatusChanged
from helpdesk.domain.tickets.status import TicketStatus
from helpdesk.domain.tickets.ticket import Ticket
from tests.unit.domain.tickets.builders import (
    LATER,
    MILA,
    OPENED_AT,
    OTHER_CUSTOMER,
    REQUESTER,
    TICKET_ID,
    ticket_in,
)

COMMENT_ID = CommentId(UUID("3f8b2a6d-9c41-4e07-b5d2-8a1c6e9f0b34"))


def comment_on(
    ticket: Ticket,
    *,
    author_id: UserId,
    author_role: Role,
    visibility: Visibility = Visibility.PUBLIC,
    text: str = "Thanks, that fixed the PDF. The rate shows 20% now.",
) -> Comment:
    return ticket.add_comment(
        comment_id=COMMENT_ID,
        author_id=author_id,
        author_role=author_role,
        body=CommentBody(text),
        visibility=visibility,
        at=LATER,
    )


def reply_from_requester(ticket: Ticket) -> Comment:
    return comment_on(ticket, author_id=REQUESTER, author_role=Role.CUSTOMER)


class TestCommentBody:
    def test_keeps_multiline_text(self) -> None:
        text = "Cleared the cache and logged in again.\n\nStill seeing 19% on the invoice."

        assert str(CommentBody(text)) == text

    @pytest.mark.parametrize("value", ["", "  ", "\n"])
    def test_rejects_blank(self, value: str) -> None:
        with pytest.raises(InvalidValueError, match="comment must not be blank"):
            CommentBody(value)

    def test_rejects_over_maximum_length(self) -> None:
        with pytest.raises(InvalidValueError, match="at most"):
            CommentBody("a" * (COMMENT_BODY_MAX_LENGTH + 1))


class TestAddComment:
    def test_returns_the_comment_attached_to_the_ticket(self) -> None:
        ticket = ticket_in(TicketStatus.IN_PROGRESS)

        comment = comment_on(
            ticket,
            author_id=MILA,
            author_role=Role.AGENT,
            text="We pushed a fix for the VAT rate. Could you download the invoice again?",
        )

        assert comment == Comment(
            id=COMMENT_ID,
            ticket_id=TICKET_ID,
            author_id=MILA,
            body=CommentBody(
                "We pushed a fix for the VAT rate. Could you download the invoice again?"
            ),
            visibility=Visibility.PUBLIC,
            created_at=LATER,
        )

    def test_records_comment_added_and_touches_the_ticket(self) -> None:
        ticket = ticket_in(TicketStatus.IN_PROGRESS)

        comment_on(ticket, author_id=MILA, author_role=Role.AGENT, visibility=Visibility.INTERNAL)

        assert ticket.updated_at == LATER
        assert ticket.pull_events() == [
            CommentAdded(
                ticket_id=TICKET_ID,
                occurred_at=LATER,
                comment_id=COMMENT_ID,
                author_id=MILA,
                visibility=Visibility.INTERNAL,
            )
        ]

    @pytest.mark.parametrize("role", [Role.AGENT, Role.ADMIN])
    def test_staff_can_write_internal_notes(self, role: Role) -> None:
        ticket = ticket_in(TicketStatus.OPEN)

        comment = comment_on(
            ticket, author_id=MILA, author_role=role, visibility=Visibility.INTERNAL
        )

        assert comment.visibility is Visibility.INTERNAL

    def test_staff_can_reply_on_tickets_they_did_not_open(self) -> None:
        ticket = ticket_in(TicketStatus.OPEN)

        comment = comment_on(ticket, author_id=MILA, author_role=Role.AGENT)

        assert comment.author_id == MILA

    def test_customer_cannot_write_internal_notes(self) -> None:
        ticket = ticket_in(TicketStatus.IN_PROGRESS)

        with pytest.raises(InternalNoteNotAllowedError):
            comment_on(
                ticket,
                author_id=REQUESTER,
                author_role=Role.CUSTOMER,
                visibility=Visibility.INTERNAL,
            )

        assert ticket.updated_at == OPENED_AT
        assert ticket.pull_events() == []

    def test_customer_cannot_comment_on_someone_elses_ticket(self) -> None:
        ticket = ticket_in(TicketStatus.IN_PROGRESS)

        with pytest.raises(NotTicketRequesterError) as excinfo:
            comment_on(ticket, author_id=OTHER_CUSTOMER, author_role=Role.CUSTOMER)

        assert excinfo.value.ticket_id == TICKET_ID
        assert ticket.pull_events() == []

    @pytest.mark.parametrize(
        ("author_id", "role"), [(REQUESTER, Role.CUSTOMER), (MILA, Role.AGENT)]
    )
    def test_closed_ticket_takes_no_comments(self, author_id: UserId, role: Role) -> None:
        ticket = ticket_in(TicketStatus.CLOSED)

        with pytest.raises(TicketClosedError):
            comment_on(ticket, author_id=author_id, author_role=role)

        assert ticket.pull_events() == []


class TestRequesterReply:
    def test_reply_while_waiting_hands_the_ticket_back_to_the_assignee(self) -> None:
        ticket = ticket_in(TicketStatus.WAITING_ON_CUSTOMER)

        reply_from_requester(ticket)

        assert ticket.status is TicketStatus.IN_PROGRESS
        assert ticket.assignee_id == MILA
        assert ticket.pull_events() == [
            CommentAdded(
                ticket_id=TICKET_ID,
                occurred_at=LATER,
                comment_id=COMMENT_ID,
                author_id=REQUESTER,
                visibility=Visibility.PUBLIC,
            ),
            TicketStatusChanged(
                ticket_id=TICKET_ID,
                occurred_at=LATER,
                previous=TicketStatus.WAITING_ON_CUSTOMER,
                current=TicketStatus.IN_PROGRESS,
            ),
        ]

    def test_reply_after_resolution_reopens_the_ticket(self) -> None:
        ticket = ticket_in(TicketStatus.RESOLVED)

        reply_from_requester(ticket)

        assert ticket.status is TicketStatus.OPEN
        assert ticket.resolved_at is None
        assert ticket.assignee_id == MILA

    @pytest.mark.parametrize("status", [TicketStatus.OPEN, TicketStatus.IN_PROGRESS])
    def test_reply_on_an_active_ticket_keeps_its_status(self, status: TicketStatus) -> None:
        ticket = ticket_in(status)

        reply_from_requester(ticket)

        assert ticket.status is status
        assert [type(event) for event in ticket.pull_events()] == [CommentAdded]

    @pytest.mark.parametrize("visibility", [Visibility.PUBLIC, Visibility.INTERNAL])
    def test_staff_comments_do_not_resume_a_waiting_ticket(self, visibility: Visibility) -> None:
        ticket = ticket_in(TicketStatus.WAITING_ON_CUSTOMER)

        comment_on(ticket, author_id=MILA, author_role=Role.AGENT, visibility=visibility)

        assert ticket.status is TicketStatus.WAITING_ON_CUSTOMER

    def test_internal_note_from_a_staff_requester_does_not_resume_the_ticket(self) -> None:
        # Agents can open tickets for themselves; their private notes are not a reply.
        ticket = ticket_in(TicketStatus.WAITING_ON_CUSTOMER)

        comment_on(
            ticket, author_id=REQUESTER, author_role=Role.AGENT, visibility=Visibility.INTERNAL
        )

        assert ticket.status is TicketStatus.WAITING_ON_CUSTOMER
