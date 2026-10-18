from datetime import datetime
from typing import Any, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from helpdesk.domain.roles import Role
from helpdesk.domain.users.user import User


# Request bodies only check shape. The rules for what a valid subject, email or password is
# live in the domain value objects, so they are written down once.
class Request(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ErrorResponse(BaseModel):
    detail: str
    code: str
    # Only for malformed requests: one entry per field that failed validation.
    errors: list[dict[str, Any]] | None = None


class UserResponse(BaseModel):
    id: UUID
    email: str
    display_name: str
    role: Role
    is_active: bool
    created_at: datetime

    @classmethod
    def from_user(cls, user: User) -> Self:
        return cls(
            id=user.id,
            email=str(user.email),
            display_name=str(user.display_name),
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at,
        )
