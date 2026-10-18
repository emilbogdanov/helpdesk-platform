from typing import Any

import pytest
from httpx import AsyncClient

from helpdesk.api.cursors import encode_cursor
from helpdesk.application.tickets.queries import TicketCursor, TicketSort
from tests.api.conftest import Headers
from tests.unit.application.fakes import FakeUnitOfWork
from tests.unit.application.ticket_catalogue import catalogue
from tests.unit.domain.tickets.builders import OPENED_AT, OTHER_CUSTOMER, TICKET_ID


@pytest.fixture(autouse=True)
async def tickets(uow: FakeUnitOfWork) -> None:
    for ticket in catalogue():
        await uow.tickets.add(ticket, idempotency_key=None)


def numbers(body: dict[str, Any]) -> list[int]:
    return [int(item["id"].replace("-", ""), 16) for item in body["items"]]


async def test_customer_lists_their_own_tickets(client: AsyncClient, as_customer: Headers) -> None:
    response = await client.get(
        "/tickets", params={"requester": str(OTHER_CUSTOMER)}, headers=as_customer
    )

    assert response.status_code == 200
    assert numbers(response.json()) == [7, 5, 2, 1]
    assert response.json()["next_cursor"] is None


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        ({"status": ["open", "resolved"]}, [7, 6, 5, 3, 1]),
        ({"priority": ["high", "urgent"], "sort": "oldest"}, [2, 3, 7]),
        ({"assignee": "me"}, [6, 2]),
        ({"assignee": "unassigned", "status": "open"}, [7, 5, 3, 1]),
        ({"requester": str(OTHER_CUSTOMER)}, [6, 4, 3]),
        ({"sort": "recently_updated"}, [1, 6, 7, 5, 4, 3, 2]),
    ],
    ids=["statuses", "priorities", "mine", "unassigned-queue", "requester", "recently-updated"],
)
async def test_agent_filters_the_queue(
    client: AsyncClient, as_agent: Headers, params: dict[str, Any], expected: list[int]
) -> None:
    response = await client.get("/tickets", params=params, headers=as_agent)

    assert response.status_code == 200
    assert numbers(response.json()) == expected


async def test_following_next_cursor_walks_every_page(
    client: AsyncClient, as_agent: Headers
) -> None:
    seen: list[int] = []
    params: dict[str, Any] = {"sort": "oldest", "limit": 3}

    for _ in range(10):
        body = (await client.get("/tickets", params=params, headers=as_agent)).json()
        seen += numbers(body)
        if body["next_cursor"] is None:
            break
        params["cursor"] = body["next_cursor"]

    assert seen == [1, 2, 3, 4, 5, 6, 7]


@pytest.mark.parametrize(
    "cursor",
    [
        "not-base64!",
        "e30",
        encode_cursor(TicketSort.NEWEST, TicketCursor(OPENED_AT, TICKET_ID)),
        encode_cursor(TicketSort.OLDEST, TicketCursor(OPENED_AT.replace(tzinfo=None), TICKET_ID)),
    ],
    ids=["garbage", "empty-json", "issued-for-another-sort", "time-without-zone"],
)
async def test_bad_cursors_are_rejected(
    client: AsyncClient, as_agent: Headers, cursor: str
) -> None:
    response = await client.get(
        "/tickets", params={"sort": "oldest", "cursor": cursor}, headers=as_agent
    )

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_value"


@pytest.mark.parametrize(
    "params",
    [{"limit": 0}, {"limit": 101}, {"status": "escalated"}, {"sort": "priority"}, {"page": 2}],
    ids=["limit-too-small", "limit-too-big", "unknown-status", "unknown-sort", "unknown-param"],
)
async def test_malformed_queries_are_rejected(
    client: AsyncClient, as_agent: Headers, params: dict[str, Any]
) -> None:
    response = await client.get("/tickets", params=params, headers=as_agent)

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_request"


async def test_assignee_must_be_me_unassigned_or_an_id(
    client: AsyncClient, as_agent: Headers
) -> None:
    response = await client.get("/tickets", params={"assignee": "mila"}, headers=as_agent)

    assert response.status_code == 422
    assert response.json()["detail"] == "assignee must be 'me', 'unassigned' or a user id"


async def test_requires_a_token(client: AsyncClient) -> None:
    assert (await client.get("/tickets")).status_code == 401
