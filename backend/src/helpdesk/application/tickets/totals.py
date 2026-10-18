from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, timedelta

from helpdesk.domain.tickets.status import TicketStatus


# What the repository counts for the dashboard. Days are UTC calendar days.
@dataclass(frozen=True, slots=True, kw_only=True)
class TicketTotals:
    by_status: Mapping[TicketStatus, int]
    # Open, in progress or waiting, and nobody has taken them.
    unassigned: int
    # Open, in progress or waiting, and no public reply from staff yet.
    awaiting_first_response: int
    # The part of those the worker has already flagged as past their target.
    first_response_overdue: int
    # Over tickets opened since the window start that have had a first reply.
    median_first_response: timedelta | None
    opened_by_day: Mapping[date, int]
    resolved_by_day: Mapping[date, int]
