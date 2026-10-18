from collections.abc import Awaitable, Callable
from uuid import UUID

import pytest

from helpdesk.application.actor import Actor
from helpdesk.application.errors import (
    AdminOnlyError,
    EmailTakenError,
    OwnAccountError,
    UserNotFoundError,
)
from helpdesk.application.users.user_service import UserService
from helpdesk.domain.ids import UserId
from helpdesk.domain.roles import Role
from helpdesk.domain.users.user import User
from helpdesk.domain.users.values import DisplayName, EmailAddress, Password
from tests.unit.application.fakes import FakePasswordHasher, FakeUnitOfWork, FixedClock
from tests.unit.domain.tickets.builders import MILA, OPENED_AT, REQUESTER, STEFAN
from tests.unit.domain.users.builders import everyone

ADMIN = Actor(STEFAN, Role.ADMIN)
AGENT = Actor(MILA, Role.AGENT)


@pytest.fixture
async def uow() -> FakeUnitOfWork:
    uow = FakeUnitOfWork()
    for person in everyone():
        await uow.users.add(person)
    return uow


@pytest.fixture
def service(uow: FakeUnitOfWork) -> UserService:
    return UserService(uow, FakePasswordHasher(), FixedClock(OPENED_AT))


async def stored(uow: FakeUnitOfWork, user_id: UserId) -> User:
    user = await uow.users.get(user_id)
    assert user is not None
    return user


class TestCreateUser:
    async def test_admin_creates_an_agent_account(
        self, service: UserService, uow: FakeUnitOfWork
    ) -> None:
        created = await service.create_user(
            ADMIN,
            email=EmailAddress("radoslav@helpdesk.test"),
            display_name=DisplayName("Radoslav Petkov"),
            role=Role.AGENT,
            password=Password("first-shift-2026"),
        )

        saved = await stored(uow, created.id)
        assert saved.role is Role.AGENT
        assert saved.is_active
        assert saved.password_hash == "hashed:first-shift-2026"
        assert uow.commits == 1

    async def test_email_must_be_free(self, service: UserService) -> None:
        with pytest.raises(EmailTakenError):
            await service.create_user(
                ADMIN,
                email=EmailAddress("mila@helpdesk.test"),
                display_name=DisplayName("Mila Again"),
                role=Role.AGENT,
                password=Password("first-shift-2026"),
            )

    async def test_agents_cannot_create_accounts(self, service: UserService) -> None:
        with pytest.raises(AdminOnlyError, match="only admins can create accounts"):
            await service.create_user(
                AGENT,
                email=EmailAddress("radoslav@helpdesk.test"),
                display_name=DisplayName("Radoslav Petkov"),
                role=Role.ADMIN,
                password=Password("first-shift-2026"),
            )


@pytest.mark.parametrize("actor", [Actor(REQUESTER, Role.CUSTOMER), AGENT, ADMIN])
async def test_everyone_can_view_their_own_profile(service: UserService, actor: Actor) -> None:
    assert (await service.get_profile(actor)).id == actor.user_id


class TestGetUser:
    async def test_admin_can_view_any_account(self, service: UserService) -> None:
        assert (await service.get_user(ADMIN, REQUESTER)).id == REQUESTER

    async def test_missing_account_is_not_found(self, service: UserService) -> None:
        with pytest.raises(UserNotFoundError):
            await service.get_user(ADMIN, UserId(UUID(int=5)))

    async def test_agents_cannot_view_accounts(self, service: UserService) -> None:
        with pytest.raises(AdminOnlyError):
            await service.get_user(AGENT, REQUESTER)


class TestManageAccounts:
    async def test_change_role(self, service: UserService, uow: FakeUnitOfWork) -> None:
        await service.change_role(ADMIN, MILA, Role.ADMIN)

        assert (await stored(uow, MILA)).role is Role.ADMIN

    async def test_deactivate_and_reactivate(
        self, service: UserService, uow: FakeUnitOfWork
    ) -> None:
        await service.deactivate(ADMIN, MILA)
        assert not (await stored(uow, MILA)).is_active

        await service.reactivate(ADMIN, MILA)
        assert (await stored(uow, MILA)).is_active

    @pytest.mark.parametrize(
        "manage",
        [
            pytest.param(lambda s, a, u: s.change_role(a, u, Role.AGENT), id="change-role"),
            pytest.param(lambda s, a, u: s.deactivate(a, u), id="deactivate"),
            pytest.param(lambda s, a, u: s.reactivate(a, u), id="reactivate"),
        ],
    )
    async def test_admins_cannot_manage_their_own_account(
        self,
        service: UserService,
        uow: FakeUnitOfWork,
        manage: Callable[[UserService, Actor, UserId], Awaitable[User]],
    ) -> None:
        with pytest.raises(OwnAccountError):
            await manage(service, ADMIN, STEFAN)

        assert (await stored(uow, STEFAN)).role is Role.ADMIN
        assert uow.commits == 0

    async def test_agents_cannot_manage_accounts(self, service: UserService) -> None:
        with pytest.raises(AdminOnlyError, match="deactivate accounts"):
            await service.deactivate(AGENT, REQUESTER)

    async def test_missing_account_is_not_found(self, service: UserService) -> None:
        with pytest.raises(UserNotFoundError):
            await service.deactivate(ADMIN, UserId(UUID(int=5)))
