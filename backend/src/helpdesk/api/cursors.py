import json
from base64 import urlsafe_b64decode, urlsafe_b64encode
from datetime import datetime
from uuid import UUID

from helpdesk.application.tickets.queries import TicketCursor, TicketSort
from helpdesk.domain.errors import InvalidValueError
from helpdesk.domain.ids import TicketId

# Clients treat cursors as opaque strings. They aren't signed: editing one only moves where a
# page starts inside results the caller may see anyway, so there is nothing to protect.


def encode_cursor(sort: TicketSort, cursor: TicketCursor) -> str:
    payload = {"sort": sort.value, "at": cursor.sort_value.isoformat(), "id": str(cursor.ticket_id)}
    raw = json.dumps(payload, separators=(",", ":")).encode()
    return urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(sort: TicketSort, token: str) -> TicketCursor:
    try:
        cursor_sort, cursor = _parse(token)
    except (ValueError, KeyError, TypeError) as error:
        raise InvalidValueError("cursor is invalid") from error
    # A cursor marks a position in one ordering; reused with another it would skip rows.
    if cursor_sort != sort:
        raise InvalidValueError(f"cursor was issued for sort={cursor_sort}, not sort={sort}")
    return cursor


def _parse(token: str) -> tuple[str, TicketCursor]:
    payload = json.loads(urlsafe_b64decode(token + "=" * (-len(token) % 4)))
    sort_value = datetime.fromisoformat(payload["at"])
    if sort_value.tzinfo is None:
        raise ValueError("cursor time has no timezone")
    return str(payload["sort"]), TicketCursor(sort_value, TicketId(UUID(payload["id"])))
