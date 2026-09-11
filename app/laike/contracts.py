from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol, runtime_checkable

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    PrivateAttr,
    model_validator,
)


class LaikePage(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        populate_by_name=True,
    )

    items: list[Mapping[str, Any]]
    next_cursor: str | None = None
    raw: Mapping[str, Any] = Field(default_factory=dict)
    has_more: bool | None = None

    _legacy_shape: bool = PrivateAttr(default=False)

    def __init__(self, **data: Any) -> None:
        legacy_shape = "has_more" in data and "raw" not in data
        super().__init__(**data)
        self._legacy_shape = legacy_shape

    @model_validator(mode="after")
    def derive_has_more(self) -> LaikePage:
        if self.has_more is None:
            object.__setattr__(self, "has_more", bool(self.next_cursor))
        return self

    def model_dump(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        result = super().model_dump(*args, **kwargs)
        if self._legacy_shape:
            result.pop("raw", None)
        else:
            result.pop("has_more", None)
        return result


class WebhookVerification(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        populate_by_name=True,
    )

    valid: bool = Field(validation_alias=AliasChoices("valid", "verified"))
    event_id: str | None = None
    source: str = "laike"
    reason: str | None = None

    _legacy_shape: bool = PrivateAttr(default=False)

    def __init__(self, **data: Any) -> None:
        legacy_shape = "verified" in data and "valid" not in data
        super().__init__(**data)
        self._legacy_shape = legacy_shape

    @property
    def verified(self) -> bool:
        return self.valid

    @property
    def legacy_compatibility(self) -> bool:
        return self._legacy_shape

    def model_dump(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        result = super().model_dump(*args, **kwargs)
        if self._legacy_shape:
            return {"verified": self.valid, "reason": self.reason}
        return result

    def __await__(self):
        async def return_self() -> WebhookVerification:
            return self

        return return_self().__await__()


class NormalizedOrder(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        populate_by_name=True,
    )

    order_id: str | None = None
    subject_id: str | None = None
    product_id: str | None = None
    status: str | None = None
    original_created_at: Any = None
    normalized_created_at: str | None = None
    original_updated_at: Any = None
    normalized_updated_at: str | None = None
    raw_payload: Mapping[str, Any] = Field(
        default_factory=dict,
        validation_alias=AliasChoices("raw_payload", "payload_json"),
    )

    _legacy_shape: bool = PrivateAttr(default=False)

    def __init__(self, **data: Any) -> None:
        legacy_shape = "created_at" in data or "payload_json" in data
        if "created_at" in data and "original_created_at" not in data:
            data["original_created_at"] = data.pop("created_at")
        if "payload_json" in data and "raw_payload" not in data:
            data["raw_payload"] = data.pop("payload_json")
        super().__init__(**data)
        self._legacy_shape = legacy_shape

    @property
    def created_at(self) -> Any:
        return self.original_created_at

    @property
    def payload_json(self) -> Mapping[str, Any]:
        return self.raw_payload

    def model_dump(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        result = super().model_dump(*args, **kwargs)
        if self._legacy_shape:
            return {
                "order_id": self.order_id,
                "status": self.status,
                "created_at": self.created_at,
                "payload_json": dict(self.payload_json),
            }
        return result

    def log_metadata(self) -> dict[str, Any]:
        return {"order_id": self.order_id, "has_payload": bool(self.raw_payload)}


class SyncResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    success: bool
    processed_count: int = 0
    failed_count: int = 0


@runtime_checkable
class LaikeClient(Protocol):
    async def fetch_orders(
        self,
        account_id: str,
        cursor: str | None,
        start_time: str | None,
        end_time: str | None,
    ) -> LaikePage:
        ...

    async def verify_webhook(
        self,
        headers: Mapping[str, str],
        raw_body: bytes,
    ) -> WebhookVerification:
        ...
