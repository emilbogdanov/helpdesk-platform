import asyncio
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from helpdesk.application.errors import InvalidCredentialsError
from helpdesk.cli import PASSWORD_VARIABLE, main
from helpdesk.config import Settings
from helpdesk.domain.users.values import EmailAddress
from helpdesk.main import app as create_production_app
from helpdesk.main import build_container

pytestmark = pytest.mark.integration

ADMIN_EMAIL = "ops@helpdesk.test"
ADMIN_PASSWORD = "bootstrap-only-7731"


@pytest.fixture
def production_settings(
    database_url: str, engine: object, monkeypatch: pytest.MonkeyPatch
) -> Settings:
    # `engine` is requested so its teardown empties the tables after the test.
    monkeypatch.setenv("HELPDESK_DATABASE_URL", database_url)
    monkeypatch.setenv("HELPDESK_REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("HELPDESK_JWT_SECRET", "integration-test-signing-secret-000000")
    monkeypatch.setenv(PASSWORD_VARIABLE, ADMIN_PASSWORD)
    return Settings(_env_file=None)


@pytest.fixture
def admin(production_settings: Settings) -> None:
    assert main(["create-admin", "--email", ADMIN_EMAIL, "--name", "Operations"]) == 0


def test_create_admin_refuses_a_taken_email(
    admin: None, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["create-admin", "--email", ADMIN_EMAIL, "--name", "Again"]) == 1
    assert "already exists" in capsys.readouterr().err


def test_create_admin_refuses_a_malformed_email(
    production_settings: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["create-admin", "--email", "ops", "--name", "Operations"]) == 1
    assert "must look like" in capsys.readouterr().err


class TestResetPassword:
    NEW_PASSWORD = "lantern-quay-88"

    def test_the_new_password_works_and_the_old_one_stops_working(
        self, admin: None, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setenv(PASSWORD_VARIABLE, self.NEW_PASSWORD)

        assert main(["reset-password", "--email", ADMIN_EMAIL]) == 0

        assert capsys.readouterr().out == f"new password set for {ADMIN_EMAIL}\n"
        assert asyncio.run(_can_log_in(ADMIN_EMAIL, self.NEW_PASSWORD))
        assert not asyncio.run(_can_log_in(ADMIN_EMAIL, ADMIN_PASSWORD))

    def test_unknown_email_is_an_error(
        self, production_settings: Settings, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert main(["reset-password", "--email", "nobody@helpdesk.test"]) == 1
        assert capsys.readouterr().err == "error: no account uses nobody@helpdesk.test\n"

    def test_typing_the_password_twice_sets_it(
        self, admin: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv(PASSWORD_VARIABLE)
        monkeypatch.setattr("getpass.getpass", lambda _prompt: self.NEW_PASSWORD)

        assert main(["reset-password", "--email", ADMIN_EMAIL]) == 0
        assert asyncio.run(_can_log_in(ADMIN_EMAIL, self.NEW_PASSWORD))

    def test_a_mistyped_repeat_changes_nothing(
        self, admin: None, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.delenv(PASSWORD_VARIABLE)
        typed = iter([self.NEW_PASSWORD, "lantern-quay-89"])
        monkeypatch.setattr("getpass.getpass", lambda _prompt: next(typed))

        assert main(["reset-password", "--email", ADMIN_EMAIL]) == 1

        assert capsys.readouterr().err == "error: the two passwords don't match\n"
        assert asyncio.run(_can_log_in(ADMIN_EMAIL, ADMIN_PASSWORD))


async def _can_log_in(email: str, password: str) -> bool:
    container = build_container(Settings())
    try:
        await container.auth().log_in(EmailAddress(email), password)
    except InvalidCredentialsError:
        return False
    finally:
        await container.close()
    return True


@pytest.fixture
async def client(production_settings: Settings, admin: None) -> AsyncIterator[AsyncClient]:
    # The same factory uvicorn runs, configured from the environment set above.
    app = create_production_app()
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://helpdesk.test") as client,
    ):
        yield client


async def bearer(client: AsyncClient, email: str, password: str) -> dict[str, str]:
    response = await client.post("/auth/token", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def test_support_conversation_through_the_real_stack(client: AsyncClient) -> None:
    as_admin = await bearer(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    agent = await client.post(
        "/users",
        json={
            "email": "mila@helpdesk.test",
            "display_name": "Mila Georgieva",
            "role": "agent",
            "password": "first-shift-2026",
        },
        headers=as_admin,
    )
    await client.post(
        "/auth/sign-up",
        json={
            "email": "petar.ivanov@northwind.bg",
            "display_name": "Petar Ivanov",
            "password": "plum-orchard-41",
        },
    )
    as_agent = await bearer(client, "mila@helpdesk.test", "first-shift-2026")
    as_customer = await bearer(client, "petar.ivanov@northwind.bg", "plum-orchard-41")

    opened = await client.post(
        "/tickets",
        json={"subject": "Can't export March invoices", "description": "Export spins forever."},
        headers=as_customer | {"Idempotency-Key": "march-export-1"},
    )
    ticket_url = f"/tickets/{opened.json()['id']}"
    taken = await client.post(f"{ticket_url}/take", headers=as_agent)
    await client.put(f"{ticket_url}/status", json={"status": "in_progress"}, headers=as_agent)
    await client.put(
        f"{ticket_url}/status", json={"status": "waiting_on_customer"}, headers=as_agent
    )
    await client.post(
        f"{ticket_url}/comments", json={"body": "Which browser are you using?"}, headers=as_agent
    )
    await client.post(f"{ticket_url}/comments", json={"body": "Firefox 141."}, headers=as_customer)
    final = await client.get(ticket_url, headers=as_customer)
    thread = await client.get(f"{ticket_url}/comments", headers=as_customer)

    assert agent.status_code == 201
    assert opened.status_code == 201
    assert taken.json()["assignee"]["id"] == agent.json()["id"]
    assert final.json()["status"] == "in_progress"
    assert [comment["body"] for comment in thread.json()] == [
        "Which browser are you using?",
        "Firefox 141.",
    ]
