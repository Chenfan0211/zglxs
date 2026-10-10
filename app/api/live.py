"""直播模块接口。

直播间、直播间成员（主播）、直播间中控、工作日志。
路径遵循老系统 /apiv1/user/... 约定，方法统一 POST。
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from app.api.responses import failure, success
from app.api._common import utcnow as _utcnow, payload as _payload, has_demo_session as _has_demo_session, page as _page, serialize as _serialize, id_from_payload as _id, to_int as _int
from app.db.models.live import CustomGroupLiveRoom, LiveRoom, LiveRoomConsole, LiveRoomMember, WorkLog
from app.db.models.organization import Staff


def _list_result(rows: list[Any], fields: list[str], total: int) -> dict[str, Any]:
    return {
        "total": total,
        "list": [{f: _serialize(getattr(r, f)) for f in fields} for r in rows],
    }


def _staff_nickname_map(session, staff_ids: list[int]) -> dict[int, str]:
    if not staff_ids:
        return {}
    rows = session.scalars(select(Staff).where(Staff.id.in_(staff_ids))).all()
    return {r.id: r.nickname or r.name for r in rows}


def create_live_router() -> APIRouter:
    router = APIRouter()

    # ---------- 直播间 ----------
    async def live_rooms_index(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        page, size = _page(payload)
        try:
            with request.app.state.laike_session_factory() as session:
                stmt = select(LiveRoom).order_by(LiveRoom.ordid, LiveRoom.id)
                keyword = str(payload.get("keyword", "")).strip()
                if keyword:
                    stmt = stmt.where(LiveRoom.name.like(f"%{keyword}%"))
                total = int(session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0)
                rows = session.scalars(stmt.offset((page - 1) * size).limit(size)).all()
                dept_map = {}
                dept_ids = {r.department_id for r in rows if r.department_id}
                if dept_ids:
                    from app.db.models.organization import Department
                    depts = session.scalars(select(Department).where(Department.id.in_(dept_ids))).all()
                    dept_map = {d.id: d.name for d in depts}
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        list_data = []
        for r in rows:
            d = {f: _serialize(getattr(r, f)) for f in ["id", "name", "live_uid", "live_uuid", "department_id", "room_id", "memo", "ordid", "status", "created_at"]}
            d["live_name"] = r.name
            d["department_name"] = dept_map.get(r.department_id, "")
            list_data.append(d)
        return success({"total": total, "list": list_data})

    async def live_rooms_add(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        name = str(payload.get("name", "")).strip()
        if not name:
            return failure("直播间名称不能为空", status_code=400)
        try:
            with request.app.state.laike_session_factory() as session:
                row = LiveRoom(
                    name=name,
                    live_uid=str(payload.get("live_uid", "")).strip() or None,
                    live_uuid=str(payload.get("live_uuid", "")).strip() or None,
                    department_id=_id(payload, "department_id"),
                    room_id=str(payload.get("room_id", "")).strip() or None,
                    memo=str(payload.get("memo", "")).strip() or None,
                    ordid=_int(payload.get("ordid", 0)) or 0,
                    status=bool(payload.get("status", 1)),
                )
                session.add(row)
                session.commit()
                session.refresh(row)
                result = {f: _serialize(getattr(row, f)) for f in ["id", "name", "live_uid", "live_uuid", "department_id", "room_id", "memo", "ordid", "status"]}
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success(result)

    async def live_rooms_edit(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        row_id = _id(payload)
        if row_id is None:
            return failure("缺少 id", status_code=400)
        try:
            with request.app.state.laike_session_factory() as session:
                row = session.scalar(select(LiveRoom).where(LiveRoom.id == row_id))
                if row is None:
                    return failure("直播间不存在", status_code=404)
                if "name" in payload:
                    row.name = str(payload.get("name", "")).strip() or row.name
                for key, field in (("live_uid", "live_uid"), ("live_uuid", "live_uuid"), ("memo", "memo")):
                    if key in payload:
                        setattr(row, field, str(payload.get(key, "")).strip() or None)
                if "department_id" in payload:
                    row.department_id = _id(payload, "department_id")
                if "room_id" in payload:
                    row.room_id = str(payload.get("room_id", "")).strip() or None
                if "ordid" in payload:
                    row.ordid = _int(payload.get("ordid", 0)) or 0
                if "status" in payload:
                    row.status = bool(payload.get("status"))
                row.updated_at = _utcnow()
                session.commit()
                result = {f: _serialize(getattr(row, f)) for f in ["id", "name", "live_uid", "live_uuid", "department_id", "room_id", "memo", "ordid", "status"]}
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success(result)

    async def live_rooms_del(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        row_id = _id(payload)
        if row_id is None:
            return failure("缺少 id", status_code=400)
        try:
            with request.app.state.laike_session_factory() as session:
                row = session.scalar(select(LiveRoom).where(LiveRoom.id == row_id))
                if row is None:
                    return failure("直播间不存在", status_code=404)
                session.delete(row)
                session.commit()
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success({})

    # ---------- 直播间成员（主播） ----------
    async def members_index(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        page, size = _page(payload)
        live_room_id = _id(payload, "live_room_id")
        try:
            with request.app.state.laike_session_factory() as session:
                stmt = select(LiveRoomMember).order_by(LiveRoomMember.id.desc())
                if live_room_id is not None:
                    stmt = stmt.where(LiveRoomMember.live_room_id == live_room_id)
                total = int(session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0)
                rows = session.scalars(stmt.offset((page - 1) * size).limit(size)).all()
                nick_map = _staff_nickname_map(session, [r.staff_id for r in rows])
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        list_data = []
        for r in rows:
            d = {f: _serialize(getattr(r, f)) for f in ["id", "live_room_id", "staff_id", "role", "status", "created_at"]}
            d["nickname"] = nick_map.get(r.staff_id, "")
            list_data.append(d)
        return success({"total": total, "list": list_data})

    async def members_add(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        live_room_id = _id(payload, "live_room_id")
        staff_id = _id(payload, "staff_id")
        if live_room_id is None or staff_id is None:
            return failure("直播间和员工不能为空", status_code=400)
        try:
            with request.app.state.laike_session_factory() as session:
                row = LiveRoomMember(live_room_id=live_room_id, staff_id=staff_id, anchor_uid=str(payload.get("anchor_uid", "")).strip() or None, is_control=bool(payload.get("is_control", False)), role=str(payload.get("role", "anchor")).strip() or "anchor", status=bool(payload.get("status", 1)))
                session.add(row)
                session.commit()
                session.refresh(row)
                result = {f: _serialize(getattr(row, f)) for f in ["id", "live_room_id", "staff_id", "anchor_uid", "is_control", "role", "status"]}
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success(result)

    async def members_edit(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        row_id = _id(payload)
        if row_id is None:
            return failure("缺少 id", status_code=400)
        try:
            with request.app.state.laike_session_factory() as session:
                row = session.scalar(select(LiveRoomMember).where(LiveRoomMember.id == row_id))
                if row is None:
                    return failure("成员不存在", status_code=404)
                if "live_room_id" in payload:
                    row.live_room_id = _id(payload, "live_room_id")
                if "staff_id" in payload:
                    row.staff_id = _id(payload, "staff_id")
                if "anchor_uid" in payload:
                    row.anchor_uid = str(payload.get("anchor_uid", "")).strip() or None
                if "is_control" in payload:
                    row.is_control = bool(payload.get("is_control"))
                if "role" in payload:
                    row.role = str(payload.get("role", "")).strip() or row.role
                if "status" in payload:
                    row.status = bool(payload.get("status"))
                row.updated_at = _utcnow()
                session.commit()
                result = {f: _serialize(getattr(row, f)) for f in ["id", "live_room_id", "staff_id", "role", "status"]}
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success(result)

    async def members_del(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        row_id = _id(payload)
        if row_id is None:
            return failure("缺少 id", status_code=400)
        try:
            with request.app.state.laike_session_factory() as session:
                row = session.scalar(select(LiveRoomMember).where(LiveRoomMember.id == row_id))
                if row is None:
                    return failure("成员不存在", status_code=404)
                session.delete(row)
                session.commit()
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success({})

    # ---------- 直播间中控 ----------
    async def consoles_index(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        page, size = _page(payload)
        live_room_id = _id(payload, "live_room_id")
        try:
            with request.app.state.laike_session_factory() as session:
                stmt = select(LiveRoomConsole).order_by(LiveRoomConsole.id.desc())
                if live_room_id is not None:
                    stmt = stmt.where(LiveRoomConsole.live_room_id == live_room_id)
                total = int(session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0)
                rows = session.scalars(stmt.offset((page - 1) * size).limit(size)).all()
                nick_map = _staff_nickname_map(session, [r.staff_id for r in rows])
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        list_data = []
        for r in rows:
            d = {f: _serialize(getattr(r, f)) for f in ["id", "live_room_id", "staff_id", "status", "created_at"]}
            d["nickname"] = nick_map.get(r.staff_id, "")
            list_data.append(d)
        return success({"total": total, "list": list_data})

    async def consoles_add(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        live_room_id = _id(payload, "live_room_id")
        staff_id = _id(payload, "staff_id")
        if live_room_id is None or staff_id is None:
            return failure("直播间和员工不能为空", status_code=400)
        try:
            with request.app.state.laike_session_factory() as session:
                row = LiveRoomConsole(live_room_id=live_room_id, staff_id=staff_id, console_uid=str(payload.get("console_uid", "")).strip() or None, status=bool(payload.get("status", 1)))
                session.add(row)
                session.commit()
                session.refresh(row)
                result = {f: _serialize(getattr(row, f)) for f in ["id", "live_room_id", "staff_id", "console_uid", "status"]}
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success(result)

    async def consoles_del(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        row_id = _id(payload)
        if row_id is None:
            return failure("缺少 id", status_code=400)
        try:
            with request.app.state.laike_session_factory() as session:
                row = session.scalar(select(LiveRoomConsole).where(LiveRoomConsole.id == row_id))
                if row is None:
                    return failure("中控不存在", status_code=404)
                session.delete(row)
                session.commit()
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success({})

    # ---------- 工作日志 ----------
    async def worklog_index(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        page, size = _page(payload)
        try:
            with request.app.state.laike_session_factory() as session:
                stmt = select(WorkLog).order_by(WorkLog.id.desc())
                total = int(session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0)
                rows = session.scalars(stmt.offset((page - 1) * size).limit(size)).all()
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success(_list_result(rows, ["id", "live_room_id", "staff_id", "work_type", "remark", "created_at"], total))

    async def worklog_add(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        try:
            with request.app.state.laike_session_factory() as session:
                row = WorkLog(
                    live_room_id=_id(payload, "live_room_id"),
                    staff_id=_id(payload, "staff_id"),
                    work_type=str(payload.get("work_type", "start")).strip() or "start",
                    remark=str(payload.get("remark", "")).strip() or None,
                )
                session.add(row)
                session.commit()
                session.refresh(row)
                result = {f: _serialize(getattr(row, f)) for f in ["id", "live_room_id", "staff_id", "work_type", "remark", "created_at"]}
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success(result)


    # ---------- 中控编辑 ----------
    async def consoles_edit(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        row_id = _id(payload)
        if row_id is None:
            return failure("缺少 id", status_code=400)
        try:
            with request.app.state.laike_session_factory() as session:
                row = session.scalar(select(LiveRoomConsole).where(LiveRoomConsole.id == row_id))
                if row is None:
                    return failure("中控不存在", status_code=404)
                if "live_room_id" in payload:
                    row.live_room_id = _id(payload, "live_room_id")
                if "staff_id" in payload:
                    row.staff_id = _id(payload, "staff_id")
                if "status" in payload:
                    row.status = bool(payload.get("status"))
                row.updated_at = _utcnow()
                session.commit()
                result = {f: _serialize(getattr(row, f)) for f in ["id", "live_room_id", "staff_id", "status"]}
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success(result)

    # ---------- 下班日志（endwork 系列） ----------
    async def worklog_end(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        try:
            with request.app.state.laike_session_factory() as session:
                row = WorkLog(
                    live_room_id=_id(payload, "live_room_id"),
                    staff_id=_id(payload, "staff_id"),
                    work_type="end",
                    remark=str(payload.get("remark", "")).strip() or None,
                )
                session.add(row)
                session.commit()
                session.refresh(row)
                result = {f: _serialize(getattr(row, f)) for f in ["id", "live_room_id", "staff_id", "work_type", "remark", "created_at"]}
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success(result)

    # ---------- 客服组-直播间关联 ----------
    async def group_live_rooms_index(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        page, size = _page(payload)
        group_id = _id(payload, "group_id")
        try:
            with request.app.state.laike_session_factory() as session:
                stmt = select(CustomGroupLiveRoom).order_by(CustomGroupLiveRoom.id.desc())
                if group_id is not None:
                    stmt = stmt.where(CustomGroupLiveRoom.group_id == group_id)
                total = int(session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0)
                rows = session.scalars(stmt.offset((page - 1) * size).limit(size)).all()
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success(_list_result(rows, ["id", "group_id", "live_room_id", "status", "created_at"], total))

    async def group_live_rooms_add(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        group_id = _id(payload, "group_id")
        live_room_id = _id(payload, "live_room_id")
        if group_id is None or live_room_id is None:
            return failure("客服组和直播间不能为空", status_code=400)
        try:
            with request.app.state.laike_session_factory() as session:
                row = CustomGroupLiveRoom(group_id=group_id, live_room_id=live_room_id, status=bool(payload.get("status", 1)))
                session.add(row)
                session.commit()
                session.refresh(row)
                result = {f: _serialize(getattr(row, f)) for f in ["id", "group_id", "live_room_id", "status"]}
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success(result)

    async def group_live_rooms_edit(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        row_id = _id(payload)
        if row_id is None:
            return failure("缺少 id", status_code=400)
        try:
            with request.app.state.laike_session_factory() as session:
                row = session.scalar(select(CustomGroupLiveRoom).where(CustomGroupLiveRoom.id == row_id))
                if row is None:
                    return failure("关联不存在", status_code=404)
                if "group_id" in payload:
                    row.group_id = _id(payload, "group_id")
                if "live_room_id" in payload:
                    row.live_room_id = _id(payload, "live_room_id")
                if "status" in payload:
                    row.status = bool(payload.get("status"))
                row.updated_at = _utcnow()
                session.commit()
                result = {f: _serialize(getattr(row, f)) for f in ["id", "group_id", "live_room_id", "status"]}
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success(result)

    async def group_live_rooms_del(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        row_id = _id(payload)
        if row_id is None:
            return failure("缺少 id", status_code=400)
        try:
            with request.app.state.laike_session_factory() as session:
                row = session.scalar(select(CustomGroupLiveRoom).where(CustomGroupLiveRoom.id == row_id))
                if row is None:
                    return failure("关联不存在", status_code=404)
                session.delete(row)
                session.commit()
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success({})



    # ---------- 搜索直播间（客服组关联用） ----------
    async def group_live_search(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        try:
            with request.app.state.laike_session_factory() as session:
                stmt = select(LiveRoom).order_by(LiveRoom.id)
                keyword = str(payload.get("keyword", "")).strip()
                if keyword:
                    stmt = stmt.where(LiveRoom.name.like(f"%{keyword}%"))
                rows = session.scalars(stmt.limit(50)).all()
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success({"list": [{f: _serialize(getattr(r, f)) for f in ["id", "name", "room_id"]} for r in rows]})

    # ---------- 搜索中控 ----------
    async def console_search(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        try:
            with request.app.state.laike_session_factory() as session:
                stmt = select(Staff).where(Staff.role == "console").order_by(Staff.id)
                rows = session.scalars(stmt.limit(100)).all()
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success({"list": [{"id": r.id, "name": r.name, "nickname": r.nickname or r.name} for r in rows]})

    # ---------- 搜索主播 ----------
    async def member_search(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        try:
            with request.app.state.laike_session_factory() as session:
                stmt = select(Staff).where(Staff.role.in_(["anchor", "co-anchor"])).order_by(Staff.id)
                rows = session.scalars(stmt.limit(100)).all()
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success({"list": [{"id": r.id, "name": r.name, "nickname": r.nickname or r.name} for r in rows]})


    routes = {
        "/apiv1/user/liverooms/index": live_rooms_index,
        "/apiv1/user/liverooms/add": live_rooms_add,
        "/apiv1/user/liverooms/edit": live_rooms_edit,
        "/apiv1/user/liverooms/del": live_rooms_del,
        "/apiv1/user/liveroommembers/index": members_index,
        "/apiv1/user/liveroommembers/add": members_add,
        "/apiv1/user/liveroommembers/edit": members_edit,
        "/apiv1/user/liveroommembers/del": members_del,
        "/apiv1/user/liveroomconsoles/index": consoles_index,
        "/apiv1/user/liveroomconsoles/add": consoles_add,
        "/apiv1/user/liveroomconsoles/edit": consoles_edit,
        "/apiv1/user/liveroomconsoles/del": consoles_del,
        "/apiv1/console/worklog": worklog_index,
        "/apiv1/console/startwork": worklog_add,
        "/apiv1/console/endwork": worklog_end,
        "/apiv1/console/consolestartwork": worklog_add,
        "/apiv1/console/consoleendwork": worklog_end,
        "/apiv1/user/customgroupliverooms/index": group_live_rooms_index,
        "/apiv1/user/customgroupliverooms/add": group_live_rooms_add,
        "/apiv1/user/customgroupliverooms/edit": group_live_rooms_edit,
        "/apiv1/user/customgroupliverooms/del": group_live_rooms_del,
        "/apiv1/user/customgroupliverooms/searchliveroom": group_live_search,
        "/apiv1/user/liveroomconsoles/searchconsole": console_search,
        "/apiv1/user/liveroommembers/searchmember": member_search,
    }
    for path, handler in routes.items():
        router.add_api_route(path, handler, methods=["POST"])

    return router
