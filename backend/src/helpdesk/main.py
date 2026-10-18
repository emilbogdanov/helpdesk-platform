import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import timedelta

from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from helpdesk.api.app import create_app
from helpdesk.api.container import Container
from helpdesk.application.tickets.upkeep import TicketUpkeep
from helpdesk.config import Settings
from helpdesk.domain.tickets.sla import DEFAULT_FIRST_RESPONSE_TARGETS
from helpdesk.infrastructure.clock import SystemClock
from helpdesk.infrastructure.db.unit_of_work import SqlUnitOfWork
from helpdesk.infrastructure.redis_lease import RedisLease
from helpdesk.infrastructure.security.passwords import Argon2PasswordHasher
from helpdesk.infrastructure.security.tokens import JwtTokenCodec
from helpdesk.worker import Job, Worker

# asyncpg timeouts, in seconds: fail fast when the database is unreachable or a query hangs,
# instead of holding the request (and a pool connection) open indefinitely.
_CONNECT_TIMEOUT = 5
_QUERY_TIMEOUT = 15


def build_container(settings: Settings) -> Container:
    engine = create_async_engine(
        str(settings.database_url),
        pool_pre_ping=True,
        connect_args={"timeout": _CONNECT_TIMEOUT, "command_timeout": _QUERY_TIMEOUT},
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    return Container(
        uow_factory=lambda: SqlUnitOfWork(session_factory),
        hasher=Argon2PasswordHasher(),
        tokens=JwtTokenCodec(settings.jwt_secret.get_secret_value()),
        clock=SystemClock(),
        token_ttl=timedelta(minutes=settings.access_token_ttl_minutes),
        close=engine.dispose,
    )


def configure_logging(settings: Settings) -> None:
    logging.basicConfig(
        level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )


def app() -> FastAPI:
    # Run with: uvicorn --factory helpdesk.main:app
    settings = Settings()
    configure_logging(settings)
    return create_app(build_container(settings))


@dataclass(frozen=True, slots=True)
class WorkerProcess:
    worker: Worker
    close: Callable[[], Awaitable[None]]


def build_worker(settings: Settings) -> WorkerProcess:
    container = build_container(settings)
    redis = Redis.from_url(
        str(settings.redis_url),
        socket_connect_timeout=_CONNECT_TIMEOUT,
        socket_timeout=_QUERY_TIMEOUT,
    )
    upkeep = TicketUpkeep(
        container.uow_factory(),
        container.clock,
        targets=DEFAULT_FIRST_RESPONSE_TARGETS,
        close_resolved_after=timedelta(days=settings.auto_close_after_days),
    )
    interval = timedelta(seconds=settings.worker_interval_seconds)
    worker = Worker(
        [
            Job("flag-overdue-first-responses", upkeep.flag_overdue_first_responses),
            Job("close-resolved-tickets", upkeep.close_resolved_tickets),
        ],
        # Several passes' worth, so only a worker that died mid-pass ever lets it lapse.
        RedisLease(redis, "helpdesk:worker:lease", ttl=interval * 5),
        every=interval,
    )

    async def close() -> None:
        await redis.aclose()
        await container.close()

    return WorkerProcess(worker=worker, close=close)
