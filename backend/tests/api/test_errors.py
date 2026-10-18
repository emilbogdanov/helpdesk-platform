from datetime import timedelta
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from helpdesk.api.app import create_app
from helpdesk.api.container import Container
from helpdesk.api.errors import ERROR_RESPONSES, register_error_handlers
from helpdesk.application.errors import ApplicationError
from helpdesk.domain.errors import DomainError
from tests.unit.application.fakes import (
    FakePasswordHasher,
    FakeTokenCodec,
    FakeUnitOfWork,
    FixedClock,
)
from tests.unit.domain.tickets.builders import OPENED_AT


def all_subclasses(base: type[Exception]) -> set[type[Exception]]:
    found: set[type[Exception]] = set()
    for subclass in base.__subclasses__():
        found |= {subclass} | all_subclasses(subclass)
    return found


def test_every_business_error_has_an_http_response() -> None:
    errors = {
        error
        for error in all_subclasses(DomainError) | all_subclasses(ApplicationError)
        if error.__module__.startswith("helpdesk.")
    }

    assert errors - set(ERROR_RESPONSES) == set()


def test_codes_are_unique() -> None:
    codes = [code for _, code in ERROR_RESPONSES.values()]

    assert len(codes) == len(set(codes))


class NewlyAddedError(DomainError):
    pass


def failing_app(error: Exception) -> FastAPI:
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/boom")
    async def boom() -> None:
        raise error

    return app


@pytest.mark.parametrize(
    "error",
    [NewlyAddedError("internal detail"), RuntimeError("internal detail")],
    ids=["unmapped-business-error", "plain-bug"],
)
async def test_bugs_get_a_500_in_the_usual_shape_without_their_message(error: Exception) -> None:
    transport = ASGITransport(app=failing_app(error), raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/boom")

    assert response.status_code == 500
    assert response.json() == {"detail": "internal error", "code": "internal"}


async def test_bugs_still_reach_the_server_with_their_traceback() -> None:
    transport = ASGITransport(app=failing_app(NewlyAddedError("internal detail")))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with pytest.raises(NewlyAddedError, match="internal detail"):
            await client.get("/boom")


async def test_malformed_requests_use_the_same_error_shape(client: AsyncClient) -> None:
    response = await client.post(
        "/auth/sign-up", json={"email": "ana@brightloop.io", "password": "quiet-harbour-19"}
    )

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "invalid_request"
    assert body["detail"] == "request is malformed"
    assert [error["loc"] for error in body["errors"]] == [["body", "display_name"]]


def container(**overrides: object) -> Container:
    parts: dict[str, Any] = {
        "uow_factory": FakeUnitOfWork,
        "hasher": FakePasswordHasher(),
        "tokens": FakeTokenCodec(),
        "clock": FixedClock(OPENED_AT),
        "token_ttl": timedelta(minutes=15),
    }
    return Container(**(parts | overrides))


async def test_shutdown_releases_what_the_container_holds() -> None:
    closed = False

    async def close() -> None:
        nonlocal closed
        closed = True

    app = create_app(container(close=close))

    async with app.router.lifespan_context(app):
        assert not closed
    assert closed


async def test_shutdown_with_nothing_to_release() -> None:
    app = create_app(container())

    async with app.router.lifespan_context(app):
        pass
