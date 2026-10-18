from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import uuid4

from helpdesk.application.actor import Actor
from helpdesk.application.errors import InvalidCredentialsError, InvalidTokenError
from helpdesk.application.ports import (
    Clock,
    PasswordHasher,
    TokenClaims,
    TokenCodec,
    UnitOfWork,
)
from helpdesk.domain.ids import UserId
from helpdesk.domain.roles import Role
from helpdesk.domain.users.user import User
from helpdesk.domain.users.values import DisplayName, EmailAddress, Password


@dataclass(frozen=True, slots=True)
class AccessToken:
    token: str
    expires_at: datetime


class AuthService:
    def __init__(
        self,
        uow: UnitOfWork,
        hasher: PasswordHasher,
        tokens: TokenCodec,
        clock: Clock,
        *,
        token_ttl: timedelta,
    ) -> None:
        self._uow = uow
        self._hasher = hasher
        self._tokens = tokens
        self._clock = clock
        self._token_ttl = token_ttl

    async def sign_up(
        self, *, email: EmailAddress, display_name: DisplayName, password: Password
    ) -> User:
        # Hashing is deliberately slow, so it happens before the transaction opens.
        password_hash = await self._hasher.hash(password)
        user = User.register(
            user_id=UserId(uuid4()),
            email=email,
            display_name=display_name,
            role=Role.CUSTOMER,
            password_hash=password_hash,
            at=self._clock.now(),
        )
        async with self._uow as uow:
            await uow.users.add(user)
            await uow.commit()
        return user

    async def log_in(self, email: EmailAddress, password: str) -> AccessToken:
        async with self._uow as uow:
            user = await uow.users.get_by_email(email)
        matches = await self._hasher.verify(
            user.password_hash if user is not None else None, password
        )
        if user is None or not matches or not user.is_active:
            raise InvalidCredentialsError
        expires_at = self._clock.now() + self._token_ttl
        return AccessToken(
            token=self._tokens.encode(TokenClaims(user_id=user.id, expires_at=expires_at)),
            expires_at=expires_at,
        )

    async def authenticate(self, token: str) -> Actor:
        claims = self._tokens.decode(token)
        if claims.expires_at <= self._clock.now():
            raise InvalidTokenError("access token has expired")
        # Loaded on every request so a deactivation or role change applies immediately,
        # not when the token runs out.
        async with self._uow as uow:
            user = await uow.users.get(claims.user_id)
        if user is None or not user.is_active:
            raise InvalidTokenError
        return Actor(user_id=user.id, role=user.role)
