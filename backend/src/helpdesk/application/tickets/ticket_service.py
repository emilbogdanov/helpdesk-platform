from collections.abc import Callable
from datetime import datetime
from uuid import uuid4

from helpdesk.application.actor import Actor
from helpdesk.application.errors import IdempotencyKeyReusedError
from helpdesk.application.ports import Clock, UnitOfWork
from helpdesk.application.tickets.access import load_visible_ticket, require_staff
from helpdesk.domain.ids import TicketId
from helpdesk.domain.tickets.status import TicketStatus
from helpdesk.domain.tickets.ticket import Ticket
from helpdesk.domain.tickets.values import Description, Priority, Subject


class TicketService:
    def __init__(self, uow: UnitOfWork, clock: Clock) -> None:
        self._uow = uow
        self._clock = clock

    async def open_ticket(
        self,
        actor: Actor,
        *,
        subject: Subject,
        description: Description,
        priority: Priority,
        idempotency_key: str | None = None,
    ) -> Ticket:
        async with self._uow as uow:
            if idempotency_key is not None:
                existing = await uow.tickets.find_by_idempotency_key(actor.user_id, idempotency_key)
                if existing is not None:
                    # A retry must carry the same request; anything else is a client bug that
                    # would otherwise silently return the wrong ticket.
                    if (existing.subject, existing.description, existing.priority) != (
                        subject,
                        description,
                        priority,
                    ):
                        raise IdempotencyKeyReusedError(idempotency_key)
                    return existing

            ticket = Ticket.open(
                ticket_id=TicketId(uuid4()),
                requester_id=actor.user_id,
                subject=subject,
                description=description,
                priority=priority,
                at=self._clock.now(),
            )
            await uow.tickets.add(ticket, idempotency_key=idempotency_key)
            await uow.audit.record(actor.user_id, ticket.pull_events())
            await uow.commit()
        return ticket

    async def get_ticket(self, actor: Actor, ticket_id: TicketId) -> Ticket:
        async with self._uow as uow:
            return await load_visible_ticket(uow.tickets, actor, ticket_id)

    async def change_status(
        self, actor: Actor, ticket_id: TicketId, status: TicketStatus
    ) -> Ticket:
        return await self._work_on(
            actor,
            ticket_id,
            action="change ticket status",
            change=lambda ticket, at: ticket.change_status(status, at=at),
        )

    async def take(self, actor: Actor, ticket_id: TicketId) -> Ticket:
        return await self._work_on(
            actor,
            ticket_id,
            action="take tickets",
            change=lambda ticket, at: ticket.assign(actor.user_id, at=at),
        )

    async def unassign(self, actor: Actor, ticket_id: TicketId) -> Ticket:
        return await self._work_on(
            actor,
            ticket_id,
            action="unassign tickets",
            change=lambda ticket, at: ticket.unassign(at=at),
        )

    async def change_priority(
        self, actor: Actor, ticket_id: TicketId, priority: Priority
    ) -> Ticket:
        return await self._work_on(
            actor,
            ticket_id,
            action="change ticket priority",
            change=lambda ticket, at: ticket.change_priority(priority, at=at),
        )

    async def _work_on(
        self,
        actor: Actor,
        ticket_id: TicketId,
        *,
        action: str,
        change: Callable[[Ticket, datetime], None],
    ) -> Ticket:
        require_staff(actor, action)
        async with self._uow as uow:
            ticket = await load_visible_ticket(uow.tickets, actor, ticket_id)
            change(ticket, self._clock.now())
            events = ticket.pull_events()
            if events:
                await uow.tickets.update(ticket)
                await uow.audit.record(actor.user_id, events)
                await uow.commit()
        return ticket
