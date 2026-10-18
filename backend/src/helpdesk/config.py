from typing import Literal

from pydantic import Field, PositiveInt, PostgresDsn, RedisDsn, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="HELPDESK_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    database_url: PostgresDsn
    redis_url: RedisDsn
    jwt_secret: SecretStr = Field(min_length=32)
    access_token_ttl_minutes: PositiveInt = 15
    worker_interval_seconds: PositiveInt = 60
    auto_close_after_days: PositiveInt = 7
