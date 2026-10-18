import asyncio
import signal
import subprocess
import sys
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import IO
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from helpdesk.cli import run_worker
from helpdesk.config import Settings
from helpdesk.domain.ids import TicketId
from helpdesk.domain.tickets.status import TicketStatus
from helpdesk.domain.tickets.ticket import Ticket
from helpdesk.domain.tickets.values import Description, Priority, Subject
from helpdesk.infrastructure.db.unit_of_work import SqlUnitOfWork
from tests.unit.domain.tickets.builders import MILA, REQUESTER

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("people")]

UNANSWERED = TicketId(UUID(int=1))
RESOLVED_LONG_AGO = TicketId(UUID(int=2))


def ticket(ticket_id: TicketId, *, status: TicketStatus, opened_days_ago: int) -> Ticket:
    # The worker reads the real clock, so these are placed relative to now.
    opened = datetime.now(UTC) - timedelta(days=opened_days_ago)
    resolved = status is TicketStatus.RESOLVED
    return Ticket(
        ticket_id=ticket_id,
        requester_id=REQUESTER,
        subject=Subject("Calendar sync stopped on Monday"),
        description=Description("Nothing new has synced since the weekend."),
        priority=Priority.NORMAL,
        status=status,
        assignee_id=MILA if resolved else None,
        created_at=opened,
        updated_at=opened,
        resolved_at=opened + timedelta(hours=1) if resolved else None,
        closed_at=None,
        first_responded_at=opened + timedelta(minutes=30) if resolved else None,
        sla_breached_at=None,
    )


@pytest.fixture
def settings(
    database_url: str, redis_url: str, engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> Settings:
    # `engine` is requested so its teardown empties the tables afterwards.
    monkeypatch.setenv("HELPDESK_DATABASE_URL", database_url)
    monkeypatch.setenv("HELPDESK_REDIS_URL", redis_url)
    monkeypatch.setenv("HELPDESK_JWT_SECRET", "integration-test-signing-secret-000000")
    return Settings(_env_file=None)


async def test_one_worker_pass_flags_and_closes_through_the_real_stack(
    uow: SqlUnitOfWork, settings: Settings
) -> None:
    async with uow:
        await uow.tickets.add(
            ticket(UNANSWERED, status=TicketStatus.OPEN, opened_days_ago=2), idempotency_key=None
        )
        await uow.tickets.add(
            ticket(RESOLVED_LONG_AGO, status=TicketStatus.RESOLVED, opened_days_ago=9),
            idempotency_key=None,
        )
        await uow.commit()
    stop = asyncio.Event()
    worker = asyncio.create_task(run_worker(settings, stop))

    unanswered, resolved = await _poll_until_processed(uow)
    stop.set()
    await asyncio.wait_for(worker, timeout=5)

    assert unanswered.sla_breached_at is not None
    assert resolved.status is TicketStatus.CLOSED


async def _poll_until_processed(uow: SqlUnitOfWork) -> tuple[Ticket, Ticket]:
    for _ in range(100):
        async with uow:
            unanswered = await uow.tickets.get(UNANSWERED)
            resolved = await uow.tickets.get(RESOLVED_LONG_AGO)
        assert unanswered is not None
        assert resolved is not None
        if unanswered.sla_breached_at and resolved.status is TicketStatus.CLOSED:
            return unanswered, resolved
        await asyncio.sleep(0.05)
    pytest.fail("the worker did not process both tickets within 5 seconds")


@pytest.mark.skipif(sys.platform == "win32", reason="Windows has no SIGTERM to send")
def test_the_worker_command_stops_cleanly_on_sigterm(settings: Settings) -> None:
    worker = subprocess.Popen(
        [sys.executable, "-c", "from helpdesk.cli import main; raise SystemExit(main(['worker']))"],
        stderr=subprocess.PIPE,
        text=True,
    )
    assert worker.stderr is not None
    started = list(_lines_until(worker.stderr, "worker started"))

    worker.send_signal(signal.SIGTERM)
    _, remaining = worker.communicate(timeout=10)

    assert started[-1].endswith("worker started; a pass every 0:01:00")
    assert worker.returncode == 0
    assert "worker stopped" in remaining


def _lines_until(stream: IO[str], text: str) -> Iterator[str]:
    for line in stream:
        yield line.rstrip()
        if text in line:
            return
    pytest.fail(f"the worker exited before logging {text!r}")
