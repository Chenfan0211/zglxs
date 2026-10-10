"""系统模块接口。

系统配置、版本信息、表格列设置。
路径遵循老系统 /apiv1/common/* 与 /apiv1/user/* 约定，方法统一 POST。
"""

from __future__ import annotations


from fastapi import APIRouter, Request
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.api.responses import failure, success
from app.api._common import utcnow as _utcnow, payload as _payload, has_demo_session as _has_demo_session, serialize as _serialize
from app.db.models.system_config import SystemConfig, TableColumnSetting


def create_system_router() -> APIRouter:
    router = APIRouter()

    # ---------- 系统配置 ----------
    async def get_config_info(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        try:
            with request.app.state.laike_session_factory() as session:
                rows = session.scalars(select(SystemConfig)).all()
                config = {r.config_key: r.config_value for r in rows}
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success({
            "name": config.get("web_name", "抖音订单管理系统"),
            "logo": config.get("logo"),
            "web_name": config.get("web_name", "抖音订单管理系统"),
            "config": config,
        })

    async def update_config_info(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        try:
            with request.app.state.laike_session_factory() as session:
                updated = []
                for key, value in payload.items():
                    if key in ("id", "action", "controller"):
                        continue
                    row = session.scalar(select(SystemConfig).where(SystemConfig.config_key == key))
                    if row is None:
                        row = SystemConfig(config_key=key, config_value=str(value))
                        session.add(row)
                    else:
                        row.config_value = str(value)
                    row.updated_at = _utcnow()
                    updated.append(key)
                session.commit()
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success({"updated": updated})

    # ---------- 版本信息 ----------
    async def get_upversion_num(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        try:
            with request.app.state.laike_session_factory() as session:
                row = session.scalar(select(SystemConfig).where(SystemConfig.config_key == "upversion_num"))
                num = int(row.config_value) if row and row.config_value else 0
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success({"num": num})

    async def get_upversion_info(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        try:
            with request.app.state.laike_session_factory() as session:
                row = session.scalar(select(SystemConfig).where(SystemConfig.config_key == "upversion_info"))
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success({
            "version": row.config_value if row else None,
            "content": None,
            "update_time": None,
        })

    # ---------- 表格列设置 ----------
    async def table_column_detail(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        table_key = str(payload.get("table_key", "")).strip()
        user_key = str(payload.get("user_key", "default")).strip() or "default"
        if not table_key:
            return failure("缺少 table_key", status_code=400)
        try:
            with request.app.state.laike_session_factory() as session:
                row = session.scalar(select(TableColumnSetting).where(TableColumnSetting.table_key == table_key, TableColumnSetting.user_key == user_key))
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success({"content": row.content if row else ""})

    async def table_column_edit(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        table_key = str(payload.get("table_key", "")).strip()
        user_key = str(payload.get("user_key", "default")).strip() or "default"
        content = str(payload.get("content", ""))
        if not table_key:
            return failure("缺少 table_key", status_code=400)
        try:
            with request.app.state.laike_session_factory() as session:
                row = session.scalar(select(TableColumnSetting).where(TableColumnSetting.table_key == table_key, TableColumnSetting.user_key == user_key))
                if row is None:
                    row = TableColumnSetting(table_key=table_key, user_key=user_key, content=content)
                    session.add(row)
                else:
                    row.content = content
                row.updated_at = _utcnow()
                session.commit()
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success({})


    # ---------- 表格列设置删除 ----------
    async def table_column_del(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        table_key = str(payload.get("table_key", "")).strip()
        user_key = str(payload.get("user_key", "default")).strip() or "default"
        if not table_key:
            return failure("缺少 table_key", status_code=400)
        try:
            with request.app.state.laike_session_factory() as session:
                row = session.scalar(select(TableColumnSetting).where(TableColumnSetting.table_key == table_key, TableColumnSetting.user_key == user_key))
                if row is not None:
                    session.delete(row)
                    session.commit()
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success({})

    # ---------- 公告已读标记 ----------
    async def notice_changeview(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        return success({})

    # ---------- 短信/手机号座位管理（外部集成占位） ----------
    async def mobile_stub(request: Request, message: str):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        return failure(message, status_code=501)

    async def mobile_config_update(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        from app.db.models.system_config import SystemConfig
        try:
            with request.app.state.laike_session_factory() as session:
                for key, value in payload.items():
                    if key in ("id", "action", "controller"):
                        continue
                    row = session.scalar(select(SystemConfig).where(SystemConfig.config_key == f"mobile_{key}"))
                    if row is None:
                        row = SystemConfig(config_key=f"mobile_{key}", config_value=str(value))
                        session.add(row)
                    else:
                        row.config_value = str(value)
                    row.updated_at = _utcnow()
                session.commit()
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success({})


    async def mobile_external_stub(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        return failure("短信/手机号/微信服务未配置，需接入外部服务商", status_code=501)


    # ---------- 手机号/短信/微信只读查询（外部集成占位） ----------
    async def mobile_read_stub(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        return success({"list": [], "total": 0})

    async def mobile_config_read(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        return success({"enabled": None, "config": {}})

    async def mobile_qrcode_read(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        return success({"qrcode": None, "status": None, "expire_time": None})



    # ---------- 公告列表（老系统路径 user/notices/index） ----------
    async def notices_index(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        from app.db.models.system import SystemNotice
        try:
            with request.app.state.laike_session_factory() as session:
                rows = session.scalars(select(SystemNotice).order_by(SystemNotice.id.desc()).limit(50)).all()
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success({
            "total": len(rows),
            "list": [{f: _serialize(getattr(r, f)) for f in ["id", "title", "content", "notice_type", "is_published", "created_at"]} for r in rows],
            "notice_type_list": [{"key": "system", "value": "系统"}],
        })


    routes = {
        "/apiv1/common/getconfiginfo": get_config_info,
        "/apiv1/common/updateconfiginfo": update_config_info,
        "/apiv1/common/getupversionnum": get_upversion_num,
        "/apiv1/common/getupversioninfo": get_upversion_info,
        "/apiv1/user/usertablecolumns/detail": table_column_detail,
        "/apiv1/user/usertablecolumns/edit": table_column_edit,
        "/apiv1/user/usertablecolumns/del": table_column_del,
        "/apiv1/user/notices/changeview": notice_changeview,
        "/apiv1/user/notices/index": notices_index,
        "/apiv1/user/mobiles/addseat": mobile_external_stub,
        "/apiv1/user/mobiles/delseat": mobile_external_stub,
        "/apiv1/user/mobiles/editseat": mobile_external_stub,
        "/apiv1/user/mobiles/createcall": mobile_external_stub,
        "/apiv1/user/mobiles/changerenewstatus": mobile_external_stub,
        "/apiv1/user/mobiles/delwechat": mobile_external_stub,
        "/apiv1/user/mobiles/sendsms": mobile_external_stub,
        "/apiv1/user/mobiles/updatewechat": mobile_external_stub,
        "/apiv1/user/sms/send": mobile_external_stub,
        "/apiv1/user/mobiles/updateconfiginfo": mobile_config_update,
        "/apiv1/user/mobiles/updatemobilecheckinfo": mobile_config_update,
        "/apiv1/user/mobiles/updatesmsinfo": mobile_config_update,
        "/apiv1/user/mobiles/updatesmstemplete": mobile_config_update,
        "/apiv1/user/mobiles/calllog": mobile_read_stub,
        "/apiv1/user/mobiles/getconfiginfo": mobile_config_read,
        "/apiv1/user/mobiles/getmobilecheckinfo": mobile_config_read,
        "/apiv1/user/mobiles/getqrcodeinfo": mobile_qrcode_read,
        "/apiv1/user/mobiles/getqrcodestatus": mobile_qrcode_read,
        "/apiv1/user/mobiles/getsmsinfo": mobile_config_read,
        "/apiv1/user/mobiles/getsmstemplete": mobile_read_stub,
        "/apiv1/user/mobiles/searchseat": mobile_read_stub,
        "/apiv1/user/mobiles/seatlist": mobile_read_stub,
        "/apiv1/user/mobiles/wechatlist": mobile_read_stub,
    }
    for path, handler in routes.items():
        router.add_api_route(path, handler, methods=["POST"])

    return router
