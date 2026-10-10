"""财务模块接口。

结算列表与统计，数据来源为来客同步库真实订单数据。
路径遵循老系统 /apiv1/financial/... 约定，方法统一 POST。
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from app.api.responses import failure, success
from app.api._common import payload as _payload, has_demo_session as _has_demo_session, page as _page
from app.db.models.laike import LaikeOrder
from app.db.models.order import OrderFollow
from app.db.models.organization import CustomServiceCate, CustomServiceGroup, Department, Staff
from app.db.models.live import LiveRoom


def _finance_row_to_dict(row: LaikeOrder, follow=None) -> dict[str, Any]:
    payload = row.payload_json if isinstance(row.payload_json, dict) else {}

    def _get(*keys):
        for k in keys:
            if k in payload:
                return payload[k]
        return None

    order_no = _get("order_id", "order_no") or row.provider_order_id
    product_name = _get("product_name", "subject", "title") or row.subject_id
    user_tel = _get("user_tel", "mobile", "phone")
    verify_amount = _get("verify_amount", "pay_amount", "payment_amount")
    if verify_amount is None:
        verify_amount = row.pay_amount_fen

    d = {
        "provider_order_id": row.provider_order_id,
        "order_no": order_no,
        "account_id": row.account_id,
        "product_id": row.product_id,
        "out_product_id": _get("out_product_id", "product_out_id"),
        "product_name": product_name,
        "user_tel": user_tel,
        "user_tel_end": str(user_tel)[-4:] if user_tel else None,
        "pay_time": row.pay_time,
        "verify_amount": verify_amount,
        "order_status": row.order_status,
        # 财务明细（从来客 payload 提取）
        "goods": _get("goods", "goods_amount"),
        "ledger_total": _get("ledger_total", "total_amount"),
        "pay": _get("pay", "actual_pay"),
        "pay_discount": _get("pay_discount"),
        "user_deliv_platform_subsidy": _get("user_deliv_platform_subsidy", "platform_subsidy"),
        "user_deliv_merchant_subsidy": _get("user_deliv_merchant_subsidy", "merchant_subsidy"),
        "total_merchant_platform_service": _get("total_merchant_platform_service", "platform_service"),
        "talent_commission": _get("talent_commission"),
        "total_agent_merchant": _get("total_agent_merchant", "agent_merchant"),
        "total_operation_agent": _get("total_operation_agent", "operation_agent"),
        "actual_insured": _get("actual_insured", "insured"),
        "crafts_man": _get("crafts_man"),
        "certificate_code": _get("certificate_code", "voucher_code"),
        # 关联名称（占位，后续 apply）
        "custom_department_name": None,
        "custom_service_group_name": None,
        "custom_cate_name": None,
        "custom_name": None,
        "department_name": None,
        "live_name": None,
        "anchor_name": None,
        "console_name": None,
        "sale_user_role_str": None,
        "sale_channel_str": None,
        "sale_user_name": None,
        "maintenance_department_name": None,
        "maintenance_name": None,
        "refund_type_str": None,
        "refund_money": None,
        "add_price": None,
        "cost_amount": None,
        "profit_amount": None,
    }
    if follow is not None:
        d["add_price"] = follow.add_price_fen
        d["cost_amount"] = follow.cost_amount_fen
        d["profit_amount"] = follow.profit_amount_fen
        d["refund_money"] = follow.refund_money_fen
        d["refund_type_str"] = follow.refund_type
    return d


def _build_name_map(session, follows):
    ids = {"dept": set(), "group": set(), "cate": set(), "staff": set(), "live": set()}
    for f in follows:
        if f.custom_department_id:
            ids["dept"].add(f.custom_department_id)
        if f.custom_service_group_id:
            ids["group"].add(f.custom_service_group_id)
        if f.custom_cate_id:
            ids["cate"].add(f.custom_cate_id)
        for sid in (f.custom_staff_id, f.maintenance_staff_id, f.anchor_staff_id, f.console_staff_id, f.sale_user_id):
            if sid:
                ids["staff"].add(sid)
        if f.maintenance_department_id:
            ids["dept"].add(f.maintenance_department_id)
        if f.live_room_id:
            ids["live"].add(f.live_room_id)
    result = {"dept": {}, "group": {}, "cate": {}, "staff": {}, "live": {}}
    if ids["dept"]:
        rows = session.scalars(select(Department).where(Department.id.in_(ids["dept"]))).all()
        result["dept"] = {d.id: d.name for d in rows}
    if ids["group"]:
        rows = session.scalars(select(CustomServiceGroup).where(CustomServiceGroup.id.in_(ids["group"]))).all()
        result["group"] = {g.id: g.name for g in rows}
    if ids["cate"]:
        rows = session.scalars(select(CustomServiceCate).where(CustomServiceCate.id.in_(ids["cate"]))).all()
        result["cate"] = {c.id: c.name for c in rows}
    if ids["staff"]:
        rows = session.scalars(select(Staff).where(Staff.id.in_(ids["staff"]))).all()
        result["staff"] = {s.id: (s.nickname or s.name) for s in rows}
    if ids["live"]:
        rows = session.scalars(select(LiveRoom).where(LiveRoom.id.in_(ids["live"]))).all()
        result["live"] = {r.id: r.name for r in rows}
    return result


def _apply_finance_names(d, follow, name_map):
    if follow is None:
        return
    d["custom_department_name"] = name_map["dept"].get(follow.custom_department_id, "")
    d["custom_service_group_name"] = name_map["group"].get(follow.custom_service_group_id, "")
    d["custom_cate_name"] = name_map["cate"].get(follow.custom_cate_id, "")
    d["custom_name"] = name_map["staff"].get(follow.custom_staff_id, "")
    d["maintenance_department_name"] = name_map["dept"].get(follow.maintenance_department_id, "")
    d["maintenance_name"] = name_map["staff"].get(follow.maintenance_staff_id, "")
    d["live_name"] = name_map["live"].get(follow.live_room_id, "")
    d["anchor_name"] = name_map["staff"].get(follow.anchor_staff_id, "")
    d["console_name"] = name_map["staff"].get(follow.console_staff_id, "")
    d["sale_user_name"] = name_map["staff"].get(follow.sale_user_id, "")
    d["sale_user_role_str"] = follow.sale_user_role
    d["sale_channel_str"] = follow.sale_channel


def create_finance_router() -> APIRouter:
    router = APIRouter()

    async def settlement_list(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        page, size = _page(payload)
        try:
            with request.app.state.laike_session_factory() as session:
                stmt = select(LaikeOrder).where(LaikeOrder.pay_amount_fen.is_not(None)).order_by(LaikeOrder.id.desc())
                total = len(session.scalars(stmt).all())
                rows = session.scalars(stmt.offset((page - 1) * size).limit(size)).all()
                order_ids = [r.provider_order_id for r in rows]
                follows = {}
                if order_ids:
                    frows = session.scalars(select(OrderFollow).where(OrderFollow.provider_order_id.in_(order_ids))).all()
                    follows = {f.provider_order_id: f for f in frows}
                name_map = _build_name_map(session, follows.values())
                list_data = []
                for r in rows:
                    d = _finance_row_to_dict(r, follows.get(r.provider_order_id))
                    _apply_finance_names(d, follows.get(r.provider_order_id), name_map)
                    list_data.append(d)
        except (RuntimeError, SQLAlchemyError):
            return failure("来客同步库未配置", status_code=503)
        return success({"total": total, "list": list_data})

    async def statistic(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        try:
            with request.app.state.laike_session_factory() as session:
                total_orders = int(session.scalar(select(func.count()).select_from(LaikeOrder)) or 0)
                total_amount_fen = int(session.scalar(select(func.coalesce(func.sum(LaikeOrder.pay_amount_fen), 0))) or 0)
                paid_orders = int(session.scalar(select(func.count()).select_from(LaikeOrder).where(LaikeOrder.pay_amount_fen.is_not(None))) or 0)
                # 按订单状态统计金额
                status_rows = session.execute(
                    select(LaikeOrder.order_status, func.count(), func.coalesce(func.sum(LaikeOrder.pay_amount_fen), 0))
                    .group_by(LaikeOrder.order_status)
                ).all()
                status_map = {0: "待付款", 1: "待发货", 2: "待收货", 3: "已完成", 4: "已取消", 5: "退款中", 6: "已退款"}
                status_list = [
                    {"status": status, "label": status_map.get(status, f"状态{status}"), "count": int(cnt), "amount_fen": int(amt)}
                    for status, cnt, amt in status_rows if status is not None
                ]
        except (RuntimeError, SQLAlchemyError):
            return failure("来客同步库未配置", status_code=503)
        return success({
            "total_orders": total_orders,
            "paid_orders": paid_orders,
            "total_amount_fen": total_amount_fen,
            "status_list": status_list,
        })

    routes = {
        "/apiv1/financial/settlementlist": settlement_list,
        "/apiv1/financial/statistic": statistic,
    }
    for path, handler in routes.items():
        router.add_api_route(path, handler, methods=["POST"])

    return router
