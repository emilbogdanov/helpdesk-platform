from dataclasses import dataclass
from enum import StrEnum

from helpdesk.domain.errors import InvalidValueError

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
        if not self.value.strip():
            raise InvalidValueError("subject must not be blank")
        if len(self.value) > SUBJECT_MAX_LENGTH:
            raise InvalidValueError(f"subject must be at most {SUBJECT_MAX_LENGTH} characters")
        # Subjects are rendered as one row in the agent queue.
        if "\n" in self.value or "\r" in self.value:
            raise InvalidValueError("subject must be a single line")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class Description:
    value: str

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise InvalidValueError("description must not be blank")
        if len(self.value) > DESCRIPTION_MAX_LENGTH:
            raise InvalidValueError(
                f"description must be at most {DESCRIPTION_MAX_LENGTH} characters"
            )

    def __str__(self) -> str:
        return self.value
