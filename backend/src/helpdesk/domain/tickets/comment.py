from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from helpdesk.domain.ids import CommentId, TicketId, UserId
from helpdesk.domain.text import ensure_text

COMMENT_BODY_MAX_LENGTH = 10_000


class Visibility(StrEnum):
    PUBLIC = "public"
    INTERNAL = "internal"


@dataclass(frozen=True, slots=True)
class CommentBody:
    value: str

    def __post_init__(self) -> None:
        ensure_text(self.value, field="comment", max_length=COMMENT_BODY_MAX_LENGTH)

    def __str__(self) -> str:
        return self.value


# Comments are never edited, so the thread doubles as a record of what the customer was told.
# New comments come from Ticket.add_comment, which decides who may write what; constructing one
# directly is for loading from storage.
@dataclass(frozen=True, slots=True, kw_only=True)
class Comment:
    id: CommentId
    ticket_id: TicketId
    author_id: UserId
    body: CommentBody
    visibility: Visibility
    created_at: datetime
