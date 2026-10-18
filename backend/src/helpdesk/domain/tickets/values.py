from dataclasses import dataclass
from enum import StrEnum

from helpdesk.domain.errors import InvalidValueError
from helpdesk.domain.text import ensure_text

SUBJECT_MAX_LENGTH = 200
DESCRIPTION_MAX_LENGTH = 10_000


class Priority(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


@dataclass(frozen=True, slots=True)
class Subject:
    value: str

    def __post_init__(self) -> None:
        ensure_text(self.value, field="subject", max_length=SUBJECT_MAX_LENGTH)
        # Subjects are rendered as one row in the agent queue.
        if "\n" in self.value or "\r" in self.value:
            raise InvalidValueError("subject must be a single line")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class Description:
    value: str

    def __post_init__(self) -> None:
        ensure_text(self.value, field="description", max_length=DESCRIPTION_MAX_LENGTH)

    def __str__(self) -> str:
        return self.value
