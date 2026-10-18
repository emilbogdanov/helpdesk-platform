from datetime import UTC, datetime, timedelta

import jwt
import pytest

from helpdesk.application.errors import InvalidTokenError
from helpdesk.application.ports import TokenClaims, TokenCodec
from helpdesk.infrastructure.security.tokens import JwtTokenCodec
from tests.unit.domain.tickets.builders import MILA

SECRET = "f3Qm9vX2-test-only-signing-secret-0042"
CLAIMS = TokenClaims(user_id=MILA, expires_at=datetime(2026, 10, 12, 9, 29, tzinfo=UTC))


@pytest.fixture
def codec() -> TokenCodec:
    return JwtTokenCodec(SECRET)


def test_round_trip(codec: TokenCodec) -> None:
    assert codec.decode(codec.encode(CLAIMS)) == CLAIMS


def test_expired_tokens_still_decode(codec: TokenCodec) -> None:
    # Expiry is judged by AuthService against its clock, not by the codec.
    past = TokenClaims(user_id=MILA, expires_at=datetime(2001, 1, 1, tzinfo=UTC))

    assert codec.decode(codec.encode(past)) == past


def test_rejects_a_token_signed_with_another_secret(codec: TokenCodec) -> None:
    forged = JwtTokenCodec("someone-elses-secret-of-decent-length").encode(CLAIMS)

    with pytest.raises(InvalidTokenError):
        codec.decode(forged)


def test_rejects_a_token_with_a_tampered_payload(codec: TokenCodec) -> None:
    header, _, signature = codec.encode(CLAIMS).split(".")
    other_payload = jwt.encode(
        {"sub": "7e9a1c3b-2d4f-4a6e-9c8b-0f1e2d3c4b5a", "exp": 1_900_000_000},
        "irrelevant-secret-padding-to-32-bytes",
        algorithm="HS256",
    ).split(".")[1]

    with pytest.raises(InvalidTokenError):
        codec.decode(f"{header}.{other_payload}.{signature}")


def test_rejects_unsigned_tokens(codec: TokenCodec) -> None:
    unsigned = jwt.encode({"sub": str(MILA), "exp": 1_900_000_000}, key=None, algorithm="none")

    with pytest.raises(InvalidTokenError):
        codec.decode(unsigned)


@pytest.mark.parametrize(
    "payload",
    [
        {"exp": 1_900_000_000},
        {"sub": str(MILA)},
        {"sub": "not-a-uuid", "exp": 1_900_000_000},
        {"sub": str(MILA), "exp": "tomorrow"},
    ],
    ids=["no-subject", "no-expiry", "subject-not-a-uuid", "expiry-not-a-number"],
)
def test_rejects_malformed_claims(codec: TokenCodec, payload: dict[str, object]) -> None:
    with pytest.raises(InvalidTokenError):
        codec.decode(jwt.encode(payload, SECRET, algorithm="HS256"))


@pytest.mark.parametrize("token", ["", "abc", "a.b.c"])
def test_rejects_garbage(codec: TokenCodec, token: str) -> None:
    with pytest.raises(InvalidTokenError):
        codec.decode(token)


def test_expiry_is_kept_to_the_second(codec: TokenCodec) -> None:
    claims = TokenClaims(user_id=MILA, expires_at=CLAIMS.expires_at + timedelta(milliseconds=750))

    assert codec.decode(codec.encode(claims)).expires_at == CLAIMS.expires_at
