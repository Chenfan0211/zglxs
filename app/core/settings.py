from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="",
        extra="ignore",
        populate_by_name=True,
    )

    app_env: str = Field(default="development", validation_alias="APP_ENV")
    database_url: str | None = Field(default=None, validation_alias="DATABASE_URL")
    php_baseline_url: str | None = Field(
        default=None,
        validation_alias="PHP_BASELINE_URL",
    )
    php_baseline_timeout_seconds: float = Field(
        default=10.0,
        validation_alias="PHP_BASELINE_TIMEOUT_SECONDS",
        gt=0,
    )

    @field_validator("database_url", "php_baseline_url", mode="before")
    @classmethod
    def blank_string_to_none(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @classmethod
    def from_env(cls) -> "Settings":
        return cls()
