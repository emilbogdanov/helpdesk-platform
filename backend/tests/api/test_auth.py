from datetime import timedelta

import pytest
from httpx import AsyncClient

from tests.api.conftest import PASSWORD, Headers
from tests.unit.application.fakes import FixedClock
from tests.unit.domain.tickets.builders import OPENED_AT


async def test_sign_up_then_log_in(client: AsyncClient) -> None:
    created = await client.post(
        "/auth/sign-up",
        json={
            "email": "Ana.Stoyanova@brightloop.io",
            "display_name": "Ana Stoyanova",
            "password": "quiet-harbour-19",
        },
    )
    token = await client.post(
        "/auth/token", json={"email": "ana.stoyanova@brightloop.io", "password": "quiet-harbour-19"}
    )

    assert created.status_code == 201
    assert created.json() | {"id": None} == {
        "id": None,
        "email": "ana.stoyanova@brightloop.io",
        "display_name": "Ana Stoyanova",
        "role": "customer",
        "is_active": True,
        "created_at": "2026-10-12T09:14:00Z",
    }
    assert token.status_code == 200
    assert token.json()["token_type"] == "bearer"
    assert token.json()["expires_at"] == "2026-10-12T09:29:00Z"


async def test_sign_up_cannot_choose_a_role(client: AsyncClient) -> None:
    response = await client.post(
        "/auth/sign-up",
        json={
            "email": "ana@brightloop.io",
            "display_name": "Ana",
            "password": "quiet-harbour-19",
            "role": "admin",
        },
    )

    assert response.status_code == 422


async def test_sign_up_with_a_taken_email_conflicts(client: AsyncClient) -> None:
    response = await client.post(
        "/auth/sign-up",
        json={"email": "MILA@helpdesk.test", "display_name": "Mila", "password": PASSWORD},
    )

    assert response.status_code == 409
    assert response.json()["code"] == "email_taken"


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("email", "ana-at-brightloop.io", "email must look like name@example.com"),
        ("display_name", " ", "display name must not be blank"),
        ("password", "short", "password must be 10 to 128 characters"),
    ],
)
async def test_sign_up_explains_invalid_input(
    client: AsyncClient, field: str, value: str, message: str
) -> None:
    body = {"email": "ana@brightloop.io", "display_name": "Ana", "password": "quiet-harbour-19"}

    response = await client.post("/auth/sign-up", json=body | {field: value})

    assert response.status_code == 422
    assert response.json() == {"detail": message, "code": "invalid_value"}


@pytest.mark.parametrize(
    "credentials",
    [
        {"email": "mila@helpdesk.test", "password": "not-her-password"},
        {"email": "nobody@helpdesk.test", "password": PASSWORD},
    ],
    ids=["wrong-password", "unknown-email"],
)
async def test_bad_credentials_get_the_same_401(
    client: AsyncClient, credentials: dict[str, str]
) -> None:
    response = await client.post("/auth/token", json=credentials)

    assert response.status_code == 401
    assert response.json() == {
        "detail": "email or password is incorrect",
        "code": "invalid_credentials",
    }


class TestProtectedEndpoints:
    @pytest.mark.parametrize(
        "headers",
        [
            {},
            {"Authorization": "Bearer not-a-token"},
            {"Authorization": "Basic bWlsYTpwYXNzd29yZA=="},
        ],
        ids=["no-token", "garbage-token", "wrong-scheme"],
    )
    async def test_reject_requests_without_a_valid_token(
        self, client: AsyncClient, headers: Headers
    ) -> None:
        response = await client.get("/users/me", headers=headers)

        assert response.status_code == 401
        assert response.headers["WWW-Authenticate"] == "Bearer"
        assert response.json()["code"] == "invalid_token"

    async def test_reject_expired_tokens(
        self, client: AsyncClient, as_agent: Headers, clock: FixedClock
    ) -> None:
        clock.current = OPENED_AT + timedelta(minutes=15)

        response = await client.get("/users/me", headers=as_agent)

        assert response.status_code == 401
        assert response.json()["detail"] == "access token has expired"
