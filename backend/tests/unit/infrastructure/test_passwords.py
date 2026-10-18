import pytest
from argon2 import PasswordHasher as Argon2

from helpdesk.application.ports import PasswordHasher
from helpdesk.domain.users.values import Password
from helpdesk.infrastructure.security.passwords import Argon2PasswordHasher

PASSWORD = "plum-orchard-41"


@pytest.fixture(scope="module")
def hasher() -> PasswordHasher:
    # Minimum cost: these tests check behaviour, not how hard the hash is to brute-force.
    return Argon2PasswordHasher(Argon2(time_cost=1, memory_cost=8, parallelism=1))


async def test_hash_is_argon2id(hasher: PasswordHasher) -> None:
    assert (await hasher.hash(Password(PASSWORD))).startswith("$argon2id$")


async def test_same_password_hashes_differently_each_time(hasher: PasswordHasher) -> None:
    assert await hasher.hash(Password(PASSWORD)) != await hasher.hash(Password(PASSWORD))


async def test_verify_accepts_the_right_password(hasher: PasswordHasher) -> None:
    password_hash = await hasher.hash(Password(PASSWORD))

    assert await hasher.verify(password_hash, PASSWORD)


@pytest.mark.parametrize("candidate", ["plum-orchard-42", "", "PLUM-ORCHARD-41"])
async def test_verify_rejects_anything_else(hasher: PasswordHasher, candidate: str) -> None:
    password_hash = await hasher.hash(Password(PASSWORD))

    assert not await hasher.verify(password_hash, candidate)


async def test_unknown_account_never_matches(hasher: PasswordHasher) -> None:
    assert not await hasher.verify(None, PASSWORD)


async def test_corrupted_hash_never_matches(hasher: PasswordHasher) -> None:
    assert not await hasher.verify("$argon2id$not-a-real-hash", PASSWORD)
