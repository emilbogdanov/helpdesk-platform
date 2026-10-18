import logging
from datetime import timedelta

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from helpdesk.api.app import create_app
from helpdesk.api.container import Container
from helpdesk.config import Settings
from helpdesk.infrastructure.clock import SystemClock
from helpdesk.infrastructure.db.unit_of_work import SqlUnitOfWork
from helpdesk.infrastructure.security.passwords import Argon2PasswordHasher
from helpdesk.infrastructure.security.tokens import JwtTokenCodec

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


def app() -> FastAPI:
    # Run with: uvicorn --factory helpdesk.main:app
    settings = Settings()
    logging.basicConfig(
        level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    return create_app(build_container(settings))
