from dataclasses import dataclass, field

from helpdesk.domain.errors import InvalidValueError
from helpdesk.domain.text import ensure_text

EMAIL_MAX_LENGTH = 254
DISPLAY_NAME_MAX_LENGTH = 100
PASSWORD_MIN_LENGTH = 10
# Long enough for any passphrase; the cap stops megabyte-sized "passwords" reaching the hasher.
PASSWORD_MAX_LENGTH = 128


@dataclass(frozen=True, slots=True)
class EmailAddress:
    value: str

    def __post_init__(self) -> None:
        # Normalised once here so lookups, uniqueness and log-in all agree on one spelling.
        normalised = self.value.strip().lower()
        object.__setattr__(self, "value", normalised)
        if len(normalised) > EMAIL_MAX_LENGTH:
            raise InvalidValueError(f"email must be at most {EMAIL_MAX_LENGTH} characters")
        local, at, domain = normalised.rpartition("@")
        if not (at and local and "." in domain.strip(".")) or any(c.isspace() for c in normalised):
            raise InvalidValueError("email must look like name@example.com")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class DisplayName:
    value: str

    def __post_init__(self) -> None:
        ensure_text(self.value, field="display name", max_length=DISPLAY_NAME_MAX_LENGTH)
        if "\n" in self.value or "\r" in self.value:
            raise InvalidValueError("display name must be a single line")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class Password:
    value: str = field(repr=False)

    def __post_init__(self) -> None:
        if not PASSWORD_MIN_LENGTH <= len(self.value) <= PASSWORD_MAX_LENGTH:
            raise InvalidValueError(
                f"password must be {PASSWORD_MIN_LENGTH} to {PASSWORD_MAX_LENGTH} characters"
            )

    def __str__(self) -> str:
        return "********"
