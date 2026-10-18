from dataclasses import dataclass

from helpdesk.domain.ids import UserId
from helpdesk.domain.roles import Role
from helpdesk.domain.users.user import User

MAX_PAGE_SIZE = 100


# Accounts are listed by name, so a page starts after the last name shown, with the id
# breaking ties between two people of the same name. See TicketCursor for why not OFFSET.
@dataclass(frozen=True, slots=True)
class UserCursor:
    display_name: str
    user_id: UserId


@dataclass(frozen=True, slots=True, kw_only=True)
class UserQuery:
    role: Role | None = None
    active: bool | None = None
    # Matched anywhere in the name or email, ignoring case.
    search: str | None = None
    after: UserCursor | None = None
    limit: int = 50


@dataclass(frozen=True, slots=True)
class UserPage:
    users: list[User]
    next_cursor: UserCursor | None
