import json
from base64 import urlsafe_b64decode, urlsafe_b64encode
from datetime import datetime
from typing import Any
from uuid import UUID

from helpdesk.application.tickets.queries import TicketCursor, TicketSort
from helpdesk.application.users.queries import UserCursor
from helpdesk.domain.errors import InvalidValueError
from helpdesk.domain.ids import TicketId, UserId

# Clients treat cursors as opaque strings. They aren't signed: editing one only moves where a
# page starts inside results the caller may see anyway, so there is nothing to protect.


def encode_cursor(sort: TicketSort, cursor: TicketCursor) -> str:
    return _encode(
        {"sort": sort.value, "at": cursor.sort_value.isoformat(), "id": str(cursor.ticket_id)}
    )


def decode_cursor(sort: TicketSort, token: str) -> TicketCursor:
    payload = _decode(token)
    try:
        cursor_sort = str(payload["sort"])
        sort_value = datetime.fromisoformat(payload["at"])
        cursor = TicketCursor(sort_value, TicketId(UUID(payload["id"])))
    except (ValueError, KeyError, TypeError) as error:
        raise InvalidValueError("cursor is invalid") from error
    if sort_value.tzinfo is None:
        raise InvalidValueError("cursor is invalid")
    # A cursor marks a position in one ordering; reused with another it would skip rows.
    if cursor_sort != sort:
        raise InvalidValueError(f"cursor was issued for sort={cursor_sort}, not sort={sort}")
    return cursor


def encode_user_cursor(cursor: UserCursor) -> str:
    return _encode({"name": cursor.display_name, "id": str(cursor.user_id)})


def decode_user_cursor(token: str) -> UserCursor:
    payload = _decode(token)
    try:
        return UserCursor(str(payload["name"]), UserId(UUID(payload["id"])))
    except (ValueError, KeyError, TypeError) as error:
        raise InvalidValueError("cursor is invalid") from error


def _encode(payload: dict[str, str]) -> str:
    raw = json.dumps(payload, separators=(",", ":")).encode()
    return urlsafe_b64encode(raw).decode().rstrip("=")


def _decode(token: str) -> dict[str, Any]:
    try:
        payload = json.loads(urlsafe_b64decode(token + "=" * (-len(token) % 4)))
    except ValueError as error:
        raise InvalidValueError("cursor is invalid") from error
    if not isinstance(payload, dict):
        raise InvalidValueError("cursor is invalid")
    return payload
