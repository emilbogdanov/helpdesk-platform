from datetime import UTC, datetime
from uuid import UUID

import jwt

from helpdesk.application.errors import InvalidTokenError
from helpdesk.application.ports import TokenClaims
from helpdesk.domain.ids import UserId

_ALGORITHM = "HS256"


class JwtTokenCodec:
    def __init__(self, secret: str) -> None:
        self._secret = secret

    def encode(self, claims: TokenClaims) -> str:
        return jwt.encode(
            {"sub": str(claims.user_id), "exp": int(claims.expires_at.timestamp())},
            self._secret,
            algorithm=_ALGORITHM,
        )

    def decode(self, token: str) -> TokenClaims:
        try:
            payload = jwt.decode(
                token,
                self._secret,
                # Pinned so a token can't pick its own algorithm (e.g. "none").
                algorithms=[_ALGORITHM],
                # AuthService checks expiry against the injected clock.
                options={"require": ["sub", "exp"], "verify_exp": False},
            )
            return TokenClaims(
                user_id=UserId(UUID(payload["sub"])),
                expires_at=datetime.fromtimestamp(payload["exp"], tz=UTC),
            )
        except (jwt.PyJWTError, ValueError, TypeError) as error:
            raise InvalidTokenError from error
