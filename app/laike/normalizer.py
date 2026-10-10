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


def _official_int(payload: Mapping[str, Any], field_name: str) -> int | None:
    value = payload.get(field_name)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise NormalizationError(f"{field_name} must be an integer")
    return value


def normalize_douyin_order(
    payload: Mapping[str, Any],
    *,
    account_id: str | None = None,
) -> NormalizedOrder:
    """Normalize only fields confirmed by the official order query contract."""
    if not isinstance(payload, Mapping):
        raise NormalizationError("order payload must be a mapping")

    provider_order_id = payload.get("order_id")
    if not isinstance(provider_order_id, (str, int)) or isinstance(
        provider_order_id, bool
    ):
        raise NormalizationError("order_id is missing or invalid")
    order_id = str(provider_order_id).strip()
    if not order_id:
        raise NormalizationError("order_id is missing or blank")

    if account_id is not None and (not isinstance(account_id, str) or not account_id.strip()):
        raise NormalizationError("account_id is invalid")

    order_status = _official_int(payload, "order_status")
    pay_amount_fen = _official_int(payload, "pay_amount")
    create_order_time = _official_int(payload, "create_order_time")
    update_order_time = _official_int(payload, "update_order_time")
    pay_time = _official_int(payload, "pay_time")

    subject_id = payload.get("user_id")
    if subject_id is not None:
        if isinstance(subject_id, bool) or not isinstance(subject_id, (str, int)):
            raise NormalizationError("user_id is invalid")
        subject_id = str(subject_id)

    product_id = None
    products = payload.get("products")
    if products is not None:
        if not isinstance(products, list):
            raise NormalizationError("products must be a list")
        if products:
            first_product = products[0]
            if not isinstance(first_product, Mapping):
                raise NormalizationError("products item must be an object")
            raw_product_id = first_product.get("product_id")
            if raw_product_id is not None:
                if isinstance(raw_product_id, bool) or not isinstance(
                    raw_product_id, (str, int)
                ):
                    raise NormalizationError("product_id is invalid")
                product_id = str(raw_product_id)

    return NormalizedOrder(
        order_id=order_id,
        account_id=account_id,
        subject_id=subject_id,
        product_id=product_id,
        status=str(order_status) if order_status is not None else None,
        order_status=order_status,
        pay_amount_fen=pay_amount_fen,
        create_order_time=create_order_time,
        update_order_time=update_order_time,
        pay_time=pay_time,
        raw_payload=dict(payload),
    )
