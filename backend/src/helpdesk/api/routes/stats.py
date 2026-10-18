from datetime import date
from typing import Annotated, Self

from fastapi import APIRouter, Query
from pydantic import BaseModel

from helpdesk.api.dependencies import ContainerDep, CurrentActor
from helpdesk.api.errors import error_responses
from helpdesk.application.tickets.statistics import MAX_DAYS, TicketOverview
from helpdesk.domain.tickets.status import TicketStatus

router = APIRouter(prefix="/stats", tags=["stats"], responses=error_responses(401, 403, 422))


class DayCountResponse(BaseModel):
    day: date
    opened: int
    resolved: int


class TicketStatsResponse(BaseModel):
    # Every status is present, with 0 where there are no tickets.
    by_status: dict[TicketStatus, int]
    unassigned: int
    awaiting_first_response: int
    first_response_overdue: int
    median_first_response_seconds: float | None
    days: list[DayCountResponse]

    @classmethod
    def from_overview(cls, overview: TicketOverview) -> Self:
        totals = overview.totals
        median = totals.median_first_response
        return cls(
            by_status={status: totals.by_status.get(status, 0) for status in TicketStatus},
            unassigned=totals.unassigned,
            awaiting_first_response=totals.awaiting_first_response,
            first_response_overdue=totals.first_response_overdue,
            median_first_response_seconds=median.total_seconds() if median else None,
            days=[
                DayCountResponse(day=day.day, opened=day.opened, resolved=day.resolved)
                for day in overview.days
            ],
        )


@router.get("/tickets")
async def ticket_stats(
    actor: CurrentActor,
    container: ContainerDep,
    days: Annotated[int, Query(ge=1, le=MAX_DAYS, description="How many days back to chart")] = 14,
) -> TicketStatsResponse:
    overview = await container.statistics().overview(actor, days=days)
    return TicketStatsResponse.from_overview(overview)
