from __future__ import annotations

from typing import TYPE_CHECKING

from helpdesk.domain.tickets.comment import Comment, Visibility
from helpdesk.domain.tickets.errors import (
    AssigneeRequiredError,
    InternalNoteNotAllowedError,
    InvalidStatusTransitionError,
    NotTicketRequesterError,
    TicketClosedError,
)
from helpdesk.domain.tickets.events import (
    CommentAdded,
    TicketAssigneeChanged,
    TicketEvent,
    TicketOpened,
    TicketPriorityChanged,
    TicketStatusChanged,
)
from helpdesk.domain.tickets.status import TicketStatus

if TYPE_CHECKING:
    from datetime import datetime

    from helpdesk.domain.ids import CommentId, TicketId, UserId
    from helpdesk.domain.roles import Role
    from helpdesk.domain.tickets.comment import CommentBody
    from helpdesk.domain.tickets.values import Description, Priority, Subject

# A reply from the requester means the ticket needs attention again: while we wait on them it
# goes back to the assignee, and after resolution it means the problem wasn't actually solved.
_STATUS_AFTER_REQUESTER_REPLY = {
    TicketStatus.WAITING_ON_CUSTOMER: TicketStatus.IN_PROGRESS,
    TicketStatus.RESOLVED: TicketStatus.OPEN,
}


class Ticket:
    # The constructor rebuilds a ticket in any state (repositories use it); new tickets go
    # through open() so they start in the right state and record TicketOpened.
    def __init__(
        self,
        *,
        ticket_id: TicketId,
        requester_id: UserId,
        subject: Subject,
        description: Description,
        priority: Priority,
        status: TicketStatus,
        assignee_id: UserId | None,
        created_at: datetime,
        updated_at: datetime,
        resolved_at: datetime | None,
        closed_at: datetime | None,
    ) -> None:
        if status.requires_assignee and assignee_id is None:
            raise AssigneeRequiredError(status)
        self._id = ticket_id
        self._requester_id = requester_id
        self._subject = subject
        self._description = description
        self._priority = priority
        self._status = status
        self._assignee_id = assignee_id
        self._created_at = created_at
        self._updated_at = updated_at
        self._resolved_at = resolved_at
        self._closed_at = closed_at
        self._events: list[TicketEvent] = []

    @classmethod
    def open(
        cls,
        *,
        ticket_id: TicketId,
        requester_id: UserId,
        subject: Subject,
        description: Description,
        priority: Priority,
        at: datetime,
    ) -> Ticket:
        ticket = cls(
            ticket_id=ticket_id,
            requester_id=requester_id,
            subject=subject,
            description=description,
            priority=priority,
            status=TicketStatus.OPEN,
            assignee_id=None,
            created_at=at,
            updated_at=at,
            resolved_at=None,
            closed_at=None,
        )
        ticket._events.append(
            TicketOpened(
                ticket_id=ticket_id,
                occurred_at=at,
                requester_id=requester_id,
                priority=priority,
            )
        )
        return ticket

    @property
    def id(self) -> TicketId:
        return self._id

    @property
    def requester_id(self) -> UserId:
        return self._requester_id

    @property
    def subject(self) -> Subject:
        return self._subject

    @property
    def description(self) -> Description:
        return self._description

    @property
    def priority(self) -> Priority:
        return self._priority

    @property
    def status(self) -> TicketStatus:
        return self._status

    @property
    def assignee_id(self) -> UserId | None:
        return self._assignee_id

    @property
    def created_at(self) -> datetime:
        return self._created_at

    @property
    def updated_at(self) -> datetime:
        return self._updated_at

    @property
    def resolved_at(self) -> datetime | None:
        return self._resolved_at

    @property
    def closed_at(self) -> datetime | None:
        return self._closed_at

    def change_status(self, target: TicketStatus, *, at: datetime) -> None:
        self._ensure_not_closed()
        if not self._status.can_transition_to(target):
            raise InvalidStatusTransitionError(self._status, target)
        if target.requires_assignee and self._assignee_id is None:
            raise AssigneeRequiredError(target)
        self._move_to(target, at)

    def assign(self, agent_id: UserId, *, at: datetime) -> None:
        # Whether agent_id belongs to an agent is checked by the caller: roles live outside
        # the ticket aggregate.
        self._ensure_not_closed()
        if agent_id == self._assignee_id:
            return
        self._set_assignee(agent_id, at)

    def unassign(self, *, at: datetime) -> None:
        self._ensure_not_closed()
        if self._assignee_id is None:
            return
        if self._status.requires_assignee:
            raise AssigneeRequiredError(self._status)
        self._set_assignee(None, at)

    def change_priority(self, priority: Priority, *, at: datetime) -> None:
        self._ensure_not_closed()
        if priority is self._priority:
            return
        previous = self._priority
        self._priority = priority
        self._updated_at = at
        self._events.append(
            TicketPriorityChanged(
                ticket_id=self._id, occurred_at=at, previous=previous, current=priority
            )
        )

    def add_comment(
        self,
        *,
        comment_id: CommentId,
        author_id: UserId,
        author_role: Role,
        body: CommentBody,
        visibility: Visibility,
        at: datetime,
    ) -> Comment:
        self._ensure_not_closed()
        if visibility is Visibility.INTERNAL and not author_role.is_staff:
            raise InternalNoteNotAllowedError
        if not author_role.is_staff and author_id != self._requester_id:
            raise NotTicketRequesterError(self._id)

        comment = Comment(
            id=comment_id,
            ticket_id=self._id,
            author_id=author_id,
            body=body,
            visibility=visibility,
            created_at=at,
        )
        self._updated_at = at
        self._events.append(
            CommentAdded(
                ticket_id=self._id,
                occurred_at=at,
                comment_id=comment_id,
                author_id=author_id,
                visibility=visibility,
            )
        )
        if author_id == self._requester_id and visibility is Visibility.PUBLIC:
            follow_up = _STATUS_AFTER_REQUESTER_REPLY.get(self._status)
            if follow_up is not None:
                self._move_to(follow_up, at)
        return comment

    def pull_events(self) -> list[TicketEvent]:
        events, self._events = self._events, []
        return events

    def _move_to(self, target: TicketStatus, at: datetime) -> None:
        previous = self._status
        self._status = target
        if target is TicketStatus.RESOLVED:
            self._resolved_at = at
        elif target is TicketStatus.OPEN:
            self._resolved_at = None
        elif target is TicketStatus.CLOSED:
            self._closed_at = at
        self._updated_at = at
        self._events.append(
            TicketStatusChanged(
                ticket_id=self._id, occurred_at=at, previous=previous, current=target
            )
        )

    def _set_assignee(self, assignee_id: UserId | None, at: datetime) -> None:
        previous = self._assignee_id
        self._assignee_id = assignee_id
        self._updated_at = at
        self._events.append(
            TicketAssigneeChanged(
                ticket_id=self._id, occurred_at=at, previous=previous, current=assignee_id
            )
        )

    def _ensure_not_closed(self) -> None:
        if self._status is TicketStatus.CLOSED:
            raise TicketClosedError(self._id)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Ticket):
            return NotImplemented
        return self._id == other._id

    def __hash__(self) -> int:
        return hash(self._id)

    def __repr__(self) -> str:
        return f"Ticket(id={self._id}, status={self._status}, assignee_id={self._assignee_id})"
