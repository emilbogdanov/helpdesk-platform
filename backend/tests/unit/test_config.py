import pytest
from pydantic import ValidationError

from helpdesk.config import Settings

VALID_ENV = {
    "HELPDESK_DATABASE_URL": "postgresql+asyncpg://helpdesk:helpdesk@db:5432/helpdesk",
    "HELPDESK_REDIS_URL": "redis://cache:6379/0",
    "HELPDESK_JWT_SECRET": "x" * 32,
}


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    for name, value in VALID_ENV.items():
        monkeypatch.setenv(name, value)
    return monkeypatch


def load_settings() -> Settings:
    # A developer's local .env must not leak into the test run.
    return Settings(_env_file=None)


def test_reads_prefixed_environment_variables(env: pytest.MonkeyPatch) -> None:
    env.setenv("HELPDESK_ACCESS_TOKEN_TTL_MINUTES", "30")

    settings = load_settings()

    assert str(settings.database_url) == VALID_ENV["HELPDESK_DATABASE_URL"]
    assert str(settings.redis_url) == VALID_ENV["HELPDESK_REDIS_URL"]
    assert settings.jwt_secret.get_secret_value() == "x" * 32
    assert settings.access_token_ttl_minutes == 30


@pytest.mark.usefixtures("env")
def test_defaults_apply_when_optional_values_are_missing() -> None:
    settings = load_settings()

    assert settings.log_level == "INFO"
    assert settings.access_token_ttl_minutes == 15


@pytest.mark.usefixtures("env")
def test_secret_is_masked_in_repr() -> None:
    assert "x" * 32 not in repr(load_settings())


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("HELPDESK_JWT_SECRET", "too-short"),
        ("HELPDESK_DATABASE_URL", "mysql://helpdesk@db/helpdesk"),
        ("HELPDESK_REDIS_URL", "http://cache:6379"),
        ("HELPDESK_ACCESS_TOKEN_TTL_MINUTES", "0"),
        ("HELPDESK_LOG_LEVEL", "VERBOSE"),
    ],
)
def test_rejects_invalid_values(env: pytest.MonkeyPatch, name: str, value: str) -> None:
    env.setenv(name, value)

    with pytest.raises(ValidationError):
        load_settings()


def test_requires_database_url(env: pytest.MonkeyPatch) -> None:
    env.delenv("HELPDESK_DATABASE_URL")

    with pytest.raises(ValidationError, match="database_url"):
        load_settings()
