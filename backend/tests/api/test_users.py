from uuid import UUID

import pytest
from httpx import AsyncClient

from helpdesk.domain.ids import UserId
from tests.api.conftest import Headers, log_in
from tests.unit.domain.tickets.builders import MILA, REQUESTER, STEFAN

NEW_AGENT = {
    "email": "radoslav@helpdesk.test",
    "display_name": "Radoslav Petkov",
    "role": "agent",
    "password": "first-shift-2026",
}


@pytest.mark.parametrize(
    ("user_id", "expected_role"),
    [(REQUESTER, "customer"), (MILA, "agent"), (STEFAN, "admin")],
)
async def test_everyone_sees_their_own_profile(
    client: AsyncClient, user_id: UserId, expected_role: str
) -> None:
    response = await client.get("/users/me", headers=await log_in(client, user_id))

    assert response.status_code == 200
    assert response.json()["role"] == expected_role


async def test_admin_creates_an_agent_who_can_log_in(
    client: AsyncClient, as_admin: Headers
) -> None:
    created = await client.post("/users", json=NEW_AGENT, headers=as_admin)
    token = await client.post(
        "/auth/token", json={"email": NEW_AGENT["email"], "password": NEW_AGENT["password"]}
    )

    assert created.status_code == 201
    assert created.json()["role"] == "agent"
    assert token.status_code == 200


async def test_admin_reads_any_account(client: AsyncClient, as_admin: Headers) -> None:
    response = await client.get(f"/users/{REQUESTER}", headers=as_admin)

    assert response.json()["email"] == "petar.ivanov@northwind.bg"


async def test_unknown_account_is_404(client: AsyncClient, as_admin: Headers) -> None:
    response = await client.get(f"/users/{UUID(int=404)}", headers=as_admin)

    assert response.status_code == 404
    assert response.json()["code"] == "user_not_found"


async def test_promotion_applies_to_the_token_already_issued(
    client: AsyncClient, as_admin: Headers, as_agent: Headers
) -> None:
    promoted = await client.put(f"/users/{MILA}/role", json={"role": "admin"}, headers=as_admin)
    created = await client.post("/users", json=NEW_AGENT, headers=as_agent)

    assert promoted.json()["role"] == "admin"
    assert created.status_code == 201


async def test_deactivated_user_is_locked_out_and_can_be_reactivated(
    client: AsyncClient, as_admin: Headers, as_agent: Headers
) -> None:
    deactivated = await client.post(f"/users/{MILA}/deactivate", headers=as_admin)
    locked_out = await client.get("/users/me", headers=as_agent)
    reactivated = await client.post(f"/users/{MILA}/reactivate", headers=as_admin)
    back_in = await client.get("/users/me", headers=as_agent)

    assert deactivated.json()["is_active"] is False
    assert locked_out.status_code == 401
    assert reactivated.json()["is_active"] is True
    assert back_in.status_code == 200


async def test_admins_cannot_lock_themselves_out(client: AsyncClient, as_admin: Headers) -> None:
    response = await client.post(f"/users/{STEFAN}/deactivate", headers=as_admin)

    assert response.status_code == 403
    assert response.json()["code"] == "own_account"


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("POST", "/users", NEW_AGENT),
        ("GET", f"/users/{REQUESTER}", None),
        ("PUT", f"/users/{REQUESTER}/role", {"role": "admin"}),
        ("POST", f"/users/{REQUESTER}/deactivate", None),
        ("POST", f"/users/{REQUESTER}/reactivate", None),
    ],
)
@pytest.mark.parametrize("user_id", [REQUESTER, MILA], ids=["customer", "agent"])
async def test_account_management_is_admin_only(
    client: AsyncClient,
    user_id: UserId,
    method: str,
    path: str,
    body: dict[str, str] | None,
) -> None:
    headers = await log_in(client, user_id)

    response = await client.request(method, path, json=body, headers=headers)

    assert response.status_code == 403
    assert response.json()["code"] == "admin_only"


async def test_staff_see_the_active_team_by_name(
    client: AsyncClient, as_agent: Headers, as_admin: Headers
) -> None:
    await client.post("/users", json=NEW_AGENT, headers=as_admin)
    created = await client.post(
        "/users",
        json={**NEW_AGENT, "email": "boris@helpdesk.test", "display_name": "Boris Atanasov"},
        headers=as_admin,
    )
    await client.post(f"/users/{created.json()['id']}/deactivate", headers=as_admin)

    response = await client.get("/users/staff", headers=as_agent)

    assert response.status_code == 200
    assert [(person["display_name"], person["role"]) for person in response.json()] == [
        ("Mila Georgieva", "agent"),
        ("Radoslav Petkov", "agent"),
        ("Stefan Kolev", "admin"),
    ]
    assert set(response.json()[0]) == {"id", "display_name", "role"}


async def test_customers_cannot_list_the_team(client: AsyncClient, as_customer: Headers) -> None:
    response = await client.get("/users/staff", headers=as_customer)

    assert response.status_code == 403
    assert response.json()["code"] == "staff_only"
