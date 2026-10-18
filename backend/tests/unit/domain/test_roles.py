import pytest

from helpdesk.domain.roles import Role


@pytest.mark.parametrize("role", [Role.AGENT, Role.ADMIN])
def test_agents_and_admins_are_staff(role: Role) -> None:
    assert role.is_staff


def test_customers_are_not_staff() -> None:
    assert not Role.CUSTOMER.is_staff
