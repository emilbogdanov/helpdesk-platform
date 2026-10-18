from helpdesk.application.users.password_reset import reset_password
from helpdesk.domain.users.values import EmailAddress, Password
from tests.unit.application.fakes import FakePasswordHasher, FakeUnitOfWork
from tests.unit.domain.tickets.builders import MILA
from tests.unit.domain.users.builders import everyone


async def seeded() -> FakeUnitOfWork:
    uow = FakeUnitOfWork()
    for person in everyone():
        await uow.users.add(person)
    return uow


async def test_sets_a_new_password_hash() -> None:
    uow = await seeded()

    changed = await reset_password(
        uow,
        FakePasswordHasher(),
        email=EmailAddress("Mila@Helpdesk.test"),
        password=Password("lantern-quay-88"),
    )

    stored = await uow.users.get(MILA)
    assert changed is not None
    assert stored is not None
    assert stored.password_hash == "hashed:lantern-quay-88"
    assert uow.commits == 1


async def test_unknown_email_changes_nothing() -> None:
    uow = await seeded()

    changed = await reset_password(
        uow,
        FakePasswordHasher(),
        email=EmailAddress("nobody@helpdesk.test"),
        password=Password("lantern-quay-88"),
    )

    assert changed is None
    assert uow.commits == 0
