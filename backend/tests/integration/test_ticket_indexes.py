from typing import Any

import pytest
from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncEngine

from helpdesk.application.tickets.queries import TicketCursor, TicketQuery, TicketSort
from helpdesk.domain.tickets.status import TicketStatus
from helpdesk.domain.tickets.values import Priority
from helpdesk.infrastructure.db.repositories import (
    awaiting_first_response,
    resolved_before,
    ticket_search,
)
from tests.unit.domain.tickets.builders import MILA, OPENED_AT, REQUESTER, TICKET_ID

pytestmark = pytest.mark.integration

CURSOR = TicketCursor(OPENED_AT, TICKET_ID)


async def plan(engine: AsyncEngine, statement: Select[Any]) -> str:
    sql = statement.compile(dialect=engine.dialect, compile_kwargs={"literal_binds": True})
    async with engine.connect() as connection:
        # A test table is tiny, so Postgres would rightly scan it whole. Taking that option
        # away shows which index it would use once the table is big enough to matter.
        await connection.exec_driver_sql("SET LOCAL enable_seqscan = off")
        rows = await connection.exec_driver_sql(f"EXPLAIN {sql}")
        return "\n".join(row[0] for row in rows)


@pytest.mark.parametrize(
    ("query", "index"),
    [
        (TicketQuery(), "ix_tickets_created_at_id"),
        (TicketQuery(sort=TicketSort.RECENTLY_UPDATED), "ix_tickets_updated_at_id"),
        (TicketQuery(requester_id=REQUESTER), "ix_tickets_requester_id_created_at_id"),
        (
            TicketQuery(requester_id=REQUESTER, after=CURSOR),
            "ix_tickets_requester_id_created_at_id",
        ),
        (
            TicketQuery(statuses=frozenset({TicketStatus.OPEN}), sort=TicketSort.OLDEST),
            "ix_tickets_status_created_at_id",
        ),
        (
            TicketQuery(assignee=MILA, sort=TicketSort.RECENTLY_UPDATED),
            "ix_tickets_assignee_id_updated_at_id",
        ),
    ],
    ids=[
        "everything-newest",
        "everything-recently-updated",
        "my-tickets",
        "my-tickets-next-page",
        "queue-by-status",
        "assigned-to-me",
    ],
)
async def test_each_list_view_reads_its_index(
    engine: AsyncEngine, query: TicketQuery, index: str
) -> None:
    assert index in await plan(engine, ticket_search(query))


async def test_the_overdue_sweep_reads_its_partial_index(engine: AsyncEngine) -> None:
    opened_before = dict.fromkeys(Priority, OPENED_AT)

    query_plan = await plan(engine, awaiting_first_response(opened_before, limit=200))

    assert "ix_tickets_awaiting_first_response" in query_plan


async def test_the_auto_close_sweep_reads_its_partial_index(engine: AsyncEngine) -> None:
    query_plan = await plan(engine, resolved_before(OPENED_AT, limit=200))

    assert "ix_tickets_resolved_at" in query_plan
