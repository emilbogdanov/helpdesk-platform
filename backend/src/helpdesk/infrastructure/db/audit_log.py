from collections.abc import Sequence
from dataclasses import fields
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from helpdesk.domain.ids import UserId
from helpdesk.domain.tickets.events import (
    CommentAdded,
    TicketAssigneeChanged,
    TicketEvent,
    TicketOpened,
    TicketPriorityChanged,
    TicketStatusChanged,
)
from helpdesk.infrastructure.db.tables import AuditEntryRow

# Stored names are part of the data, so they're spelled out rather than derived from class
# names: renaming an event class must not change the history already written.
EVENT_TYPES: dict[type[TicketEvent], str] = {
    TicketOpened: "ticket_opened",
    TicketStatusChanged: "status_changed",
    TicketAssigneeChanged: "assignee_changed",
    TicketPriorityChanged: "priority_changed",
    CommentAdded: "comment_added",
}

# Already stored in their own columns.
_COLUMN_FIELDS = frozenset({"ticket_id", "occurred_at"})


class SqlAuditLog:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(self, actor_id: UserId, events: Sequence[TicketEvent]) -> None:
        self._session.add_all(
            AuditEntryRow(
                ticket_id=event.ticket_id,
                actor_id=actor_id,
                event_type=EVENT_TYPES[type(event)],
                occurred_at=event.occurred_at,
                payload=_payload(event),
            )
            for event in events
        )


def _payload(event: TicketEvent) -> dict[str, Any]:
    return {
        field.name: _to_json(getattr(event, field.name))
        for field in fields(event)
        if field.name not in _COLUMN_FIELDS
    }


def _to_json(value: object) -> object:
    # Enums are StrEnums and serialize as their value; only UUIDs need converting.
    return str(value) if isinstance(value, UUID) else value
