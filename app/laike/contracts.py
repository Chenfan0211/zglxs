from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class LaikePage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[dict[str, Any]]
    next_cursor: str | None = None
    has_more: bool = False


class WebhookVerification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verified: bool
    reason: str | None = None


class NormalizedOrder(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_id: str | None = None
    status: str | None = None
    created_at: str | None = None
    payload_json: dict[str, Any] = Field(default_factory=dict)

    def log_metadata(self) -> dict[str, Any]:
        return {"order_id": self.order_id, "has_payload": bool(self.payload_json)}


class SyncResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    success: bool
    processed_count: int = 0
    failed_count: int = 0
