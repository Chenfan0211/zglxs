from typing import Literal

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
    app_name: str = Field(
        default="douyin-order-python",
        validation_alias="APP_NAME",
    )
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    environment: str = Field(
        default="development",
        validation_alias="ENVIRONMENT",
    )
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
    redis_url: str | None = Field(default=None, validation_alias="REDIS_URL")
    test_database_url: str | None = Field(
        default=None,
        validation_alias="TEST_DATABASE_URL",
    )
    laike_base_url: str | None = Field(
        default=None,
        validation_alias="LAIKE_BASE_URL",
    )
    laike_orders_path: str | None = Field(
        default=None,
        validation_alias="LAIKE_ORDERS_PATH",
    )
    laike_app_id: str | None = Field(default=None, validation_alias="LAIKE_APP_ID")
    laike_app_secret: str | None = Field(
        default=None,
        validation_alias="LAIKE_APP_SECRET",
    )
    laike_access_token: str | None = Field(
        default=None,
        validation_alias="LAIKE_ACCESS_TOKEN",
    )
    laike_webhook_secret: str | None = Field(
        default=None,
        validation_alias="LAIKE_WEBHOOK_SECRET",
    )
    laike_webhook_signature_header: str = Field(
        default="X-Laike-Signature",
        validation_alias="LAIKE_WEBHOOK_SIGNATURE_HEADER",
    )
    laike_webhook_event_id_header: str = Field(
        default="X-Laike-Event-Id",
        validation_alias="LAIKE_WEBHOOK_EVENT_ID_HEADER",
    )
    laike_sync_mode: Literal["observe", "shadow", "write"] = Field(
        default="observe",
        validation_alias="LAIKE_SYNC_MODE",
    )
    laike_webhook_enabled: bool = Field(
        default=False,
        validation_alias="LAIKE_WEBHOOK_ENABLED",
    )
    laike_reconcile_enabled: bool = Field(
        default=False,
        validation_alias="LAIKE_RECONCILE_ENABLED",
    )
    laike_write_enabled: bool = Field(
        default=False,
        validation_alias="LAIKE_WRITE_ENABLED",
    )
    laike_max_retries: int = Field(default=5, validation_alias="LAIKE_MAX_RETRIES")
    laike_overlap_seconds: int = Field(
        default=300,
        validation_alias="LAIKE_OVERLAP_SECONDS",
    )
    laike_webhook_claim_timeout_seconds: float = Field(
        default=300,
        validation_alias="LAIKE_WEBHOOK_CLAIM_TIMEOUT_SECONDS",
        gt=0,
    )

    @field_validator(
        "database_url",
        "php_baseline_url",
        "redis_url",
        "test_database_url",
        "laike_base_url",
        "laike_orders_path",
        "laike_app_id",
        "laike_app_secret",
        "laike_access_token",
        "laike_webhook_secret",
        mode="before",
    )
    @classmethod
    def blank_string_to_none(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @classmethod
    def from_env(cls) -> "Settings":
        return cls()
