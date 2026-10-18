from uuid import uuid4

from helpdesk.application.ports import Clock, PasswordHasher, UnitOfWork
from helpdesk.domain.ids import UserId
from helpdesk.domain.roles import Role
from helpdesk.domain.users.user import User
from helpdesk.domain.users.values import DisplayName, EmailAddress, Password


# Creates an admin with no acting admin to authorise it, which is how the first account on
# a fresh install comes to exist. Only the operator CLI calls this; the API never does.
async def register_admin(
    uow: UnitOfWork,
    hasher: PasswordHasher,
    clock: Clock,
    *,
    email: EmailAddress,
    display_name: DisplayName,
    password: Password,
) -> User:
    admin = User.register(
        user_id=UserId(uuid4()),
        email=email,
        display_name=display_name,
        role=Role.ADMIN,
        password_hash=await hasher.hash(password),
        at=clock.now(),
    )
    async with uow:
        await uow.users.add(admin)
        await uow.commit()
    return admin
