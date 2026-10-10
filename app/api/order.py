"""订单业务模块接口。

订单列表/详情复用来客同步库真实数据（app.api.laike_orders），
本模块提供跟进、分配、认领、备注、锁单等业务写操作与日志查询。
路径遵循老系统 /apiv1/user/order/... 约定，方法统一 POST。
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from app.api.responses import failure, success
from app.api._common import utcnow as _utcnow, payload as _payload, has_demo_session as _has_demo_session, page as _page, serialize as _serialize, to_int as _int
from app.db.models.laike import LaikeOrder
from app.db.models.order import FollowStatus, OrderClaim, OrderFollow, OrderFollowLog
from app.db.models.organization import Staff


def _order_row_to_dict(row: LaikeOrder, follow=None) -> dict[str, Any]:
    payload = row.payload_json if isinstance(row.payload_json, dict) else {}
    # 从 payload_json 提取来客订单字段（兼容多种键名）
    def _get(*keys):
        for k in keys:
            if k in payload:
                return payload[k]
        return None

    order_no = _get("order_id", "order_no") or row.provider_order_id
    product_name = _get("product_name", "subject", "title") or row.subject_id
    user_tel = _get("user_tel", "mobile", "phone", "contact_mobile")
    user_tel_end = str(user_tel)[-4:] if user_tel else None
    use_time = _get("use_time", "verify_time", "used_at")
    verify_amount = _get("verify_amount", "pay_amount", "payment_amount")
    if verify_amount is None and row.pay_amount_fen is not None:
        verify_amount = row.pay_amount_fen

    result = {
        "provider_order_id": row.provider_order_id,
        "order_no": order_no,
        "account_id": row.account_id,
        "order_status": row.order_status,
        "order_status_str": str(row.order_status or ""),
        "pay_amount_fen": row.pay_amount_fen,
        "verify_amount": verify_amount,
        "create_order_time": row.create_order_time,
        "update_order_time": row.update_order_time,
        "pay_time": row.pay_time,
        "use_time": use_time,
        "subject_id": row.subject_id,
        "product_id": row.product_id,
        "out_product_id": _get("out_product_id", "product_out_id"),
        "product_name": product_name,
        "user_tel": user_tel,
        "user_tel_end": user_tel_end,
        "memo": None,
        "follow_status_str": None,
        "custom_department_name": None,
        "custom_service_group_name": None,
        "custom_cate_name": None,
        "custom_name": None,
        "department_name": None,
        "live_name": None,
        "anchor_name": None,
        "console_name": None,
        "maintenance_department_name": None,
        "maintenance_name": None,
        "refund_money": None,
        "refund_type_str": None,
        "add_price": None,
        "cost_amount": None,
        "profit_amount": None,
    }
    if follow is not None:
        result["memo"] = follow.memo
        result["follow_status_str"] = follow.follow_status
        result["refund_money"] = follow.refund_money_fen
        result["refund_type_str"] = follow.refund_type
        result["add_price"] = follow.add_price_fen
        result["cost_amount"] = follow.cost_amount_fen
        result["profit_amount"] = follow.profit_amount_fen
    return result


def _build_order_name_map(session, follows):
    """收集所有需要名称化的 ID，一次性查询映射。"""
    from app.db.models.organization import CustomServiceCate, CustomServiceGroup, Department, Staff
    from app.db.models.live import LiveRoom
    ids = {
        "dept": set(), "group": set(), "cate": set(), "staff": set(), "live": set(),
    }
    for f in follows:
        if f.custom_department_id:
            ids["dept"].add(f.custom_department_id)
        if f.custom_service_group_id:
            ids["group"].add(f.custom_service_group_id)
        if f.custom_cate_id:
            ids["cate"].add(f.custom_cate_id)
        if f.custom_staff_id:
            ids["staff"].add(f.custom_staff_id)
        if f.maintenance_department_id:
            ids["dept"].add(f.maintenance_department_id)
        if f.maintenance_staff_id:
            ids["staff"].add(f.maintenance_staff_id)
        if f.live_room_id:
            ids["live"].add(f.live_room_id)
        if f.anchor_staff_id:
            ids["staff"].add(f.anchor_staff_id)
        if f.console_staff_id:
            ids["staff"].add(f.console_staff_id)
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


def _apply_order_names(d, follow, name_map):
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
    d["custom_allocation_time"] = follow.custom_allocation_time
    d["custom_allocation_type_str"] = follow.custom_allocation_type


def _follow_status_map() -> dict[str, str]:
    return {
        "new": "待跟进",
        "following": "跟进中",
        "done": "已完成",
        "invalid": "无效",
    }


def create_order_router() -> APIRouter:
    router = APIRouter()

    # ---------- 订单列表（真实来客数据） ----------
    async def order_tradelist(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        page, size = _page(payload)
        try:
            with request.app.state.laike_session_factory() as session:
                stmt = select(LaikeOrder).order_by(LaikeOrder.id.desc())
                order_id = str(payload.get("order_id", "")).strip()
                account_id = str(payload.get("account_id", "")).strip()
                order_status = _int(payload.get("order_status"), "order_status")
                if order_id:
                    stmt = stmt.where(LaikeOrder.provider_order_id.like(f"%{order_id}%"))
                if account_id:
                    stmt = stmt.where(LaikeOrder.account_id.like(f"%{account_id}%"))
                if order_status is not None:
                    stmt = stmt.where(LaikeOrder.order_status == order_status)
                total = int(session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0)
                rows = session.scalars(stmt.offset((page - 1) * size).limit(size)).all()
                # 联查 order_follow 与关联名称
                order_ids = [r.provider_order_id for r in rows]
                follows = {}
                if order_ids:
                    frows = session.scalars(select(OrderFollow).where(OrderFollow.provider_order_id.in_(order_ids))).all()
                    follows = {f.provider_order_id: f for f in frows}
                name_map = _build_order_name_map(session, follows.values())
        except (RuntimeError, SQLAlchemyError):
            return failure("来客同步库未配置", status_code=503)
        list_data = []
        for r in rows:
            d = _order_row_to_dict(r, follows.get(r.provider_order_id))
            _apply_order_names(d, follows.get(r.provider_order_id), name_map)
            list_data.append(d)
        return success({"total": total, "list": list_data})

    async def order_detail(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        order_id = str(payload.get("order_id", "")).strip()
        if not order_id:
            return failure("缺少 order_id", status_code=400)
        try:
            with request.app.state.laike_session_factory() as session:
                order = session.scalar(select(LaikeOrder).where(LaikeOrder.provider_order_id == order_id))
                if order is None:
                    return failure("订单不存在", status_code=404)
                follow = session.scalar(select(OrderFollow).where(OrderFollow.provider_order_id == order_id))
                result = _order_row_to_dict(order)
                result["follow"] = (
                    {f: _serialize(getattr(follow, f)) for f in ["id", "follow_status", "owner_staff_id", "follow_day", "memo", "tel", "lock_flag"]}
                    if follow else None
                )
        except (RuntimeError, SQLAlchemyError):
            return failure("来客同步库未配置", status_code=503)
        return success(result)

    # ---------- 跟进 ----------
    async def follow_update(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        order_id = str(payload.get("order_id", "")).strip()
        if not order_id:
            return failure("缺少 order_id", status_code=400)
        try:
            with request.app.state.laike_session_factory() as session:
                follow = session.scalar(select(OrderFollow).where(OrderFollow.provider_order_id == order_id))
                if follow is None:
                    follow = OrderFollow(provider_order_id=order_id)
                    session.add(follow)
                if "follow_status" in payload:
                    follow.follow_status = str(payload.get("follow_status", "")).strip() or follow.follow_status
                if "owner_staff_id" in payload:
                    follow.owner_staff_id = _int(payload.get("owner_staff_id"), "owner_staff_id")
                if "follow_day" in payload:
                    follow.follow_day = _int(payload.get("follow_day"), "follow_day")
                if "memo" in payload:
                    follow.memo = str(payload.get("memo", "")).strip() or None
                if "tel" in payload:
                    follow.tel = str(payload.get("tel", "")).strip() or None
                if "lock_flag" in payload:
                    follow.lock_flag = bool(payload.get("lock_flag"))
                follow.updated_at = _utcnow()
                session.add(OrderFollowLog(
                    provider_order_id=order_id,
                    staff_id=_int(payload.get("staff_id"), "staff_id"),
                    action=str(payload.get("action", "follow")).strip() or "follow",
                    remark=str(payload.get("memo", "")).strip() or None,
                ))
                session.commit()
                session.refresh(follow)
                result = {f: _serialize(getattr(follow, f)) for f in ["id", "follow_status", "owner_staff_id", "follow_day", "memo", "tel", "lock_flag"]}
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success(result)

    # ---------- 认领 ----------
    async def order_claim(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        order_id = str(payload.get("order_id", "")).strip()
        staff_id = _int(payload.get("staff_id"), "staff_id")
        if not order_id:
            return failure("缺少 order_id", status_code=400)
        try:
            with request.app.state.laike_session_factory() as session:
                row = OrderClaim(provider_order_id=order_id, staff_id=staff_id)
                session.add(row)
                session.commit()
                session.refresh(row)
                result = {f: _serialize(getattr(row, f)) for f in ["id", "provider_order_id", "staff_id", "status", "created_at"]}
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success(result)

    # ---------- 跟进日志 ----------
    async def follow_log(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        page, size = _page(payload)
        order_id = str(payload.get("order_id", "")).strip()
        try:
            with request.app.state.laike_session_factory() as session:
                stmt = select(OrderFollowLog).order_by(OrderFollowLog.id.desc())
                if order_id:
                    stmt = stmt.where(OrderFollowLog.provider_order_id == order_id)
                total = int(session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0)
                rows = session.scalars(stmt.offset((page - 1) * size).limit(size)).all()
                staff_ids = [r.staff_id for r in rows if r.staff_id]
                staff_map = {}
                if staff_ids:
                    staff_rows = session.scalars(select(Staff).where(Staff.id.in_(staff_ids))).all()
                    staff_map = {s.id: s.nickname or s.name for s in staff_rows}
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        list_data = []
        for r in rows:
            d = {f: _serialize(getattr(r, f)) for f in ["id", "provider_order_id", "staff_id", "action", "remark", "created_at"]}
            d["staff_name"] = staff_map.get(r.staff_id, "") if r.staff_id else ""
            list_data.append(d)
        return success({"total": total, "list": list_data})

    # ---------- 认领日志 ----------
    async def claim_log(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        page, size = _page(payload)
        order_id = str(payload.get("order_id", "")).strip()
        try:
            with request.app.state.laike_session_factory() as session:
                stmt = select(OrderClaim).order_by(OrderClaim.id.desc())
                if order_id:
                    stmt = stmt.where(OrderClaim.provider_order_id == order_id)
                total = int(session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0)
                rows = session.scalars(stmt.offset((page - 1) * size).limit(size)).all()
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success({"total": total, "list": [{f: _serialize(getattr(r, f)) for f in ["id", "provider_order_id", "staff_id", "status", "created_at"]} for r in rows]})

    # ---------- 搜索（主播/中控/客服/售后） ----------
    async def search_staff(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        role = str(payload.get("role", "")).strip()
        try:
            with request.app.state.laike_session_factory() as session:
                stmt = select(Staff).order_by(Staff.id)
                if role:
                    stmt = stmt.where(Staff.role == role)
                rows = session.scalars(stmt.limit(100)).all()
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success({"list": [{"id": r.id, "name": r.name, "nickname": r.nickname or r.name} for r in rows]})


    # ---------- 跟进状态配置 ----------
    async def follow_status_index(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        page, size = _page(payload)
        try:
            with request.app.state.laike_session_factory() as session:
                stmt = select(FollowStatus).order_by(FollowStatus.sort_order)
                total = int(session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0)
                rows = session.scalars(stmt.offset((page - 1) * size).limit(size)).all()
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success({"total": total, "list": [{f: _serialize(getattr(r, f)) for f in ["id", "name", "sort_order", "status", "created_at"]} for r in rows]})

    async def follow_status_add(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        name = str(payload.get("name", "")).strip()
        if not name:
            return failure("状态名称不能为空", status_code=400)
        try:
            with request.app.state.laike_session_factory() as session:
                row = FollowStatus(name=name, sort_order=int(payload.get("sort_order", 0) or 0), status=bool(payload.get("status", 1)))
                session.add(row)
                session.commit()
                session.refresh(row)
                result = {f: _serialize(getattr(row, f)) for f in ["id", "name", "sort_order", "status"]}
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success(result)

    async def follow_status_edit(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        row_id = _int(payload.get("id"), "id")
        if row_id is None:
            return failure("缺少 id", status_code=400)
        try:
            with request.app.state.laike_session_factory() as session:
                row = session.scalar(select(FollowStatus).where(FollowStatus.id == row_id))
                if row is None:
                    return failure("状态不存在", status_code=404)
                if "name" in payload:
                    row.name = str(payload.get("name", "")).strip() or row.name
                if "sort_order" in payload:
                    row.sort_order = int(payload.get("sort_order", 0) or 0)
                if "status" in payload:
                    row.status = bool(payload.get("status"))
                row.updated_at = _utcnow()
                session.commit()
                result = {f: _serialize(getattr(row, f)) for f in ["id", "name", "sort_order", "status"]}
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success(result)

    async def follow_status_del(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        row_id = _int(payload.get("id"), "id")
        if row_id is None:
            return failure("缺少 id", status_code=400)
        try:
            with request.app.state.laike_session_factory() as session:
                row = session.scalar(select(FollowStatus).where(FollowStatus.id == row_id))
                if row is None:
                    return failure("状态不存在", status_code=404)
                session.delete(row)
                session.commit()
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success({})

    # ---------- 订单跟进字段更新（memo/tel/lockflag/followday/成本等） ----------
    async def order_field_update(request: Request, field_map: dict):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        order_id = str(payload.get("order_id", "")).strip()
        if not order_id:
            return failure("缺少 order_id", status_code=400)
        try:
            with request.app.state.laike_session_factory() as session:
                follow = session.scalar(select(OrderFollow).where(OrderFollow.provider_order_id == order_id))
                if follow is None:
                    follow = OrderFollow(provider_order_id=order_id)
                    session.add(follow)
                for src, dst in field_map.items():
                    if src in payload:
                        setattr(follow, dst, payload.get(src))
                follow.updated_at = _utcnow()
                session.add(OrderFollowLog(provider_order_id=order_id, staff_id=_int(payload.get("staff_id"), "staff_id"), action=str(payload.get("action", "update")).strip() or "update", remark=str(payload.get("memo", "")).strip() or None))
                session.commit()
                session.refresh(follow)
                result = {f: _serialize(getattr(follow, f)) for f in ["id", "follow_status", "owner_staff_id", "follow_day", "memo", "tel", "lock_flag"]}
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success(result)

    async def order_updatememo(request: Request):
        return await order_field_update(request, {"memo": "memo"})

    async def order_updatetel(request: Request):
        return await order_field_update(request, {"tel": "tel"})

    async def order_updatelockflg(request: Request):
        return await order_field_update(request, {"lock_flag": "lock_flag"})

    async def order_setfollowday(request: Request):
        return await order_field_update(request, {"follow_day": "follow_day"})

    async def order_changecostinfo(request: Request):
        return await order_field_update(request, {"memo": "memo"})

    async def order_addfollow(request: Request):
        return await order_field_update(request, {"memo": "memo", "follow_status": "follow_status"})

    async def order_confirm(request: Request):
        return await order_field_update(request, {"follow_status": "follow_status"})

    async def order_release(request: Request):
        return await order_field_update(request, {"lock_flag": "lock_flag"})

    # ---------- 批量操作（简化：遍历 order_ids 逐个更新） ----------
    async def _batch_update(request: Request, field: str, value_key: str):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        order_ids = payload.get("order_ids") or payload.get("ids") or []
        if isinstance(order_ids, str):
            order_ids = [x.strip() for x in order_ids.split(",") if x.strip()]
        if not order_ids:
            return failure("缺少 order_ids", status_code=400)
        value = payload.get(value_key)
        try:
            with request.app.state.laike_session_factory() as session:
                updated = 0
                for oid in order_ids:
                    follow = session.scalar(select(OrderFollow).where(OrderFollow.provider_order_id == oid))
                    if follow is None:
                        follow = OrderFollow(provider_order_id=oid)
                        session.add(follow)
                    setattr(follow, field, value)
                    follow.updated_at = _utcnow()
                    updated += 1
                session.commit()
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success({"updated": updated})

    async def order_batchallocation(request: Request):
        return await _batch_update(request, "owner_staff_id", "staff_id")

    async def order_batchallocationmaintenance(request: Request):
        return await _batch_update(request, "owner_staff_id", "staff_id")

    async def order_publicbatchallocation(request: Request):
        return await _batch_update(request, "owner_staff_id", "staff_id")

    async def order_batchchangeanchor(request: Request):
        return await _batch_update(request, "owner_staff_id", "staff_id")

    async def order_batchchangeconsole(request: Request):
        return await _batch_update(request, "owner_staff_id", "staff_id")

    async def order_batchchangefollowstatus(request: Request):
        return await _batch_update(request, "follow_status", "follow_status")

    async def order_batchaddfollow(request: Request):
        return await _batch_update(request, "memo", "memo")



    async def follow_status_changestatus(request: Request):
        return await follow_status_edit(request)

    async def order_add(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        return failure("订单由来客同步自动创建，不支持手动新增", status_code=400)

    async def order_edit(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        order_id = str(payload.get("order_id", "")).strip()
        if not order_id:
            return failure("缺少 order_id", status_code=400)
        return await order_field_update(request, {"memo": "memo", "tel": "tel"})

    async def order_del(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        return failure("同步订单不允许删除", status_code=400)



    # ---------- 订单子列表（按状态/类型筛选，对接来客库） ----------
    async def order_sublist(request: Request, statuses=None):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        page, size = _page(payload)
        try:
            with request.app.state.laike_session_factory() as session:
                stmt = select(LaikeOrder).order_by(LaikeOrder.id.desc())
                if statuses:
                    stmt = stmt.where(LaikeOrder.order_status.in_(statuses))
                total = int(session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0)
                rows = session.scalars(stmt.offset((page - 1) * size).limit(size)).all()
                order_ids = [r.provider_order_id for r in rows]
                follows = {}
                if order_ids:
                    frows = session.scalars(select(OrderFollow).where(OrderFollow.provider_order_id.in_(order_ids))).all()
                    follows = {f.provider_order_id: f for f in frows}
                name_map = _build_order_name_map(session, follows.values())
        except (RuntimeError, SQLAlchemyError):
            return failure("来客同步库未配置", status_code=503)
        list_data = []
        for r in rows:
            d = _order_row_to_dict(r, follows.get(r.provider_order_id))
            _apply_order_names(d, follows.get(r.provider_order_id), name_map)
            list_data.append(d)
        return success({"total": total, "list": list_data})

    async def order_uselist(request: Request):
        return await order_sublist(request, statuses=[3])

    async def order_refundlist(request: Request):
        return await order_sublist(request, statuses=[5, 6])

    async def order_reservationlist(request: Request):
        return await order_sublist(request)

    async def order_claimcustomlist(request: Request):
        return await order_sublist(request)

    async def order_operatelog(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        page, size = _page(payload)
        order_id = str(payload.get("order_id", "")).strip()
        try:
            with request.app.state.laike_session_factory() as session:
                stmt = select(OrderFollowLog).order_by(OrderFollowLog.id.desc())
                if order_id:
                    stmt = stmt.where(OrderFollowLog.provider_order_id == order_id)
                total = int(session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0)
                rows = session.scalars(stmt.offset((page - 1) * size).limit(size)).all()
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success({"total": total, "list": [{f: _serialize(getattr(r, f)) for f in ["id", "provider_order_id", "staff_id", "action", "remark", "created_at"]} for r in rows]})


    routes = {
        "/apiv1/user/order/tradelist": order_tradelist,
        "/apiv1/user/order/detail": order_detail,
        "/apiv1/user/order/updatefollowstatus": follow_update,
        "/apiv1/user/order/claim": order_claim,
        "/apiv1/user/order/followlog": follow_log,
        "/apiv1/user/order/claimlog": claim_log,
        "/apiv1/user/order/searchanchor": search_staff,
        "/apiv1/user/order/searchconsole": search_staff,
        "/apiv1/user/order/searchcustom": search_staff,
        "/apiv1/user/order/searchmaintenance": search_staff,
        "/apiv1/user/followstatus/index": follow_status_index,
        "/apiv1/user/followstatus/add": follow_status_add,
        "/apiv1/user/followstatus/edit": follow_status_edit,
        "/apiv1/user/followstatus/del": follow_status_del,
        "/apiv1/user/order/updatememo": order_updatememo,
        "/apiv1/user/order/updatetel": order_updatetel,
        "/apiv1/user/order/updatelockflg": order_updatelockflg,
        "/apiv1/user/order/setfollowday": order_setfollowday,
        "/apiv1/user/order/changecostinfo": order_changecostinfo,
        "/apiv1/user/order/addfollow": order_addfollow,
        "/apiv1/user/order/confirm": order_confirm,
        "/apiv1/user/order/release": order_release,
        "/apiv1/user/order/batchallocation": order_batchallocation,
        "/apiv1/user/order/batchallocationmaintenance": order_batchallocationmaintenance,
        "/apiv1/user/order/publicbatchallocation": order_publicbatchallocation,
        "/apiv1/user/order/batchchangeanchor": order_batchchangeanchor,
        "/apiv1/user/order/batchchangeconsole": order_batchchangeconsole,
        "/apiv1/user/order/batchchangefollowstatus": order_batchchangefollowstatus,
        "/apiv1/user/order/batchaddfollow": order_batchaddfollow,
        "/apiv1/user/followstatus/changestatus": follow_status_changestatus,
        "/apiv1/user/order/add": order_add,
        "/apiv1/user/order/edit": order_edit,
        "/apiv1/user/order/del": order_del,
        "/apiv1/user/order/uselist": order_uselist,
        "/apiv1/user/order/refundlist": order_refundlist,
        "/apiv1/user/order/reservationlist": order_reservationlist,
        "/apiv1/user/order/claimcustomlist": order_claimcustomlist,
        "/apiv1/user/order/operatelog": order_operatelog,
    }
    for path, handler in routes.items():
        router.add_api_route(path, handler, methods=["POST"])

    return router
