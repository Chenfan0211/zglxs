from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.api.health import require_loopback
from app.api.responses import failure, success
from app.api._common import has_demo_session as _has_demo_session, payload as _request_payload
from app.db.models.system import SystemNotice


def create_notice_router() -> APIRouter:
    router = APIRouter(prefix="/api/notices")

    @router.get("")
    async def list_notices(request: Request):
        require_loopback(request)
        include_all = request.query_params.get("all") in {"1", "true", "True"}
        try:
            with request.app.state.laike_session_factory() as session:
                statement = select(SystemNotice).order_by(SystemNotice.id.desc())
                if not include_all:
                    statement = statement.where(SystemNotice.is_published.is_(True))
                rows = session.scalars(statement).all()
        except (RuntimeError, SQLAlchemyError):
            return failure("来客同步库未配置", status_code=503)
        return success({"list": [_notice_to_dict(row) for row in rows]})

    @router.get("/{notice_id}")
    async def get_notice(request: Request, notice_id: int):
        require_loopback(request)
        try:
            with request.app.state.laike_session_factory() as session:
                row = session.scalar(
                    select(SystemNotice).where(SystemNotice.id == notice_id)
                )
        except (RuntimeError, SQLAlchemyError):
            return failure("来客同步库未配置", status_code=503)
        if row is None:
            return failure("公告不存在", status_code=404)
        return success(_notice_to_dict(row))

    @router.post("")
    async def create_notice(request: Request):
        if not _has_demo_session(request):
            return failure("未授权", status_code=401)
        payload = await _request_payload(request)
        title = str(payload.get("title", "")).strip()
        content = str(payload.get("content", "")).strip()
        if not title or not content:
            return failure("标题和内容不能为空", status_code=400)
        try:
            with request.app.state.laike_session_factory() as session:
                notice = SystemNotice(
                    title=title,
                    content=content,
                    notice_type=str(payload.get("notice_type", "system")).strip()
                    or "system",
                    is_published=bool(payload.get("is_published", True)),
                )
                session.add(notice)
                session.commit()
                session.refresh(notice)
                result = _notice_to_dict(notice)
        except (RuntimeError, SQLAlchemyError):
            return failure("来客同步库未配置", status_code=503)
        return success(result)

    @router.put("/{notice_id}")
    async def update_notice(request: Request, notice_id: int):
        if not _has_demo_session(request):
            return failure("未授权", status_code=401)
        payload = await _request_payload(request)
        try:
            with request.app.state.laike_session_factory() as session:
                row = session.scalar(
                    select(SystemNotice).where(SystemNotice.id == notice_id)
                )
                if row is None:
                    return failure("公告不存在", status_code=404)
                if "title" in payload:
                    row.title = str(payload.get("title", "")).strip() or row.title
                if "content" in payload:
                    row.content = (
                        str(payload.get("content", "")).strip() or row.content
                    )
                if "notice_type" in payload:
                    row.notice_type = (
                        str(payload.get("notice_type", "")).strip()
                        or row.notice_type
                    )
                if "is_published" in payload:
                    row.is_published = bool(payload.get("is_published"))
                session.commit()
                session.refresh(row)
                result = _notice_to_dict(row)
        except (RuntimeError, SQLAlchemyError):
            return failure("来客同步库未配置", status_code=503)
        return success(result)

    @router.delete("/{notice_id}")
    async def delete_notice(request: Request, notice_id: int):
        if not _has_demo_session(request):
            return failure("未授权", status_code=401)
        try:
            with request.app.state.laike_session_factory() as session:
                row = session.scalar(
                    select(SystemNotice).where(SystemNotice.id == notice_id)
                )
                if row is None:
                    return failure("公告不存在", status_code=404)
                session.delete(row)
                session.commit()
        except (RuntimeError, SQLAlchemyError):
            return failure("来客同步库未配置", status_code=503)
        return success({})

    return router


def _notice_to_dict(notice: SystemNotice) -> dict[str, Any]:
    return {
        "id": notice.id,
        "title": notice.title,
        "content": notice.content,
        "notice_type": notice.notice_type,
        "is_published": notice.is_published,
        "created_at": (
            notice.created_at.isoformat() if notice.created_at else None
        ),
        "updated_at": (
            notice.updated_at.isoformat() if notice.updated_at else None
        ),
    }

