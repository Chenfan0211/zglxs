from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from sqlalchemy.exc import SQLAlchemyError

from app.api.health import require_loopback
from app.api.responses import failure, success
from app.laike.query import (
    LaikeOrderQuery,
    order_detail_to_dict,
    order_to_dict,
    sync_run_to_dict,
)


def create_laike_order_router() -> APIRouter:
    router = APIRouter(prefix="/api/laike")

    @router.get("/orders")
    async def list_orders(request: Request):
        require_loopback(request)
        try:
            filters = _parse_order_filters(request)
            page_num, page_size = _parse_page(request)
        except ValueError as exc:
            return failure(str(exc), status_code=400)
        try:
            with request.app.state.laike_session_factory() as session:
                rows, total = LaikeOrderQuery(session).list_orders(
                    **filters,
                    page_num=page_num,
                    page_size=page_size,
                )
        except (RuntimeError, SQLAlchemyError):
            return failure("来客同步库未配置", status_code=503)
        return success(
            {
                "list": [order_to_dict(row) for row in rows],
                "total": total,
                "page_num": page_num,
                "page_size": page_size,
            }
        )

    @router.get("/orders/{order_id}")
    async def get_order(request: Request, order_id: str):
        require_loopback(request)
        if not order_id.strip():
            return failure("order_id must not be blank", status_code=400)
        try:
            with request.app.state.laike_session_factory() as session:
                order = LaikeOrderQuery(session).get_order(order_id)
        except (RuntimeError, SQLAlchemyError):
            return failure("来客同步库未配置", status_code=503)
        if order is None:
            return failure("订单不存在", status_code=404)
        return success(
            order_detail_to_dict(
                order,
                include_sensitive_payload=(
                    request.app.state.settings.laike_query_include_sensitive_payload
                ),
            )
        )

    @router.get("/sync-runs")
    async def list_sync_runs(request: Request):
        require_loopback(request)
        try:
            page_num, page_size = _parse_page(request)
            account_id = _optional_text(request.query_params.get("account_id"))
        except ValueError as exc:
            return failure(str(exc), status_code=400)
        try:
            with request.app.state.laike_session_factory() as session:
                rows, total = LaikeOrderQuery(session).list_sync_runs(
                    account_id=account_id,
                    page_num=page_num,
                    page_size=page_size,
                )
        except (RuntimeError, SQLAlchemyError):
            return failure("来客同步库未配置", status_code=503)
        return success(
            {
                "list": [sync_run_to_dict(row) for row in rows],
                "total": total,
                "page_num": page_num,
                "page_size": page_size,
            }
        )

    return router


def _parse_order_filters(request: Request) -> dict[str, Any]:
    params = request.query_params
    result: dict[str, Any] = {
        "account_id": _optional_text(params.get("account_id")),
        "order_id": _optional_text(params.get("order_id")),
        "order_status": _optional_int(params.get("order_status"), "order_status"),
        "create_order_start_time": _optional_int(
            params.get("create_order_start_time"), "create_order_start_time"
        ),
        "create_order_end_time": _optional_int(
            params.get("create_order_end_time"), "create_order_end_time"
        ),
        "update_order_start_time": _optional_int(
            params.get("update_order_start_time"), "update_order_start_time"
        ),
        "update_order_end_time": _optional_int(
            params.get("update_order_end_time"), "update_order_end_time"
        ),
    }
    for start_name, end_name in (
        ("create_order_start_time", "create_order_end_time"),
        ("update_order_start_time", "update_order_end_time"),
    ):
        if (
            result[start_name] is not None
            and result[end_name] is not None
            and result[start_name] > result[end_name]
        ):
            raise ValueError(f"{start_name} must not be after {end_name}")
    return result


def _parse_page(request: Request) -> tuple[int, int]:
    page_num = _optional_int(request.query_params.get("page_num"), "page_num")
    page_size = _optional_int(request.query_params.get("page_size"), "page_size")
    page_num = 1 if page_num is None else page_num
    page_size = 20 if page_size is None else page_size
    if page_num <= 0:
        raise ValueError("page_num must be positive")
    if page_size <= 0 or page_size > 100:
        raise ValueError("page_size must be between 1 and 100")
    return page_num, page_size


def _optional_int(value: str | None, name: str) -> int | None:
    if value is None or not value.strip():
        return None
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc


def _optional_text(value: str | None) -> str | None:
    value = value.strip() if value is not None else None
    return value or None
