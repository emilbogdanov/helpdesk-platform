from httpx import AsyncClient

from tests.api.conftest import Headers


async def test_admins_get_every_status_and_one_entry_per_day(
    client: AsyncClient, as_admin: Headers
) -> None:
    response = await client.get("/stats/tickets", params={"days": 7}, headers=as_admin)

    assert response.status_code == 200
    body = response.json()
    assert body["by_status"] == {
        "open": 0,
        "in_progress": 0,
        "waiting_on_customer": 0,
        "resolved": 0,
        "closed": 0,
    }
    assert len(body["days"]) == 7
    assert body["days"][-1] == {"day": "2026-10-12", "opened": 0, "resolved": 0}
    assert body["median_first_response_seconds"] is None


async def test_agents_cannot_see_the_dashboard(client: AsyncClient, as_agent: Headers) -> None:
    response = await client.get("/stats/tickets", headers=as_agent)

    assert response.status_code == 403
    assert response.json()["code"] == "admin_only"


async def test_the_window_has_limits(client: AsyncClient, as_admin: Headers) -> None:
    response = await client.get("/stats/tickets", params={"days": 365}, headers=as_admin)

    assert response.status_code == 422
