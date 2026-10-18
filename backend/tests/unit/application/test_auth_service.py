from datetime import timedelta
from uuid import UUID

import pytest

from helpdesk.application.actor import Actor
from helpdesk.application.errors import (
    EmailTakenError,
    InvalidCredentialsError,
    InvalidTokenError,
)
from helpdesk.application.ports import TokenClaims
from helpdesk.application.users.auth_service import AccessToken, AuthService
from helpdesk.domain.ids import UserId
from helpdesk.domain.roles import Role
from helpdesk.domain.users.values import DisplayName, EmailAddress, Password
from tests.unit.application.fakes import (
    FakePasswordHasher,
    FakeTokenCodec,
    FakeUnitOfWork,
    FixedClock,
)
from tests.unit.domain.tickets.builders import MILA, OPENED_AT
from tests.unit.domain.users.builders import user

TOKEN_TTL = timedelta(minutes=15)
PASSWORD = "plum-orchard-41"


@pytest.fixture
def uow() -> FakeUnitOfWork:
    return FakeUnitOfWork()


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(OPENED_AT)


@pytest.fixture
def service(uow: FakeUnitOfWork, clock: FixedClock) -> AuthService:
    return AuthService(uow, FakePasswordHasher(), FakeTokenCodec(), clock, token_ttl=TOKEN_TTL)


@pytest.fixture
async def mila(uow: FakeUnitOfWork) -> None:
    await uow.users.add(
        user(
            MILA,
            email="mila@helpdesk.test",
            name="Mila Georgieva",
            role=Role.AGENT,
            password_hash=f"hashed:{PASSWORD}",
        )
    )


async def log_in_mila(service: AuthService) -> AccessToken:
    return await service.log_in(EmailAddress("mila@helpdesk.test"), PASSWORD)


class TestSignUp:
    async def test_creates_an_active_customer_with_a_hashed_password(
        self, service: AuthService, uow: FakeUnitOfWork
    ) -> None:
        created = await service.sign_up(
            email=EmailAddress("petar.ivanov@northwind.bg"),
            display_name=DisplayName("Petar Ivanov"),
            password=Password(PASSWORD),
        )

        stored = await uow.users.get(created.id)
        assert stored is not None
        assert stored.role is Role.CUSTOMER
        assert stored.is_active
        assert stored.password_hash == f"hashed:{PASSWORD}"
        assert stored.created_at == OPENED_AT
        assert uow.commits == 1

    @pytest.mark.usefixtures("mila")
    async def test_rejects_an_email_that_already_has_an_account(
        self, service: AuthService, uow: FakeUnitOfWork
    ) -> None:
        with pytest.raises(EmailTakenError):
            await service.sign_up(
                email=EmailAddress("Mila@Helpdesk.test"),
                display_name=DisplayName("Someone Else"),
                password=Password(PASSWORD),
            )

        assert len(uow.users.rows) == 1


@pytest.mark.usefixtures("mila")
class TestLogIn:
    async def test_issues_a_token_that_expires_after_the_ttl(self, service: AuthService) -> None:
        access = await log_in_mila(service)

        assert access.expires_at == OPENED_AT + TOKEN_TTL
        assert FakeTokenCodec().decode(access.token) == TokenClaims(
            user_id=MILA, expires_at=OPENED_AT + TOKEN_TTL
        )

    async def test_email_is_matched_case_insensitively(self, service: AuthService) -> None:
        access = await service.log_in(EmailAddress("MILA@helpdesk.test"), PASSWORD)

        assert access.token

    @pytest.mark.parametrize(
        ("email", "password"),
        [
            ("mila@helpdesk.test", "wrong-password"),
            ("nobody@helpdesk.test", PASSWORD),
        ],
        ids=["wrong-password", "unknown-email"],
    )
    async def test_bad_credentials_get_one_indistinguishable_error(
        self, service: AuthService, email: str, password: str
    ) -> None:
        with pytest.raises(InvalidCredentialsError, match="email or password is incorrect"):
            await service.log_in(EmailAddress(email), password)

    async def test_deactivated_accounts_cannot_log_in(
        self, service: AuthService, uow: FakeUnitOfWork
    ) -> None:
        uow.users.rows[MILA].deactivate()

        with pytest.raises(InvalidCredentialsError):
            await log_in_mila(service)


@pytest.mark.usefixtures("mila")
class TestAuthenticate:
    async def test_resolves_the_token_to_the_current_user(self, service: AuthService) -> None:
        access = await log_in_mila(service)

        assert await service.authenticate(access.token) == Actor(MILA, Role.AGENT)

    async def test_role_changes_apply_to_existing_tokens(
        self, service: AuthService, uow: FakeUnitOfWork
    ) -> None:
        access = await log_in_mila(service)
        uow.users.rows[MILA].change_role(Role.ADMIN)

        assert (await service.authenticate(access.token)).role is Role.ADMIN

    async def test_expired_token_is_rejected(self, service: AuthService, clock: FixedClock) -> None:
        access = await log_in_mila(service)
        clock.advance(TOKEN_TTL)

        with pytest.raises(InvalidTokenError, match="expired"):
            await service.authenticate(access.token)

    async def test_deactivation_revokes_existing_tokens(
        self, service: AuthService, uow: FakeUnitOfWork
    ) -> None:
        access = await log_in_mila(service)
        uow.users.rows[MILA].deactivate()

        with pytest.raises(InvalidTokenError):
            await service.authenticate(access.token)

    async def test_token_for_a_deleted_account_is_rejected(self, service: AuthService) -> None:
        token = FakeTokenCodec().encode(
            TokenClaims(user_id=UserId(UUID(int=1)), expires_at=OPENED_AT + TOKEN_TTL)
        )

        with pytest.raises(InvalidTokenError):
            await service.authenticate(token)

    async def test_forged_token_is_rejected(self, service: AuthService) -> None:
        with pytest.raises(InvalidTokenError):
            await service.authenticate("not-a-token")
