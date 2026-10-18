from collections.abc import Callable
from uuid import uuid4

from helpdesk.application.actor import Actor
from helpdesk.application.errors import AdminOnlyError, OwnAccountError, UserNotFoundError
from helpdesk.application.ports import Clock, PasswordHasher, UnitOfWork
from helpdesk.domain.ids import UserId
from helpdesk.domain.roles import Role
from helpdesk.domain.users.user import User
from helpdesk.domain.users.values import DisplayName, EmailAddress, Password


class UserService:
    def __init__(self, uow: UnitOfWork, hasher: PasswordHasher, clock: Clock) -> None:
        self._uow = uow
        self._hasher = hasher
        self._clock = clock

    async def create_user(
        self,
        actor: Actor,
        *,
        email: EmailAddress,
        display_name: DisplayName,
        role: Role,
        password: Password,
    ) -> User:
        _require_admin(actor, "create accounts")
        password_hash = await self._hasher.hash(password)
        user = User.register(
            user_id=UserId(uuid4()),
            email=email,
            display_name=display_name,
            role=role,
            password_hash=password_hash,
            at=self._clock.now(),
        )
        async with self._uow as uow:
            await uow.users.add(user)
            await uow.commit()
        return user

    async def get_user(self, actor: Actor, user_id: UserId) -> User:
        _require_admin(actor, "view accounts")
        async with self._uow as uow:
            return await _load(uow, user_id)

    async def change_role(self, actor: Actor, user_id: UserId, role: Role) -> User:
        return await self._manage(
            actor, user_id, action="change the role", change=lambda user: user.change_role(role)
        )

    async def deactivate(self, actor: Actor, user_id: UserId) -> User:
        return await self._manage(
            actor, user_id, action="deactivate", change=lambda user: user.deactivate()
        )

    async def reactivate(self, actor: Actor, user_id: UserId) -> User:
        return await self._manage(
            actor, user_id, action="reactivate", change=lambda user: user.reactivate()
        )

    async def _manage(
        self, actor: Actor, user_id: UserId, *, action: str, change: Callable[[User], None]
    ) -> User:
        _require_admin(actor, f"{action} accounts")
        if user_id == actor.user_id:
            raise OwnAccountError(action)
        async with self._uow as uow:
            user = await _load(uow, user_id)
            change(user)
            await uow.users.update(user)
            await uow.commit()
        return user


async def _load(uow: UnitOfWork, user_id: UserId) -> User:
    user = await uow.users.get(user_id)
    if user is None:
        raise UserNotFoundError(user_id)
    return user


def _require_admin(actor: Actor, action: str) -> None:
    if actor.role is not Role.ADMIN:
        raise AdminOnlyError(action)
