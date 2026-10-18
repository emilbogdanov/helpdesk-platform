from dataclasses import dataclass

from helpdesk.domain.ids import UserId
from helpdesk.domain.roles import Role


# The authenticated caller, as resolved from the access token by the API layer.
@dataclass(frozen=True, slots=True)
class Actor:
    user_id: UserId
    role: Role
