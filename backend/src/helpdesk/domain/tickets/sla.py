from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta

from helpdesk.domain.errors import InvalidValueError
from helpdesk.domain.tickets.values import Priority


# How long a ticket may wait for its first public reply from staff, by priority. Measured in
# wall-clock time: there is no notion of business hours or holidays yet.
@dataclass(frozen=True, slots=True)
class FirstResponseTargets:
    by_priority: Mapping[Priority, timedelta]

    def __post_init__(self) -> None:
        if set(self.by_priority) != set(Priority):
            raise InvalidValueError("every priority needs a first-response target")

    def due_at(self, priority: Priority, opened_at: datetime) -> datetime:
        return opened_at + self.by_priority[priority]


DEFAULT_FIRST_RESPONSE_TARGETS = FirstResponseTargets(
    {
        Priority.URGENT: timedelta(hours=1),
        Priority.HIGH: timedelta(hours=4),
        Priority.NORMAL: timedelta(days=1),
        Priority.LOW: timedelta(days=3),
    }
)
