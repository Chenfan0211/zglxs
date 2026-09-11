from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .contracts import NormalizedOrder


class NormalizationError(ValueError):
    """Raised when an explicitly mapped order cannot be normalized."""


@dataclass(frozen=True, slots=True)
class OrderFieldMapping:
    order_id: str
    subject_id: str
    product_id: str
    status: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


def _read_path(payload: Mapping[str, Any], path: str | None) -> Any:
    if not path:
        return None
    current: Any = payload
    for segment in path.split("."):
        if not isinstance(current, Mapping) or segment not in current:
            return None
        current = current[segment]
    return current


def _normalize_time(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class OrderNormalizer:
    def __init__(self, mapping: OrderFieldMapping) -> None:
        self.mapping = mapping

    def normalize(self, payload: Mapping[str, Any]) -> NormalizedOrder:
        if not isinstance(payload, Mapping):
            raise NormalizationError("order payload must be a mapping")

        values = {
            "order_id": _read_path(payload, self.mapping.order_id),
            "subject_id": _read_path(payload, self.mapping.subject_id),
            "product_id": _read_path(payload, self.mapping.product_id),
        }
        for field_name, value in values.items():
            if not isinstance(value, str) or not value.strip():
                raise NormalizationError(f"{field_name} is missing or blank")

        original_created_at = _read_path(payload, self.mapping.created_at)
        original_updated_at = _read_path(payload, self.mapping.updated_at)
        return NormalizedOrder(
            order_id=values["order_id"],
            subject_id=values["subject_id"],
            product_id=values["product_id"],
            status=_read_path(payload, self.mapping.status),
            original_created_at=original_created_at,
            normalized_created_at=_normalize_time(original_created_at),
            original_updated_at=original_updated_at,
            normalized_updated_at=_normalize_time(original_updated_at),
            raw_payload=payload,
        )

    __call__ = normalize


def normalize_order(
    payload: Mapping[str, Any],
    mapping: OrderFieldMapping | None = None,
) -> NormalizedOrder:
    if mapping is not None:
        return OrderNormalizer(mapping).normalize(payload)
    if not isinstance(payload, Mapping):
        raise NormalizationError("order payload must be a mapping")

    return NormalizedOrder(
        order_id=payload.get("order_id"),
        status=payload.get("status"),
        created_at=payload.get("created_at"),
        payload_json=dict(payload),
    )
