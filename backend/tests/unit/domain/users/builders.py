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


EMAILS = {
    REQUESTER: "petar.ivanov@northwind.bg",
    OTHER_CUSTOMER: "elena@brightloop.io",
    MILA: "mila@helpdesk.test",
    STEFAN: "stefan@helpdesk.test",
}


def everyone(password_hash: str = FAKE_PASSWORD_HASH) -> list[User]:
    """The people the ticket builders refer to by id."""
    return [
        user(
            user_id,
            email=EMAILS[user_id],
            name=name,
            role=role,
            password_hash=password_hash,
        )
        for user_id, name, role in [
            (REQUESTER, "Petar Ivanov", Role.CUSTOMER),
            (OTHER_CUSTOMER, "Elena Dimova", Role.CUSTOMER),
            (MILA, "Mila Georgieva", Role.AGENT),
            (STEFAN, "Stefan Kolev", Role.ADMIN),
        ]
    ]
