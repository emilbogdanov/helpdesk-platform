from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

    from helpdesk.domain.ids import UserId
    from helpdesk.domain.roles import Role
    from helpdesk.domain.users.values import DisplayName, EmailAddress


class User:
    # The constructor rebuilds a user from storage; new accounts go through register().
    def __init__(
        self,
        *,
        user_id: UserId,
        email: EmailAddress,
        display_name: DisplayName,
        role: Role,
        password_hash: str,
        is_active: bool,
        created_at: datetime,
    ) -> None:
        self._id = user_id
        self._email = email
        self._display_name = display_name
        self._role = role
        self._password_hash = password_hash
        self._is_active = is_active
        self._created_at = created_at

    @classmethod
    def register(
        cls,
        *,
        user_id: UserId,
        email: EmailAddress,
        display_name: DisplayName,
        role: Role,
        password_hash: str,
        at: datetime,
    ) -> User:
        return cls(
            user_id=user_id,
            email=email,
            display_name=display_name,
            role=role,
            password_hash=password_hash,
            is_active=True,
            created_at=at,
        )

    @property
    def id(self) -> UserId:
        return self._id

    @property
    def email(self) -> EmailAddress:
        return self._email

    @property
    def display_name(self) -> DisplayName:
        return self._display_name

    @property
    def role(self) -> Role:
        return self._role

    @property
    def password_hash(self) -> str:
        return self._password_hash

    @property
    def is_active(self) -> bool:
        return self._is_active

    @property
    def created_at(self) -> datetime:
        return self._created_at

    @property
    def can_work_tickets(self) -> bool:
        return self._is_active and self._role.is_staff

    def change_role(self, role: Role) -> None:
        self._role = role

    def deactivate(self) -> None:
        self._is_active = False

    def reactivate(self) -> None:
        self._is_active = True

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, User):
            return NotImplemented
        return self._id == other._id

    def __hash__(self) -> int:
        return hash(self._id)

    def __repr__(self) -> str:
        return f"User(id={self._id}, role={self._role}, is_active={self._is_active})"
