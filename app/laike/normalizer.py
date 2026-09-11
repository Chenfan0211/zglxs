from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .contracts import NormalizedOrder


def normalize_order(payload: Mapping[str, Any]) -> NormalizedOrder:
    payload_json = dict(payload)
    return NormalizedOrder(
        order_id=payload.get("order_id"),
        status=payload.get("status"),
        created_at=payload.get("created_at"),
        payload_json=payload_json,
    )
