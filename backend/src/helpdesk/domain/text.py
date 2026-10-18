from helpdesk.domain.errors import InvalidValueError


def ensure_text(value: str, *, field: str, max_length: int) -> None:
    if not value.strip():
        raise InvalidValueError(f"{field} must not be blank")
    if len(value) > max_length:
        raise InvalidValueError(f"{field} must be at most {max_length} characters")
