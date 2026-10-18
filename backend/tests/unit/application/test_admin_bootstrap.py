import pytest

from helpdesk.application.errors import EmailTakenError
from helpdesk.application.users.admin_bootstrap import register_admin
from helpdesk.domain.roles import Role
from helpdesk.domain.users.values import DisplayName, EmailAddress, Password
from tests.unit.application.fakes import FakePasswordHasher, FakeUnitOfWork, FixedClock
from tests.unit.domain.tickets.builders import OPENED_AT
from tests.unit.domain.users.builders import everyone


async def test_creates_an_active_admin() -> None:
    uow = FakeUnitOfWork()

    admin = await register_admin(
        uow,
        FakePasswordHasher(),
        FixedClock(OPENED_AT),
        email=EmailAddress("ops@helpdesk.test"),
        display_name=DisplayName("Operations"),
        password=Password("bootstrap-only-7731"),
    )

    stored = await uow.users.get(admin.id)
    assert stored is not None
    assert stored.role is Role.ADMIN
    assert stored.is_active
    assert stored.password_hash == "hashed:bootstrap-only-7731"
    assert uow.commits == 1


async def test_refuses_an_email_that_is_taken() -> None:
    uow = FakeUnitOfWork()
    for person in everyone():
        await uow.users.add(person)

    with pytest.raises(EmailTakenError):
        await register_admin(
            uow,
            FakePasswordHasher(),
            FixedClock(OPENED_AT),
            email=EmailAddress("mila@helpdesk.test"),
            display_name=DisplayName("Mila"),
            password=Password("bootstrap-only-7731"),
        )
