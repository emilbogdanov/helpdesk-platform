from helpdesk.domain.ids import UserId
from helpdesk.domain.roles import Role
from helpdesk.domain.users.user import User
from helpdesk.domain.users.values import DisplayName, EmailAddress
from tests.unit.domain.tickets.builders import (
    MILA,
    OPENED_AT,
    OTHER_CUSTOMER,
    REQUESTER,
    STEFAN,
)

# Not a real hash: hashing is the hasher's job, and these users never log in with it.
FAKE_PASSWORD_HASH = "fake-hash"


def user(
    user_id: UserId,
    *,
    email: str,
    name: str,
    role: Role,
    is_active: bool = True,
    password_hash: str = FAKE_PASSWORD_HASH,
) -> User:
    return User(
        user_id=user_id,
        email=EmailAddress(email),
        display_name=DisplayName(name),
        role=role,
        password_hash=password_hash,
        is_active=is_active,
        created_at=OPENED_AT,
    )


def everyone() -> list[User]:
    """The people the ticket builders refer to by id."""
    return [
        user(REQUESTER, email="petar.ivanov@northwind.bg", name="Petar Ivanov", role=Role.CUSTOMER),
        user(OTHER_CUSTOMER, email="elena@brightloop.io", name="Elena Dimova", role=Role.CUSTOMER),
        user(MILA, email="mila@helpdesk.test", name="Mila Georgieva", role=Role.AGENT),
        user(STEFAN, email="stefan@helpdesk.test", name="Stefan Kolev", role=Role.ADMIN),
    ]
