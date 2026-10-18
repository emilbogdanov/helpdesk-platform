from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import timedelta

from helpdesk.application.ports import Clock, PasswordHasher, TokenCodec, UnitOfWork
from helpdesk.application.users.auth_service import AuthService
from helpdesk.application.users.user_service import UserService


async def _nothing_to_close() -> None:
    return None


# Everything a request needs, built once at start-up. Services are cheap and get a fresh
# unit of work per request, so no transaction is ever shared between two requests.
@dataclass(frozen=True, slots=True, kw_only=True)
class Container:
    uow_factory: Callable[[], UnitOfWork]
    hasher: PasswordHasher
    tokens: TokenCodec
    clock: Clock
    token_ttl: timedelta
    close: Callable[[], Awaitable[None]] = _nothing_to_close

    def auth(self) -> AuthService:
        return AuthService(
            self.uow_factory(), self.hasher, self.tokens, self.clock, token_ttl=self.token_ttl
        )

    def users(self) -> UserService:
        return UserService(self.uow_factory(), self.hasher, self.clock)
