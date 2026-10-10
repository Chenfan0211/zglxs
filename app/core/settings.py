from pathlib import Path
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
    demo_login_enabled: bool = Field(
        default=False,
        validation_alias="DEMO_LOGIN_ENABLED",
    )
    demo_login_username: str | None = Field(
        default=None,
        validation_alias="DEMO_LOGIN_USERNAME",
    )
    demo_login_password: str | None = Field(
        default=None,
        validation_alias="DEMO_LOGIN_PASSWORD",
    )
    demo_captcha_code: str = Field(
        default="1111",
        validation_alias="DEMO_CAPTCHA_CODE",
    )
    demo_captcha_key: str = Field(
        default="DEMO-CAPTCHA",
        validation_alias="DEMO_CAPTCHA_KEY",
    )
    migration_organization_enabled: bool = Field(
        default=False,
        validation_alias="MIGRATION_ORGANIZATION_ENABLED",
    )
    migration_live_enabled: bool = Field(
        default=False,
        validation_alias="MIGRATION_LIVE_ENABLED",
    )
    migration_order_enabled: bool = Field(
        default=False,
        validation_alias="MIGRATION_ORDER_ENABLED",
    )
    migration_finance_enabled: bool = Field(
        default=False,
        validation_alias="MIGRATION_FINANCE_ENABLED",
    )
    migration_system_enabled: bool = Field(
        default=False,
        validation_alias="MIGRATION_SYSTEM_ENABLED",
    )
    database_url: str | None = Field(default=None, validation_alias="DATABASE_URL")
    redis_url: str | None = Field(default=None, validation_alias="REDIS_URL")
    test_database_url: str | None = Field(
        default=None,
        validation_alias="TEST_DATABASE_URL",
    )
    laike_base_url: str | None = Field(
        default="https://open.douyin.com",
        validation_alias="LAIKE_BASE_URL",
    )
    laike_orders_path: str | None = Field(
        default="/goodlife/v1/trade/order/query/",
        validation_alias="LAIKE_ORDERS_PATH",
    )
    laike_database_url: str | None = Field(
        default=None,
        validation_alias="LAIKE_DATABASE_URL",
    )
    laike_account_id: str | None = Field(
        default=None,
        validation_alias="LAIKE_ACCOUNT_ID",
    )
    laike_rpc_transit_life_account: str | None = Field(
        default=None,
        validation_alias="LAIKE_RPC_TRANSIT_LIFE_ACCOUNT",
    )
    laike_page_size: int = Field(
        default=100,
        validation_alias="LAIKE_PAGE_SIZE",
        ge=1,
        le=100,
    )
    laike_initial_lookback_seconds: int = Field(
        default=86400,
        validation_alias="LAIKE_INITIAL_LOOKBACK_SECONDS",
        gt=0,
    )
    laike_poll_interval_seconds: int = Field(
        default=300,
        validation_alias="LAIKE_POLL_INTERVAL_SECONDS",
        gt=0,
    )
    laike_api_timeout_seconds: float = Field(
        default=10.0,
        validation_alias="LAIKE_API_TIMEOUT_SECONDS",
        gt=0,
    )
    laike_query_include_sensitive_payload: bool = Field(
        default=False,
        validation_alias="LAIKE_QUERY_INCLUDE_SENSITIVE_PAYLOAD",
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
        "redis_url",
        "test_database_url",
        "laike_base_url",
        "laike_orders_path",
        "laike_database_url",
        "laike_account_id",
        "laike_rpc_transit_life_account",
        "laike_app_id",
        "laike_app_secret",
        "laike_access_token",
        "laike_webhook_secret",
        "demo_login_username",
        "demo_login_password",
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

    def formal_migration_enabled(self, module: str) -> bool:
        flags = {
            "organization": self.migration_organization_enabled,
            "live": self.migration_live_enabled,
            "order": self.migration_order_enabled,
            "finance": self.migration_finance_enabled,
            "system": self.migration_system_enabled,
        }
        try:
            return flags[module]
        except KeyError as exc:
            raise ValueError(f"unknown migration module: {module}") from exc
