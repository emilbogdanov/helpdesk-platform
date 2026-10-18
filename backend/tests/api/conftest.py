from collections.abc import AsyncIterator
from datetime import timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from helpdesk.api.app import create_app
from helpdesk.api.container import Container
from helpdesk.domain.ids import UserId
from tests.unit.application.fakes import (
    FakePasswordHasher,
    FakeTokenCodec,
    FakeUnitOfWork,
    FixedClock,
)
from tests.unit.domain.tickets.builders import MILA, OPENED_AT, OTHER_CUSTOMER, REQUESTER, STEFAN
from tests.unit.domain.users.builders import EMAILS, everyone

PASSWORD = "plum-orchard-41"
Headers = dict[str, str]


@pytest.fixture
async def uow() -> FakeUnitOfWork:
    uow = FakeUnitOfWork()
    for person in everyone(password_hash=f"hashed:{PASSWORD}"):
        await uow.users.add(person)
    return uow


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(OPENED_AT)


@pytest.fixture
async def client(uow: FakeUnitOfWork, clock: FixedClock) -> AsyncIterator[AsyncClient]:
    container = Container(
        # One shared fake stands in for the database across requests.
        uow_factory=lambda: uow,
        hasher=FakePasswordHasher(),
        tokens=FakeTokenCodec(),
        clock=clock,
        token_ttl=timedelta(minutes=15),
    )
    transport = ASGITransport(app=create_app(container))
    async with AsyncClient(transport=transport, base_url="http://helpdesk.test") as client:
        yield client


async def log_in(client: AsyncClient, user_id: UserId) -> Headers:
    response = await client.post(
        "/auth/token", json={"email": EMAILS[user_id], "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
async def as_customer(client: AsyncClient) -> Headers:
    return await log_in(client, REQUESTER)


@pytest.fixture
async def as_other_customer(client: AsyncClient) -> Headers:
    return await log_in(client, OTHER_CUSTOMER)


@pytest.fixture
async def as_agent(client: AsyncClient) -> Headers:
    return await log_in(client, MILA)


@pytest.fixture
async def as_admin(client: AsyncClient) -> Headers:
    return await log_in(client, STEFAN)
