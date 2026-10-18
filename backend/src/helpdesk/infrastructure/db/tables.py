from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Identity,
    Index,
    MetaData,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from helpdesk.domain.roles import Role
from helpdesk.domain.tickets.comment import Visibility
from helpdesk.domain.tickets.status import TicketStatus
from helpdesk.domain.tickets.values import SUBJECT_MAX_LENGTH, Priority
from helpdesk.domain.users.values import DISPLAY_NAME_MAX_LENGTH, EMAIL_MAX_LENGTH

# Deterministic constraint names, so migrations can refer to them and
# autogenerate never sees a renamed constraint as a new one.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


# Shared by the partial index and the worker's query, which must match it to use the index.
AWAITING_FIRST_RESPONSE = (
    "first_responded_at IS NULL AND sla_breached_at IS NULL"
    " AND status IN ('open', 'in_progress', 'waiting_on_customer')"
)


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    type_annotation_map = {datetime: DateTime(timezone=True)}  # noqa: RUF012


def _enum_column(enum: type[StrEnum], name: str) -> Enum:
    # VARCHAR plus a CHECK constraint instead of a native Postgres enum: adding a status
    # later is a one-line migration rather than an ALTER TYPE dance.
    return Enum(
        enum,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=32,
        values_callable=lambda members: [member.value for member in members],
    )


class UserRow(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(EMAIL_MAX_LENGTH), unique=True)
    display_name: Mapped[str] = mapped_column(String(DISPLAY_NAME_MAX_LENGTH))
    role: Mapped[Role] = mapped_column(_enum_column(Role, "role"))
    password_hash: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool]
    created_at: Mapped[datetime]
    version: Mapped[int] = mapped_column()

    __table_args__ = (Index("ix_users_display_name_id", "display_name", "id"),)
    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012


class TicketRow(Base):
    __tablename__ = "tickets"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    requester_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    subject: Mapped[str] = mapped_column(String(SUBJECT_MAX_LENGTH))
    description: Mapped[str] = mapped_column(Text)
    priority: Mapped[Priority] = mapped_column(_enum_column(Priority, "priority"))
    status: Mapped[TicketStatus] = mapped_column(_enum_column(TicketStatus, "status"))
    assignee_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
    resolved_at: Mapped[datetime | None]
    closed_at: Mapped[datetime | None]
    first_responded_at: Mapped[datetime | None]
    sla_breached_at: Mapped[datetime | None]
    idempotency_key: Mapped[str | None] = mapped_column(String(255))
    # Optimistic locking: an UPDATE only matches the version that was read, so two agents
    # editing the same ticket can't silently overwrite each other.
    version: Mapped[int] = mapped_column()

    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012
    __table_args__ = (
        UniqueConstraint("requester_id", "idempotency_key"),
        CheckConstraint(
            "status NOT IN ('in_progress', 'waiting_on_customer') OR assignee_id IS NOT NULL",
            name="worked_ticket_has_assignee",
        ),
        # One index per list view; each ends in id because the cursor sorts by it last.
        Index("ix_tickets_created_at_id", "created_at", "id"),
        Index("ix_tickets_updated_at_id", "updated_at", "id"),
        Index("ix_tickets_requester_id_created_at_id", "requester_id", "created_at", "id"),
        Index("ix_tickets_status_created_at_id", "status", "created_at", "id"),
        Index("ix_tickets_assignee_id_updated_at_id", "assignee_id", "updated_at", "id"),
        # Partial indexes for the worker: they hold only the tickets it still has to look at,
        # so they stay small no matter how much history piles up.
        Index(
            "ix_tickets_awaiting_first_response",
            "created_at",
            postgresql_where=text(AWAITING_FIRST_RESPONSE),
        ),
        Index(
            "ix_tickets_resolved_at",
            "resolved_at",
            postgresql_where=text("status = 'resolved'"),
        ),
    )


class CommentRow(Base):
    __tablename__ = "comments"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    ticket_id: Mapped[UUID] = mapped_column(ForeignKey("tickets.id"))
    author_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    body: Mapped[str] = mapped_column(Text)
    visibility: Mapped[Visibility] = mapped_column(_enum_column(Visibility, "visibility"))
    created_at: Mapped[datetime]

    __table_args__ = (Index("ix_comments_ticket_id_created_at", "ticket_id", "created_at"),)


class AuditEntryRow(Base):
    __tablename__ = "audit_entries"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    ticket_id: Mapped[UUID] = mapped_column(ForeignKey("tickets.id"))
    # Null for changes the system made on its own, such as auto-closing a ticket.
    actor_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    event_type: Mapped[str] = mapped_column(String(64))
    occurred_at: Mapped[datetime]
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)

    __table_args__ = (Index("ix_audit_entries_ticket_id_occurred_at", "ticket_id", "occurred_at"),)
