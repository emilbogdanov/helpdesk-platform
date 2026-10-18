from uuid import UUID

import pytest

from helpdesk.application.actor import Actor
from helpdesk.application.errors import StaffOnlyError
from helpdesk.application.users.people import PeopleDirectory
from helpdesk.domain.ids import UserId
from helpdesk.domain.roles import Role
from tests.unit.application.fakes import FakeUnitOfWork
from tests.unit.domain.tickets.builders import MILA, REQUESTER, STEFAN
from tests.unit.domain.users.builders import everyone


async def directory() -> PeopleDirectory:
    uow = FakeUnitOfWork()
    for person in everyone():
        await uow.users.add(person)
    return PeopleDirectory(uow)


async def test_looks_up_each_person_once_however_often_they_appear() -> None:
    people = await (await directory()).find([REQUESTER, MILA, REQUESTER, MILA])

    assert {user_id: str(user.display_name) for user_id, user in people.items()} == {
        REQUESTER: "Petar Ivanov",
        MILA: "Mila Georgieva",
    }


async def test_an_empty_lookup_finds_nobody() -> None:
    assert await (await directory()).find([]) == {}


async def test_unknown_ids_are_left_out() -> None:
    people = await (await directory()).find([UserId(UUID(int=404))])

    assert people == {}


async def test_staff_list_the_team() -> None:
    staff = await (await directory()).staff(Actor(MILA, Role.AGENT))

    assert [person.id for person in staff] == [MILA, STEFAN]


async def test_customers_cannot_list_the_team() -> None:
    with pytest.raises(StaffOnlyError):
        await (await directory()).staff(Actor(REQUESTER, Role.CUSTOMER))
