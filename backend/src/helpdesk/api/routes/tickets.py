from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from fastapi import APIRouter, Header, Query, status
from pydantic import BaseModel, ConfigDict, Field

from helpdesk.api.container import Container
from helpdesk.api.cursors import decode_cursor, encode_cursor
from helpdesk.api.dependencies import ContainerDep, CurrentActor
from helpdesk.api.errors import error_responses
from helpdesk.api.schemas import PersonResponse, Request
from helpdesk.application.actor import Actor
from helpdesk.application.tickets.queries import (
    MAX_PAGE_SIZE,
    UNASSIGNED,
    TicketQuery,
    TicketSort,
)
from helpdesk.domain.errors import InvalidValueError
from helpdesk.domain.ids import TicketId, UserId
from helpdesk.domain.tickets.comment import Comment, CommentBody, Visibility
from helpdesk.domain.tickets.status import TicketStatus
from helpdesk.domain.tickets.ticket import Ticket
from helpdesk.domain.tickets.values import Description, Priority, Subject
from helpdesk.domain.users.user import User

router = APIRouter(
    prefix="/tickets", tags=["tickets"], responses=error_responses(401, 403, 404, 409, 422)
)

IdempotencyKey = Annotated[
    str | None,
    Header(
        alias="Idempotency-Key",
        min_length=1,
        max_length=255,
        description="Retrying with the same key returns the ticket from the first attempt.",
    ),
]


class OpenTicketRequest(Request):
    subject: str
    description: str
    priority: Priority = Priority.NORMAL


class StatusChangeRequest(Request):
    status: TicketStatus


class PriorityChangeRequest(Request):
    priority: Priority


class AssigneeChangeRequest(Request):
    assignee_id: UUID


class AddCommentRequest(Request):
    body: str
    visibility: Visibility = Visibility.PUBLIC


class TicketResponse(BaseModel):
    id: UUID
    requester: PersonResponse
    subject: str
    description: str
    priority: Priority
    status: TicketStatus
    assignee: PersonResponse | None
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None
    closed_at: datetime | None
    first_responded_at: datetime | None
    # Set once nobody on staff replied within the first-response target for the priority.
    sla_breached_at: datetime | None

    @classmethod
    def from_ticket(cls, ticket: Ticket, people: Mapping[UserId, User]) -> Self:
        assignee = people[ticket.assignee_id] if ticket.assignee_id else None
        return cls(
            id=ticket.id,
            requester=PersonResponse.from_user(people[ticket.requester_id]),
            subject=str(ticket.subject),
            description=str(ticket.description),
            priority=ticket.priority,
            status=ticket.status,
            assignee=PersonResponse.from_user(assignee) if assignee else None,
            created_at=ticket.created_at,
            updated_at=ticket.updated_at,
            resolved_at=ticket.resolved_at,
            closed_at=ticket.closed_at,
            first_responded_at=ticket.first_responded_at,
            sla_breached_at=ticket.sla_breached_at,
        )


class CommentResponse(BaseModel):
    id: UUID
    ticket_id: UUID
    author: PersonResponse
    body: str
    visibility: Visibility
    created_at: datetime

    @classmethod
    def from_comment(cls, comment: Comment, people: Mapping[UserId, User]) -> Self:
        return cls(
            id=comment.id,
            ticket_id=comment.ticket_id,
            author=PersonResponse.from_user(people[comment.author_id]),
            body=str(comment.body),
            visibility=comment.visibility,
            created_at=comment.created_at,
        )


class TicketListResponse(BaseModel):
    items: list[TicketResponse]
    # Pass back as `cursor` for the next page; null on the last page.
    next_cursor: str | None


class TicketListParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: list[TicketStatus] = []
    priority: list[Priority] = []
    assignee: str | None = Field(None, description="`me`, `unassigned` or a user id")
    requester: UUID | None = Field(None, description="Ignored for customers")
    sort: TicketSort = TicketSort.NEWEST
    limit: int = Field(25, ge=1, le=MAX_PAGE_SIZE)
    cursor: str | None = Field(None, description="`next_cursor` from the previous page")

    def to_query(self, actor: Actor) -> TicketQuery:
        return TicketQuery(
            statuses=frozenset(self.status),
            priorities=frozenset(self.priority),
            requester_id=UserId(self.requester) if self.requester else None,
            assignee=_assignee_filter(self.assignee, actor),
            sort=self.sort,
            after=decode_cursor(self.sort, self.cursor) if self.cursor else None,
            limit=self.limit,
        )


