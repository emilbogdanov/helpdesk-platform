from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta

from helpdesk.application.actor import Actor
from helpdesk.application.errors import AdminOnlyError
from helpdesk.application.ports import Clock, UnitOfWork
from helpdesk.application.tickets.totals import TicketTotals
from helpdesk.domain.errors import InvalidValueError
from helpdesk.domain.roles import Role

MAX_DAYS = 90


@dataclass(frozen=True, slots=True)
class DayCount:
    day: date
    opened: int
    resolved: int


@dataclass(frozen=True, slots=True)
class TicketOverview:
    totals: TicketTotals
    # Oldest first, one entry for every day in the window, quiet days included.
    days: list[DayCount]


class TicketStatistics:
    def __init__(self, uow: UnitOfWork, clock: Clock) -> None:
        self._uow = uow
        self._clock = clock

    async def overview(self, actor: Actor, *, days: int) -> TicketOverview:
        if actor.role is not Role.ADMIN:
            raise AdminOnlyError("see ticket statistics")
        if not 1 <= days <= MAX_DAYS:
            raise InvalidValueError(f"days must be 1 to {MAX_DAYS}")
        today = self._clock.now().astimezone(UTC).date()
        first_day = today - timedelta(days=days - 1)
        async with self._uow as uow:
            totals = await uow.tickets.totals(since=datetime.combine(first_day, time(), UTC))
        window = (first_day + timedelta(days=offset) for offset in range(days))
        return TicketOverview(
            totals=totals,
            days=[
                DayCount(day, totals.opened_by_day.get(day, 0), totals.resolved_by_day.get(day, 0))
                for day in window
            ],
        )
