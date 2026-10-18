import asyncio
import secrets

from argon2 import PasswordHasher as Argon2
from argon2.exceptions import InvalidHashError, VerificationError

from helpdesk.domain.users.values import Password


class Argon2PasswordHasher:
    def __init__(self, argon2: Argon2 | None = None) -> None:
        self._argon2 = argon2 or Argon2()
        # Hash of a secret nobody knows. Checking unknown accounts against it costs the same
        # as a real check, so timing doesn't reveal which emails are registered.
        self._decoy_hash = self._argon2.hash(secrets.token_urlsafe(32))

    # Argon2 is slow and CPU-bound on purpose. Running it in a thread keeps the event loop
    # serving other requests while one log-in is being checked.
    async def hash(self, password: Password) -> str:
        return await asyncio.to_thread(self._argon2.hash, password.value)

    async def verify(self, password_hash: str | None, candidate: str) -> bool:
        matches = await asyncio.to_thread(
            self._matches, password_hash or self._decoy_hash, candidate
        )
        return matches and password_hash is not None

    def _matches(self, password_hash: str, candidate: str) -> bool:
        try:
            return self._argon2.verify(password_hash, candidate)
        except (VerificationError, InvalidHashError):
            return False