@router.get("")
async def list_tickets(
    params: Annotated[TicketListParams, Query()], actor: CurrentActor, container: ContainerDep
) -> TicketListResponse:
    page = await container.tickets().list_tickets(actor, params.to_query(actor))
    return TicketListResponse(
        items=await _present_tickets(container, page.tickets),
        next_cursor=encode_cursor(params.sort, page.next_cursor) if page.next_cursor else None,
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def open_ticket(
    body: OpenTicketRequest,
    actor: CurrentActor,
    container: ContainerDep,
    idempotency_key: IdempotencyKey = None,
) -> TicketResponse:
    ticket = await container.tickets().open_ticket(
        actor,
        subject=Subject(body.subject),
        description=Description(body.description),
        priority=body.priority,
        idempotency_key=idempotency_key,
    )
    return await _present_ticket(container, ticket)


@router.get("/{ticket_id}")
async def get_ticket(
    ticket_id: UUID, actor: CurrentActor, container: ContainerDep
) -> TicketResponse:
    ticket = await container.tickets().get_ticket(actor, TicketId(ticket_id))
    return await _present_ticket(container, ticket)


@router.put("/{ticket_id}/status")
async def change_status(
    ticket_id: UUID, body: StatusChangeRequest, actor: CurrentActor, container: ContainerDep
) -> TicketResponse:
    ticket = await container.tickets().change_status(actor, TicketId(ticket_id), body.status)
    return await _present_ticket(container, ticket)


@router.put("/{ticket_id}/priority")
async def change_priority(
    ticket_id: UUID, body: PriorityChangeRequest, actor: CurrentActor, container: ContainerDep
) -> TicketResponse:
    ticket = await container.tickets().change_priority(actor, TicketId(ticket_id), body.priority)
    return await _present_ticket(container, ticket)


@router.put("/{ticket_id}/assignee")
async def assign(
    ticket_id: UUID, body: AssigneeChangeRequest, actor: CurrentActor, container: ContainerDep
) -> TicketResponse:
    ticket = await container.tickets().assign(actor, TicketId(ticket_id), UserId(body.assignee_id))
    return await _present_ticket(container, ticket)


@router.delete("/{ticket_id}/assignee")
async def unassign(ticket_id: UUID, actor: CurrentActor, container: ContainerDep) -> TicketResponse:
    ticket = await container.tickets().unassign(actor, TicketId(ticket_id))
    return await _present_ticket(container, ticket)


@router.post("/{ticket_id}/take")
async def take(ticket_id: UUID, actor: CurrentActor, container: ContainerDep) -> TicketResponse:
    ticket = await container.tickets().take(actor, TicketId(ticket_id))
    return await _present_ticket(container, ticket)


@router.get("/{ticket_id}/comments")
async def list_comments(
    ticket_id: UUID, actor: CurrentActor, container: ContainerDep
) -> list[CommentResponse]:
    comments = await container.comments().list_comments(actor, TicketId(ticket_id))
    people = await container.people().find(comment.author_id for comment in comments)
    return [CommentResponse.from_comment(comment, people) for comment in comments]


@router.post("/{ticket_id}/comments", status_code=status.HTTP_201_CREATED)
async def add_comment(
    ticket_id: UUID, body: AddCommentRequest, actor: CurrentActor, container: ContainerDep
) -> CommentResponse:
    comment = await container.comments().add_comment(
        actor, TicketId(ticket_id), body=CommentBody(body.body), visibility=body.visibility
    )
    people = await container.people().find([comment.author_id])
    return CommentResponse.from_comment(comment, people)


async def _present_ticket(container: Container, ticket: Ticket) -> TicketResponse:
    [presented] = await _present_tickets(container, [ticket])
    return presented


async def _present_tickets(container: Container, tickets: Sequence[Ticket]) -> list[TicketResponse]:
    # One lookup for everyone on the page rather than one per ticket.
    people = await container.people().find(_people_on(tickets))
    return [TicketResponse.from_ticket(ticket, people) for ticket in tickets]


def _people_on(tickets: Iterable[Ticket]) -> Iterable[UserId]:
    for ticket in tickets:
        yield ticket.requester_id
        if ticket.assignee_id:
            yield ticket.assignee_id


def _assignee_filter(value: str | None, actor: Actor) -> UserId | Literal["unassigned"] | None:
    if value is None:
        return None
    if value == "me":
        return actor.user_id
    if value == UNASSIGNED:
        return UNASSIGNED
    try:
        return UserId(UUID(value))
    except ValueError as error:
        raise InvalidValueError("assignee must be 'me', 'unassigned' or a user id") from error
