from helpdesk.application.actor import Actor
from helpdesk.application.errors import StaffOnlyError, TicketNotFoundError
from helpdesk.application.ports import TicketRepository
from helpdesk.domain.ids import TicketId
from helpdesk.domain.tickets.ticket import Ticket


async def load_visible_ticket(
    tickets: TicketRepository, actor: Actor, ticket_id: TicketId
) -> Ticket:
    ticket = await tickets.get(ticket_id)
    if ticket is None:
        raise TicketNotFoundError(ticket_id)
    if not actor.role.is_staff and ticket.requester_id != actor.user_id:
        raise TicketNotFoundError(ticket_id)
    return ticket


def require_staff(actor: Actor, action: str) -> None:
    if not actor.role.is_staff:
        raise StaffOnlyError(action)
