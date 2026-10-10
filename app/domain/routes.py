from __future__ import annotations

from app.api.migration import MigrationRegistry
from app.core.settings import Settings


def register_business_routes(
    registry: MigrationRegistry,
    settings: Settings,
) -> None:
    """Register only formal handlers backed by verified business implementations."""

    # No formal business handler is eligible until PHP parity evidence and a
    # redacted schema snapshot exist. Fixture routes are mounted separately.
    del registry, settings
