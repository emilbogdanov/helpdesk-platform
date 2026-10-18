import logging
from collections.abc import Callable
from datetime import timedelta

from helpdesk.application.errors import ConcurrentUpdateError
from helpdesk.application.ports import Clock, UnitOfWork
from helpdesk.domain.ids import TicketId
from helpdesk.domain.tickets.sla import FirstResponseTargets
from helpdesk.domain.tickets.ticket import Ticket

logger = logging.getLogger(__name__)


# Work nobody asks for: the worker runs these on a schedule. Each pass handles a bounded batch
# and each ticket gets its own short transaction, so one ticket being edited at the same moment
# costs a retry on the next pass instead of rolling back everything else.
class TicketUpkeep:
    def __init__(
        self,
        uow: UnitOfWork,
        clock: Clock,
        *,
        targets: FirstResponseTargets,
        close_resolved_after: timedelta,
        batch_size: int = 200,
    ) -> None:
        self._uow = uow
        self._clock = clock
        self._targets = targets
        self._close_resolved_after = close_resolved_after
        self._batch_size = batch_size

    async def flag_overdue_first_responses(self) -> int:
        now = self._clock.now()
        opened_before = {
            priority: now - target for priority, target in self._targets.by_priority.items()
        }
        async with self._uow as uow:
            candidates = await uow.tickets.find_awaiting_first_response(
                opened_before, limit=self._batch_size
            )
        return await self._apply_each(
            candidates,
            lambda ticket: ticket.flag_overdue_first_response(self._targets, at=now),
        )

    async def close_resolved_tickets(self) -> int:
        now = self._clock.now()
        cutoff = now - self._close_resolved_after
        async with self._uow as uow:
            candidates = await uow.tickets.find_resolved_before(cutoff, limit=self._batch_size)
        return await self._apply_each(
            candidates, lambda ticket: ticket.close_if_resolved_before(cutoff, at=now)
        )

    async def _apply_each(
        self, ticket_ids: list[TicketId], change: Callable[[Ticket], None]
    ) -> int:
        changed = 0
        for ticket_id in ticket_ids:
            try:
                if await self._apply(ticket_id, change):
                    changed += 1
            except ConcurrentUpdateError:
                logger.info("ticket %s changed while being processed; next pass retries", ticket_id)
        return changed

    async def _apply(self, ticket_id: TicketId, change: Callable[[Ticket], None]) -> bool:
        async with self._uow as uow:
            ticket = await uow.tickets.get(ticket_id)
            if ticket is None:
                return False
            change(ticket)
            events = ticket.pull_events()
            if not events:
                return False
            await uow.tickets.update(ticket)
            await uow.audit.record(None, events)
            await uow.commit()
            return True
