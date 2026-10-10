from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.db.models.laike import LaikeOrder, LaikeSyncRun


SENSITIVE_PAYLOAD_KEYS = {
    "address",
    "authorization",
    "cookie",
    "mobile",
    "password",
    "phone",
    "secret",
    "signature",
    "tel",
    "token",
}


class LaikeOrderQuery:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_orders(
        self,
        *,
        account_id: str | None = None,
        order_id: str | None = None,
        order_status: int | None = None,
        create_order_start_time: int | None = None,
        create_order_end_time: int | None = None,
        update_order_start_time: int | None = None,
        update_order_end_time: int | None = None,
        page_num: int = 1,
        page_size: int = 20,
    ) -> tuple[list[LaikeOrder], int]:
        statement: Select[tuple[LaikeOrder]] = select(LaikeOrder)
        count_statement = select(func.count()).select_from(LaikeOrder)
        conditions = _order_conditions(
            account_id=account_id,
            order_id=order_id,
            order_status=order_status,
            create_order_start_time=create_order_start_time,
            create_order_end_time=create_order_end_time,
            update_order_start_time=update_order_start_time,
            update_order_end_time=update_order_end_time,
        )
        statement = statement.where(*conditions).order_by(LaikeOrder.id.desc())
        count_statement = count_statement.where(*conditions)
        total = int(self.session.scalar(count_statement) or 0)
        rows = list(
            self.session.scalars(
                statement.offset((page_num - 1) * page_size).limit(page_size)
            )
        )
        return rows, total

    def get_order(self, provider_order_id: str) -> LaikeOrder | None:
        return self.session.scalar(
            select(LaikeOrder).where(
                LaikeOrder.provider_order_id == provider_order_id
            )
        )

    def list_sync_runs(
        self,
        *,
        account_id: str | None = None,
        page_num: int = 1,
        page_size: int = 20,
    ) -> tuple[list[LaikeSyncRun], int]:
        conditions = []
        if account_id:
            conditions.append(LaikeSyncRun.account_id == account_id)
        statement = (
            select(LaikeSyncRun)
            .where(*conditions)
            .order_by(LaikeSyncRun.id.desc())
        )
        count_statement = select(func.count()).select_from(LaikeSyncRun).where(*conditions)
        total = int(self.session.scalar(count_statement) or 0)
        rows = list(
            self.session.scalars(
                statement.offset((page_num - 1) * page_size).limit(page_size)
            )
        )
        return rows, total


def order_to_dict(order: LaikeOrder) -> dict[str, Any]:
    return {
        "provider_order_id": order.provider_order_id,
        "account_id": order.account_id,
        "order_status": order.order_status,
        "pay_amount_fen": order.pay_amount_fen,
        "create_order_time": order.create_order_time,
        "update_order_time": order.update_order_time,
        "pay_time": order.pay_time,
        "subject_id": order.subject_id,
        "product_id": order.product_id,
        "first_discovered_at": _datetime_value(order.first_discovered_at),
        "last_updated_at": _datetime_value(order.last_updated_at),
    }


def order_detail_to_dict(
    order: LaikeOrder,
    *,
    include_sensitive_payload: bool = False,
) -> dict[str, Any]:
    result = order_to_dict(order)
    result["payload_json"] = (
        order.payload_json
        if include_sensitive_payload
        else redact_payload(order.payload_json)
    )
    return result


def sync_run_to_dict(run: LaikeSyncRun) -> dict[str, Any]:
    return {
        "id": run.id,
        "account_id": run.account_id,
        "status": run.status,
        "start_time": run.start_time,
        "end_time": run.end_time,
        "page_count": run.page_count,
        "fetched_count": run.fetched_count,
        "processed_count": run.processed_count,
        "succeeded_count": run.succeeded_count,
        "duplicate_count": run.duplicate_count,
        "failed_count": run.failed_count,
        "error_code": run.error_code,
        "error_message": run.error_message,
        "started_at": _datetime_value(run.started_at),
        "finished_at": _datetime_value(run.finished_at),
    }


def redact_payload(value: Any, *, key: str | None = None) -> Any:
    if key and _is_sensitive_key(key):
        return "[REDACTED]"
    if isinstance(value, Mapping):
        return {
            str(child_key): redact_payload(child_value, key=str(child_key))
            for child_key, child_value in value.items()
        }
    if isinstance(value, list):
        return [redact_payload(item) for item in value]
    return value


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return normalized in SENSITIVE_PAYLOAD_KEYS or any(
        marker in normalized
        for marker in (
            "phone",
            "mobile",
            "tel",
            "address",
            "token",
            "secret",
            "password",
            "cookie",
            "signature",
            "authorization",
        )
    )


def _order_conditions(**filters: Any) -> list[Any]:
    conditions = []
    if filters["account_id"]:
        conditions.append(LaikeOrder.account_id == filters["account_id"])
    if filters["order_id"]:
        conditions.append(LaikeOrder.provider_order_id == filters["order_id"])
    if filters["order_status"] is not None:
        conditions.append(LaikeOrder.order_status == filters["order_status"])
    for field, start_name, end_name in (
        (
            "create_order_time",
            "create_order_start_time",
            "create_order_end_time",
        ),
        (
            "update_order_time",
            "update_order_start_time",
            "update_order_end_time",
        ),
    ):
        column = getattr(LaikeOrder, field)
        start = filters[start_name]
        end = filters[end_name]
        if start is not None:
            conditions.append(column >= start)
        if end is not None:
            conditions.append(column <= end)
    return conditions


def _datetime_value(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()
