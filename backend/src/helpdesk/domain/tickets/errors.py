from helpdesk.domain.errors import DomainError
from helpdesk.domain.ids import TicketId
from helpdesk.domain.tickets.status import TicketStatus


class InvalidStatusTransitionError(DomainError):
    def __init__(self, current: TicketStatus, target: TicketStatus) -> None:
        super().__init__(f"cannot move a ticket from {current} to {target}")
        self.current = current
        self.target = target


class AssigneeRequiredError(DomainError):
    def __init__(self, status: TicketStatus) -> None:
        super().__init__(f"a ticket that is {status} must have an assignee")
        self.status = status


class TicketClosedError(DomainError):
    def __init__(self, ticket_id: TicketId) -> None:
        super().__init__(f"ticket {ticket_id} is closed and can no longer change")
        self.ticket_id = ticket_id


class InternalNoteNotAllowedError(DomainError):
    def __init__(self) -> None:
        super().__init__("only agents and admins can write internal notes")


class NotTicketRequesterError(DomainError):
    def __init__(self, ticket_id: TicketId) -> None:
        super().__init__(f"customers can only comment on their own tickets, not {ticket_id}")
        self.ticket_id = ticket_id
