# Shared here rather than in each aggregate so tickets can reference users without importing them.
from typing import NewType
from uuid import UUID

TicketId = NewType("TicketId", UUID)
CommentId = NewType("CommentId", UUID)
UserId = NewType("UserId", UUID)
