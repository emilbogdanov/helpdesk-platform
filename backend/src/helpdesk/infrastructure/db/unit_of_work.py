from dataclasses import dataclass
from types import TracebackType
from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm.exc import StaleDataError

from helpdesk.application.errors import ConcurrentUpdateError
from helpdesk.infrastructure.db.audit_log import SqlAuditLog
from helpdesk.infrastructure.db.repositories import SqlCommentRepository, SqlTicketRepository


@dataclass(frozen=True, slots=True)
class _Transaction:
    session: AsyncSession
    tickets: SqlTicketRepository
    comments: SqlCommentRepository
    audit: SqlAuditLog


class SqlUnitOfWork:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._transaction: _Transaction | None = None

    @property
    def tickets(self) -> SqlTicketRepository:
        return self._active().tickets

    @property
    def comments(self) -> SqlCommentRepository:
        return self._active().comments

    @property
    def audit(self) -> SqlAuditLog:
        return self._active().audit

    async def __aenter__(self) -> Self:
        if self._transaction is not None:
            raise RuntimeError("unit of work is already in use; blocks can't be nested")
        session = self._session_factory()
        self._transaction = _Transaction(
            session=session,
            tickets=SqlTicketRepository(session),
            comments=SqlCommentRepository(session),
            audit=SqlAuditLog(session),
        )
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        transaction, self._transaction = self._active(), None
        # Closing rolls back whatever was not committed.
        await transaction.session.close()

    async def commit(self) -> None:
        try:
            await self._active().session.commit()
        except StaleDataError as error:
            raise ConcurrentUpdateError from error

    def _active(self) -> _Transaction:
        if self._transaction is None:
            raise RuntimeError("unit of work used outside 'async with'")
        return self._transaction
