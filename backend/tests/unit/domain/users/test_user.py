import pytest

from helpdesk.domain.ids import UserId
from helpdesk.domain.roles import Role
from helpdesk.domain.users.user import User
from helpdesk.domain.users.values import DisplayName, EmailAddress
from tests.unit.domain.tickets.builders import MILA, OPENED_AT
from tests.unit.domain.users.builders import user


def test_register_creates_an_active_account() -> None:
    registered = User.register(
        user_id=MILA,
        email=EmailAddress("Mila@Helpdesk.test"),
        display_name=DisplayName("Mila Georgieva"),
        role=Role.AGENT,
        password_hash="argon2-hash",
        at=OPENED_AT,
    )

    assert registered.id == MILA
    assert str(registered.email) == "mila@helpdesk.test"
    assert str(registered.display_name) == "Mila Georgieva"
    assert registered.role is Role.AGENT
    assert registered.password_hash == "argon2-hash"
    assert registered.is_active
    assert registered.created_at == OPENED_AT


@pytest.mark.parametrize("role", [Role.AGENT, Role.ADMIN])
def test_active_staff_can_work_tickets(role: Role) -> None:
    assert user(MILA, email="mila@helpdesk.test", name="Mila", role=role).can_work_tickets


def test_customers_cannot_work_tickets() -> None:
    assert not user(
        MILA, email="mila@helpdesk.test", name="Mila", role=Role.CUSTOMER
    ).can_work_tickets


def test_change_role() -> None:
    mila = user(MILA, email="mila@helpdesk.test", name="Mila", role=Role.AGENT)

    mila.change_role(Role.ADMIN)

    assert mila.role is Role.ADMIN


def test_deactivate_and_reactivate() -> None:
    mila = user(MILA, email="mila@helpdesk.test", name="Mila", role=Role.AGENT)

    mila.deactivate()
    assert not mila.is_active
    assert not mila.can_work_tickets

    mila.reactivate()
    assert mila.is_active


def test_identity_is_the_id() -> None:
    first = user(MILA, email="mila@helpdesk.test", name="Mila", role=Role.AGENT)
    renamed = user(MILA, email="mila.g@helpdesk.test", name="Mila G.", role=Role.ADMIN)

    assert first == renamed
    assert len({first, renamed}) == 1
    assert first != UserId(MILA)


def test_repr_leaves_out_personal_data() -> None:
    mila = user(MILA, email="mila@helpdesk.test", name="Mila", role=Role.AGENT)

    assert repr(mila) == f"User(id={MILA}, role=agent, is_active=True)"
