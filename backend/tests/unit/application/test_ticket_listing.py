from dataclasses import replace

import pytest

from helpdesk.application.actor import Actor
from helpdesk.application.tickets.queries import (
    UNASSIGNED,
    TicketPage,
    TicketQuery,
    TicketSort,
)
from helpdesk.application.tickets.ticket_service import TicketService
from helpdesk.domain.errors import InvalidValueError
from helpdesk.domain.roles import Role
from helpdesk.domain.tickets.status import TicketStatus
from helpdesk.domain.tickets.values import Priority
from tests.unit.application.fakes import FakeUnitOfWork, FixedClock
from tests.unit.application.ticket_catalogue import catalogue, numbers
from tests.unit.domain.tickets.builders import MILA, OPENED_AT, OTHER_CUSTOMER, REQUESTER

CUSTOMER = Actor(REQUESTER, Role.CUSTOMER)
AGENT = Actor(MILA, Role.AGENT)


@pytest.fixture
async def service() -> TicketService:
    uow = FakeUnitOfWork()
    for ticket in catalogue():
        await uow.tickets.add(ticket, idempotency_key=None)
    return TicketService(uow, FixedClock(OPENED_AT))


async def all_pages(service: TicketService, actor: Actor, query: TicketQuery) -> list[TicketPage]:
    pages = [await service.list_tickets(actor, query)]
    while (cursor := pages[-1].next_cursor) is not None:
        pages.append(await service.list_tickets(actor, replace(query, after=cursor)))
    return pages


class TestVisibility:
    async def test_customers_see_only_their_own_tickets(self, service: TicketService) -> None:
        page = await service.list_tickets(CUSTOMER, TicketQuery())

        assert numbers(page.tickets) == [7, 5, 2, 1]

    async def test_customers_cannot_ask_for_someone_elses_tickets(
        self, service: TicketService
    ) -> None:
        page = await service.list_tickets(CUSTOMER, TicketQuery(requester_id=OTHER_CUSTOMER))

        assert numbers(page.tickets) == [7, 5, 2, 1]

    async def test_staff_see_everyone(self, service: TicketService) -> None:
        page = await service.list_tickets(AGENT, TicketQuery())

        assert numbers(page.tickets) == [7, 6, 5, 4, 3, 2, 1]


class TestFilters:
    @pytest.mark.parametrize(
        ("query", "expected"),
        [
            (TicketQuery(statuses=frozenset({TicketStatus.OPEN})), [7, 5, 3, 1]),
            (
                TicketQuery(
                    statuses=frozenset({TicketStatus.IN_PROGRESS, TicketStatus.WAITING_ON_CUSTOMER})
                ),
                [4, 2],
            ),
            (TicketQuery(priorities=frozenset({Priority.HIGH, Priority.URGENT})), [7, 3, 2]),
            (TicketQuery(assignee=MILA), [6, 2]),
            (TicketQuery(assignee=UNASSIGNED), [7, 5, 3, 1]),
            (TicketQuery(requester_id=OTHER_CUSTOMER), [6, 4, 3]),
            (
                TicketQuery(
                    statuses=frozenset({TicketStatus.OPEN}),
                    priorities=frozenset({Priority.HIGH}),
                    requester_id=REQUESTER,
                ),
                [7],
            ),
        ],
        ids=[
            "one-status",
            "several-statuses",
            "priorities",
            "assignee",
            "unassigned",
            "requester",
            "combined",
        ],
    )
    async def test_staff_filters(
        self, service: TicketService, query: TicketQuery, expected: list[int]
    ) -> None:
        assert numbers((await service.list_tickets(AGENT, query)).tickets) == expected


class TestSorting:
    @pytest.mark.parametrize(
        ("sort", "expected"),
        [
            (TicketSort.NEWEST, [7, 6, 5, 4, 3, 2, 1]),
            (TicketSort.OLDEST, [1, 2, 3, 4, 5, 6, 7]),
            (TicketSort.RECENTLY_UPDATED, [1, 6, 7, 5, 4, 3, 2]),
        ],
    )
    async def test_orders(
        self, service: TicketService, sort: TicketSort, expected: list[int]
    ) -> None:
        assert (
            numbers((await service.list_tickets(AGENT, TicketQuery(sort=sort))).tickets) == expected
        )


class TestPagination:
    @pytest.mark.parametrize("sort", list(TicketSort))
    async def test_pages_cover_every_ticket_exactly_once(
        self, service: TicketService, sort: TicketSort
    ) -> None:
        everything = await service.list_tickets(AGENT, TicketQuery(sort=sort))

        pages = await all_pages(service, AGENT, TicketQuery(sort=sort, limit=2))

        assert [len(page.tickets) for page in pages] == [2, 2, 2, 1]
        assert [n for page in pages for n in numbers(page.tickets)] == numbers(everything.tickets)

    async def test_full_last_page_has_no_cursor(self, service: TicketService) -> None:
        page = await service.list_tickets(CUSTOMER, TicketQuery(limit=4))

        assert len(page.tickets) == 4
        assert page.next_cursor is None

    async def test_pages_follow_the_filter(self, service: TicketService) -> None:
        query = TicketQuery(
            statuses=frozenset({TicketStatus.OPEN}), sort=TicketSort.OLDEST, limit=3
        )

        pages = await all_pages(service, AGENT, query)

        assert [numbers(page.tickets) for page in pages] == [[1, 3, 5], [7]]

    @pytest.mark.parametrize("limit", [0, 101])
    async def test_page_size_is_bounded(self, service: TicketService, limit: int) -> None:
        with pytest.raises(InvalidValueError, match="page size must be 1 to 100"):
            await service.list_tickets(AGENT, TicketQuery(limit=limit))
