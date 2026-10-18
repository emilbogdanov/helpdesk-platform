from helpdesk.application.ports import PasswordHasher, UnitOfWork
from helpdesk.domain.users.user import User
from helpdesk.domain.users.values import EmailAddress, Password


# For the operator CLI, like register_admin: there is no self-service reset yet, so someone
# with server access sets the new password. Tokens issued before the reset stay valid until
# they expire (15 minutes by default); there is no revocation list.
async def reset_password(
    uow: UnitOfWork, hasher: PasswordHasher, *, email: EmailAddress, password: Password
) -> User | None:
    password_hash = await hasher.hash(password)
    async with uow:
        user = await uow.users.get_by_email(email)
        if user is None:
            return None
        user.change_password(password_hash)
        await uow.users.update(user)
        await uow.commit()
    return user
