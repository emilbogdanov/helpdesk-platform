from helpdesk.domain.ids import TicketId
from helpdesk.domain.users.values import EmailAddress


class ApplicationError(Exception):
    pass


class TicketNotFoundError(ApplicationError):
    # Also raised when a customer asks for someone else's ticket, so ticket ids can't be probed.
    def __init__(self, ticket_id: TicketId) -> None:
        super().__init__(f"ticket {ticket_id} not found")
        self.ticket_id = ticket_id


class StaffOnlyError(ApplicationError):
    def __init__(self, action: str) -> None:
        super().__init__(f"only agents and admins can {action}")
        self.action = action


class IdempotencyKeyReusedError(ApplicationError):
    def __init__(self, key: str) -> None:
        super().__init__(f"idempotency key {key!r} was already used for a different ticket")
        self.key = key


class IdempotencyKeyConflictError(ApplicationError):
    # Raised by TicketRepository.add when another request stored the same key first.
    def __init__(self, key: str) -> None:
        super().__init__(f"idempotency key {key!r} is already taken")
        self.key = key


class ConcurrentUpdateError(ApplicationError):
    def __init__(self) -> None:
        super().__init__("the ticket was changed by someone else; reload it and try again")


class EmailTakenError(ApplicationError):
    def __init__(self, email: EmailAddress) -> None:
        super().__init__(f"an account with {email} already exists")
        self.email = email
