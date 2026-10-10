from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Request
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from app.api.health import require_loopback
from app.api.responses import failure, success
from app.db.models.laike import LaikeOrder


def create_dashboard_router() -> APIRouter:
    router = APIRouter(prefix="/api/dashboard")

    @router.get("/home")
    async def home(request: Request):
        require_loopback(request)
        try:
            with request.app.state.laike_session_factory() as session:
                data = _build_home_summary(session)
        except (RuntimeError, SQLAlchemyError):
            return failure("来客同步库未配置", status_code=503)
        return success(data)

    return router


def _build_home_summary(session) -> dict:
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    total_orders = int(
        session.scalar(select(func.count()).select_from(LaikeOrder)) or 0
    )
    total_amount_fen = int(
        session.scalar(
            select(func.coalesce(func.sum(LaikeOrder.pay_amount_fen), 0))
        ) or 0
    )

    today_orders = int(
        session.scalar(
            select(func.count())
            .select_from(LaikeOrder)
            .where(LaikeOrder.create_order_time >= int(today_start.timestamp()))
        ) or 0
    )
    month_orders = int(
        session.scalar(
            select(func.count())
            .select_from(LaikeOrder)
            .where(LaikeOrder.create_order_time >= int(month_start.timestamp()))
        ) or 0
    )

    today_amount_fen = int(
        session.scalar(
            select(func.coalesce(func.sum(LaikeOrder.pay_amount_fen), 0)).where(
                LaikeOrder.create_order_time >= int(today_start.timestamp())
            )
        ) or 0
    )

    trend = _trend_summary(session, now)
    distribution = _status_distribution(session)

    return {
        "cards": {
            "total_orders": total_orders,
            "total_amount_fen": total_amount_fen,
            "today_orders": today_orders,
            "today_amount_fen": today_amount_fen,
        },
        "stats": [
            {"label": "累计订单", "value": str(total_orders)},
            {"label": "今日订单", "value": str(today_orders)},
            {"label": "本月订单", "value": str(month_orders)},
        ],
        "trend": trend,
        "distribution": distribution,
    }


def _trend_summary(session, now: datetime) -> dict:
    """近 7 天订单数与成交额趋势。"""
    dates: list[str] = []
    orders: list[int] = []
    amounts: list[int] = []
    for offset in range(6, -1, -1):
        day = (now - timedelta(days=offset)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        day_end = day + timedelta(days=1)
        day_count = int(
            session.scalar(
                select(func.count())
                .select_from(LaikeOrder)
                .where(
                    LaikeOrder.create_order_time >= int(day.timestamp()),
                    LaikeOrder.create_order_time < int(day_end.timestamp()),
                )
            ) or 0
        )
        day_amount = int(
            session.scalar(
                select(func.coalesce(func.sum(LaikeOrder.pay_amount_fen), 0)).where(
                    LaikeOrder.create_order_time >= int(day.timestamp()),
                    LaikeOrder.create_order_time < int(day_end.timestamp()),
                )
            ) or 0
        )
        dates.append(day.strftime("%m-%d"))
        orders.append(day_count)
        amounts.append(day_amount)
    return {"dates": dates, "orders": orders, "amounts": amounts}


def _status_distribution(session) -> list[dict]:
    """订单状态分布。"""
    rows = session.execute(
        select(LaikeOrder.order_status, func.count())
        .where(LaikeOrder.order_status.is_not(None))
        .group_by(LaikeOrder.order_status)
    ).all()
    label_map = {
        0: "待付款",
        1: "待发货",
        2: "待收货",
        3: "已完成",
        4: "已取消",
        5: "退款中",
        6: "已退款",
    }
    return [
        {"name": label_map.get(status, f"状态{status}"), "value": int(count)}
        for status, count in rows
    ]
