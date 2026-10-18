from collections.abc import Iterable

from helpdesk.application.actor import Actor
from helpdesk.application.ports import UnitOfWork
from helpdesk.application.tickets.access import require_staff
from helpdesk.domain.ids import UserId
from helpdesk.domain.users.user import User


# Names to show next to tickets and comments. There is deliberately no permission check:
# callers only pass the requester, assignee and authors of records the actor was already
# allowed to read, and the API exposes nothing beyond a name and a role from the result.
class PeopleDirectory:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def find(self, user_ids: Iterable[UserId]) -> dict[UserId, User]:
        wanted = set(user_ids)
        if not wanted:
            return {}
        async with self._uow as uow:
            return {user.id: user for user in await uow.users.get_many(wanted)}

    # Who a ticket can be assigned to. Customers have no use for the staff list.
    async def staff(self, actor: Actor) -> list[User]:
        require_staff(actor, "see who is on the team")
        async with self._uow as uow:
            return await uow.users.find_staff()
