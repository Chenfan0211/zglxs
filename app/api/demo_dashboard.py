# -*- coding: utf-8 -*-
"""中控工作台（console）接口。

对接真实业务表与来客同步库，替代原先的 DEMO 假数据。
路径遵循老系统 /apiv1/console/* 约定，方法统一 POST。
"""

from __future__ import annotations


from fastapi import APIRouter, Request
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from app.api.responses import failure, success
from app.api._common import payload as _payload, has_demo_session as _has_demo_session, serialize as _serialize, to_int as _int
from app.core.settings import Settings
from app.db.models.laike import LaikeOrder
from app.db.models.live import LiveRoom, LiveRoomConsole, LiveRoomMember, WorkLog
from app.db.models.organization import (
    CustomServiceGroup,
    Department,
    Staff,
)


def _session(request: Request):
    return request.app.state.laike_session_factory()


def create_demo_dashboard_router(settings: Settings) -> APIRouter:
    del settings
    router = APIRouter()

    # ---------- 中控工作台中心 ----------
    async def center(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        try:
            with _session(request) as session:
                departments = session.scalars(select(Department).order_by(Department.id)).all()
                custom_departments = session.scalars(select(Department).where(Department.name.like("%客服%")).order_by(Department.id)).all()
                maintenance_departments = session.scalars(select(Department).where(Department.name.like("%售后%")).order_by(Department.id)).all()
                total_orders = int(session.scalar(select(func.count()).select_from(LaikeOrder)) or 0)
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success({
            "info": {"total_order_num": total_orders},
            "department_list": [{"key": f"DEPT-{d.id}", "value": d.name} for d in departments],
            "custom_department_list": [{"key": f"DEPT-{d.id}", "value": d.name} for d in custom_departments],
            "maintenance_department_list": [{"key": f"DEPT-{d.id}", "value": d.name} for d in maintenance_departments],
        })

    # ---------- 直播间搜索 ----------
    async def search_live_rooms(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        keyword = str(payload.get("keyword", "")).strip()
        try:
            with _session(request) as session:
                stmt = select(LiveRoom).order_by(LiveRoom.id)
                if keyword:
                    stmt = stmt.where(LiveRoom.name.like(f"%{keyword}%"))
                rows = session.scalars(stmt.limit(100)).all()
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success({"list": [{"id": str(r.id), "live_name": r.name} for r in rows]})

    # ---------- 主播搜索 ----------
    async def search_anchors(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        keyword = str(payload.get("keyword", "")).strip()
        try:
            with _session(request) as session:
                stmt = select(Staff).where(Staff.role.in_(["anchor", "co-anchor"])).order_by(Staff.id)
                if keyword:
                    stmt = stmt.where(Staff.name.like(f"%{keyword}%"))
                rows = session.scalars(stmt.limit(100)).all()
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success({"list": [{"id": str(r.id), "nickname": r.nickname or r.name} for r in rows]})

    # ---------- 中控搜索 ----------
    async def search_consoles(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        keyword = str(payload.get("keyword", "")).strip()
        try:
            with _session(request) as session:
                stmt = select(Staff).where(Staff.role == "console").order_by(Staff.id)
                if keyword:
                    stmt = stmt.where(Staff.name.like(f"%{keyword}%"))
                rows = session.scalars(stmt.limit(100)).all()
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success({"list": [{"id": str(r.id), "nickname": r.nickname or r.name} for r in rows]})

    # ---------- 客服组搜索 ----------
    async def search_groups(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        keyword = str(payload.get("keyword", "")).strip()
        try:
            with _session(request) as session:
                stmt = select(CustomServiceGroup).order_by(CustomServiceGroup.id)
                if keyword:
                    stmt = stmt.where(CustomServiceGroup.name.like(f"%{keyword}%"))
                rows = session.scalars(stmt.limit(100)).all()
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success({"list": [{"id": str(r.id), "name": r.name} for r in rows]})

    # ---------- 客服搜索 ----------
    async def search_customs(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        keyword = str(payload.get("keyword", "")).strip()
        try:
            with _session(request) as session:
                stmt = select(Staff).where(Staff.role == "custom").order_by(Staff.id)
                if keyword:
                    stmt = stmt.where(Staff.name.like(f"%{keyword}%"))
                rows = session.scalars(stmt.limit(100)).all()
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success({"list": [{"id": str(r.id), "nickname": r.nickname or r.name} for r in rows]})

    # ---------- 售后搜索 ----------
    async def search_maintenance(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        keyword = str(payload.get("keyword", "")).strip()
        try:
            with _session(request) as session:
                stmt = select(Staff).where(Staff.role == "maintenance").order_by(Staff.id)
                if keyword:
                    stmt = stmt.where(Staff.name.like(f"%{keyword}%"))
                rows = session.scalars(stmt.limit(100)).all()
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success({"list": [{"id": str(r.id), "nickname": r.nickname or r.name} for r in rows]})

    # ---------- 直播间主播列表 ----------
    async def live_room_anchors(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        live_room_id = _int(payload.get("live_room_id"), "live_room_id")
        try:
            with _session(request) as session:
                stmt = select(LiveRoomMember).order_by(LiveRoomMember.id)
                if live_room_id is not None:
                    stmt = stmt.where(LiveRoomMember.live_room_id == live_room_id)
                rows = session.scalars(stmt.limit(100)).all()
                staff_ids = [r.staff_id for r in rows]
                staff_map = {}
                if staff_ids:
                    staff_rows = session.scalars(select(Staff).where(Staff.id.in_(staff_ids))).all()
                    staff_map = {s.id: s.nickname or s.name for s in staff_rows}
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success({"is_view_button": "1", "list": [{"id": str(r.id), "nickname": staff_map.get(r.staff_id, "")} for r in rows]})

    # ---------- 直播间中控列表 ----------
    async def live_room_consoles(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        live_room_id = _int(payload.get("live_room_id"), "live_room_id")
        try:
            with _session(request) as session:
                stmt = select(LiveRoomConsole).order_by(LiveRoomConsole.id)
                if live_room_id is not None:
                    stmt = stmt.where(LiveRoomConsole.live_room_id == live_room_id)
                rows = session.scalars(stmt.limit(100)).all()
                staff_ids = [r.staff_id for r in rows]
                staff_map = {}
                if staff_ids:
                    staff_rows = session.scalars(select(Staff).where(Staff.id.in_(staff_ids))).all()
                    staff_map = {s.id: s.nickname or s.name for s in staff_rows}
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success({"list": [{"id": str(r.id), "nickname": staff_map.get(r.staff_id, ""), "live_room_id": r.live_room_id} for r in rows]})

    # ---------- 中控工作日志 ----------
    async def console_worklog(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        try:
            with _session(request) as session:
                stmt = select(WorkLog).order_by(WorkLog.id.desc()).limit(100)
                rows = session.scalars(stmt).all()
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success({"total": len(rows), "list": [{f: _serialize(getattr(r, f)) for f in ["id", "live_room_id", "staff_id", "work_type", "remark", "created_at"]} for r in rows]})

    # ---------- 直播间排名（对接来客订单） ----------
    async def live_room_rank(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        try:
            with _session(request) as session:
                rows = session.execute(
                    select(LaikeOrder.account_id, func.count().label("cnt"), func.coalesce(func.sum(LaikeOrder.pay_amount_fen), 0).label("amount"))
                    .group_by(LaikeOrder.account_id)
                    .order_by(func.sum(LaikeOrder.pay_amount_fen).desc())
                    .limit(50)
                ).all()
                rooms = session.scalars(select(LiveRoom)).all()
                room_map = {str(r.id): r.name for r in rooms}
        except (RuntimeError, SQLAlchemyError):
            return failure("来客同步库未配置", status_code=503)
        list_data = []
        for i, (account_id, cnt, amount) in enumerate(rows, start=1):
            list_data.append({"rank": i, "live_name": room_map.get(account_id, account_id or ""), "order_num": int(cnt), "total_money": f"¥{int(amount or 0) / 100:.2f}"})
        return success({"list": list_data})

    # ---------- 主播订单金额排名 ----------
    async def order_money_rank(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        try:
            with _session(request) as session:
                rows = session.execute(
                    select(LaikeOrder.account_id, func.coalesce(func.sum(LaikeOrder.pay_amount_fen), 0).label("amount"))
                    .group_by(LaikeOrder.account_id)
                    .order_by(func.sum(LaikeOrder.pay_amount_fen).desc())
                    .limit(50)
                ).all()
        except (RuntimeError, SQLAlchemyError):
            return failure("来客同步库未配置", status_code=503)
        return success({"list": [{"rank": i, "nickname": account_id or "", "total_money": f"¥{int(amount or 0) / 100:.2f}"} for i, (account_id, amount) in enumerate(rows, start=1)]})

    # ---------- 主播核销金额排名 ----------
    async def order_use_money_rank(request: Request):
        return await order_money_rank(request)

    # ---------- 订单区域分布 ----------
    async def order_area(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        try:
            with _session(request) as session:
                rows = session.execute(
                    select(LaikeOrder.account_id, func.count().label("cnt"))
                    .group_by(LaikeOrder.account_id)
                    .order_by(func.count().desc())
                    .limit(50)
                ).all()
        except (RuntimeError, SQLAlchemyError):
            return failure("来客同步库未配置", status_code=503)
        total = sum(int(c) for _, c in rows) or 1
        list_data = []
        for i, (account_id, cnt) in enumerate(rows, start=1):
            list_data.append({"rank": i, "name": account_id or "未知", "num": int(cnt), "rate": f"{int(cnt) * 100 / total:.2f}%"})
        return success({"list": list_data})

    routes = {
        "/apiv1/console/center": center,
        "/apiv1/console/searchanchorliveroom": search_live_rooms,
        "/apiv1/console/searchcustomliveroom": search_live_rooms,
        "/apiv1/console/searchanchor": search_anchors,
        "/apiv1/console/searchconsole": search_consoles,
        "/apiv1/console/searchgroup": search_groups,
        "/apiv1/console/searchcustom": search_customs,
        "/apiv1/console/searchmaintenance": search_maintenance,
        "/apiv1/console/liveroomanchorlist": live_room_anchors,
        "/apiv1/console/liveroomconsolelist": live_room_consoles,
        "/apiv1/console/consoleworklog": console_worklog,
        "/apiv1/console/liveroomrank": live_room_rank,
        "/apiv1/console/ordermoneyrank": order_money_rank,
        "/apiv1/console/orderusemoneyrank": order_use_money_rank,
        "/apiv1/console/orderarea": order_area,
    }
    for path, handler in routes.items():
        router.add_api_route(path, handler, methods=["POST"])

    return router

