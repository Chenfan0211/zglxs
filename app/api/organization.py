"""组织模块接口（按老系统前端源码还原字段）。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from app.api.responses import failure, success
from app.api._common import utcnow as _utcnow, payload as _payload, has_demo_session as _has_demo_session, page as _page, serialize as _serialize, id_from_payload as _id, to_int as _int
from app.db.models.organization import (
    Account,
    AccountProduct,
    CustomServiceCate,
    CustomServiceGroup,
    CustomServiceGroupMember,
    Department,
    Staff,
)
from app.db.models.system_config import SystemConfig


def _rows(session, stmt):
    return session.scalars(stmt).all()


def _to_dict(row: Any, fields: list[str]) -> dict[str, Any]:
    return {f: _serialize(getattr(row, f)) for f in fields}


DEPT_TYPE_MAP = {"live": "直播部门", "custom": "转化部门", "maintenance": "售后部门"}

ROLE_MAP = {
    "super": "超级管理员",
    "live_leader": "直播部门负责人",
    "custom_leader": "转化部门负责人",
    "live_staff": "直播员工",
    "custom_staff": "转化客服",
    "console_staff": "中控员工",
    "maintenance_leader": "售后部门负责人",
    "maintenance_staff": "售后员工",
    "staff": "普通员工",
}


def create_organization_router() -> APIRouter:
    router = APIRouter()

    # ================= 部门 =================
    async def departments_index(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        page, size = _page(payload)
        try:
            with request.app.state.laike_session_factory() as session:
                stmt = select(Department).order_by(Department.ordid, Department.id)
                keyword = str(payload.get("department_name", "")).strip()
                dept_type = str(payload.get("type", "")).strip()
                if keyword:
                    stmt = stmt.where(Department.name.like(f"%{keyword}%"))
                if dept_type and dept_type != "0":
                    stmt = stmt.where(Department.dept_type == dept_type)
                total = int(session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0)
                rows = _rows(session, stmt.offset((page - 1) * size).limit(size))
                user_nums = {}
                for r in rows:
                    user_nums[r.id] = int(session.scalar(select(func.count()).select_from(Staff).where(Staff.department_id == r.id)) or 0)
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        list_data = []
        for r in rows:
            d = _to_dict(r, ["id", "name", "dept_type", "ordid"])
            d["department_name"] = r.name
            d["type"] = r.dept_type
            d["type_str"] = DEPT_TYPE_MAP.get(r.dept_type, r.dept_type)
            d["user_num"] = user_nums.get(r.id, 0)
            list_data.append(d)
        return success({
            "total": total,
            "list": list_data,
            "department_type_list": [{"key": k, "value": v} for k, v in DEPT_TYPE_MAP.items()],
        })

    async def departments_add(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        name = str(payload.get("department_name", payload.get("name", ""))).strip()
        if not name:
            return failure("部门名称不能为空", status_code=400)
        try:
            with request.app.state.laike_session_factory() as session:
                row = Department(
                    name=name,
                    dept_type=str(payload.get("type", "live")).strip() or "live",
                    ordid=_int(payload.get("ordid", 255)) or 255,
                    remark=str(payload.get("remark", "")).strip() or None,
                )
                session.add(row)
                session.commit()
                session.refresh(row)
                result = _to_dict(row, ["id", "name", "dept_type", "ordid"])
                result["department_name"] = row.name
                result["type"] = row.dept_type
                result["type_str"] = DEPT_TYPE_MAP.get(row.dept_type, row.dept_type)
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success(result)

    async def departments_edit(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        row_id = _id(payload)
        if row_id is None:
            return failure("缺少 id", status_code=400)
        try:
            with request.app.state.laike_session_factory() as session:
                row = session.scalar(select(Department).where(Department.id == row_id))
                if row is None:
                    return failure("部门不存在", status_code=404)
                if "department_name" in payload or "name" in payload:
                    row.name = str(payload.get("department_name", payload.get("name", ""))).strip() or row.name
                if "type" in payload:
                    row.dept_type = str(payload.get("type", "")).strip() or row.dept_type
                if "ordid" in payload:
                    row.ordid = _int(payload.get("ordid", 255)) or 255
                row.updated_at = _utcnow()
                session.commit()
                result = _to_dict(row, ["id", "name", "dept_type", "ordid"])
                result["department_name"] = row.name
                result["type"] = row.dept_type
                result["type_str"] = DEPT_TYPE_MAP.get(row.dept_type, row.dept_type)
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success(result)

    async def departments_del(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        row_id = _id(payload)
        if row_id is None:
            return failure("缺少 id", status_code=400)
        try:
            with request.app.state.laike_session_factory() as session:
                row = session.scalar(select(Department).where(Department.id == row_id))
                if row is None:
                    return failure("部门不存在", status_code=404)
                session.delete(row)
                session.commit()
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success({})

    async def departments_search(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        try:
            with request.app.state.laike_session_factory() as session:
                stmt = select(Department).order_by(Department.id)
                keyword = str(payload.get("keyword", "")).strip()
                if keyword:
                    stmt = stmt.where(Department.name.like(f"%{keyword}%"))
                rows = _rows(session, stmt.limit(50))
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success({"list": [{"id": r.id, "department_name": r.name, "type": r.dept_type} for r in rows]})


    # ================= 员工 =================
    async def staff_index(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        page, size = _page(payload)
        try:
            with request.app.state.laike_session_factory() as session:
                stmt = select(Staff).order_by(Staff.id.desc())
                keyword = str(payload.get("keyword", "")).strip()
                department_id = _id(payload, "department_id")
                if keyword:
                    stmt = stmt.where(Staff.name.like(f"%{keyword}%") | Staff.nickname.like(f"%{keyword}%") | Staff.mobile.like(f"%{keyword}%"))
                if department_id is not None:
                    stmt = stmt.where(Staff.department_id == department_id)
                total = int(session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0)
                rows = _rows(session, stmt.offset((page - 1) * size).limit(size))
                dept_map = {}
                dept_ids = {r.department_id for r in rows if r.department_id}
                if dept_ids:
                    depts = _rows(session, select(Department).where(Department.id.in_(dept_ids)))
                    dept_map = {d.id: d.name for d in depts}
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        list_data = []
        for r in rows:
            d = _to_dict(r, ["id", "name", "nickname", "mobile", "department_id", "service_cate_id", "role", "status"])
            d["department_name"] = dept_map.get(r.department_id, "")
            d["role_str"] = ROLE_MAP.get(r.role, r.role)
            list_data.append(d)
        return success({"total": total, "list": list_data})

    async def staff_add(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        name = str(payload.get("name", "")).strip()
        if not name:
            return failure("员工姓名不能为空", status_code=400)
        try:
            with request.app.state.laike_session_factory() as session:
                row = Staff(
                    name=name,
                    nickname=str(payload.get("nickname", "")).strip() or None,
                    mobile=str(payload.get("mobile", "")).strip() or None,
                    department_id=_id(payload, "department_id"),
                    service_cate_id=str(payload.get("service_cate_id", "")).strip() or None,
                    password=str(payload.get("password", "")).strip() or None,
                    role=str(payload.get("role", "staff")).strip() or "staff",
                )
                session.add(row)
                session.commit()
                session.refresh(row)
                result = _to_dict(row, ["id", "name", "nickname", "mobile", "department_id", "service_cate_id", "role"])
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success(result)

    async def staff_edit(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        row_id = _id(payload)
        if row_id is None:
            return failure("缺少 id", status_code=400)
        try:
            with request.app.state.laike_session_factory() as session:
                row = session.scalar(select(Staff).where(Staff.id == row_id))
                if row is None:
                    return failure("员工不存在", status_code=404)
                for key, field in (("name", "name"), ("nickname", "nickname"), ("mobile", "mobile"), ("role", "role"), ("service_cate_id", "service_cate_id")):
                    if key in payload:
                        setattr(row, field, str(payload.get(key, "")).strip() or None)
                if "department_id" in payload:
                    row.department_id = _id(payload, "department_id")
                if "password" in payload and payload.get("password"):
                    row.password = str(payload.get("password", ""))
                row.updated_at = _utcnow()
                session.commit()
                result = _to_dict(row, ["id", "name", "nickname", "mobile", "department_id", "service_cate_id", "role"])
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success(result)

    async def staff_del(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        row_id = _id(payload)
        if row_id is None:
            return failure("缺少 id", status_code=400)
        try:
            with request.app.state.laike_session_factory() as session:
                row = session.scalar(select(Staff).where(Staff.id == row_id))
                if row is None:
                    return failure("员工不存在", status_code=404)
                session.delete(row)
                session.commit()
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success({})

    async def staff_change(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        row_id = _id(payload)
        if row_id is None:
            return failure("缺少 id", status_code=400)
        try:
            with request.app.state.laike_session_factory() as session:
                row = session.scalar(select(Staff).where(Staff.id == row_id))
                if row is None:
                    return failure("员工不存在", status_code=404)
                if "status" in payload:
                    row.status = bool(payload.get("status"))
                if "role" in payload:
                    row.role = str(payload.get("role", "")).strip() or row.role
                row.updated_at = _utcnow()
                session.commit()
                result = _to_dict(row, ["id", "name", "nickname", "role", "status"])
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success(result)

    async def staff_changecustomstatus(request: Request):
        return await staff_change(request)

    async def staff_getauthinfo(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        row_id = _id(payload)
        try:
            with request.app.state.laike_session_factory() as session:
                if row_id is None:
                    return success({"roles": [], "permissions": []})
                row = session.scalar(select(Staff).where(Staff.id == row_id))
                if row is None:
                    return failure("员工不存在", status_code=404)
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success({"id": row.id, "name": row.name, "role": row.role, "permissions": []})

    async def staff_updateauthinfo(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        row_id = _id(payload)
        if row_id is None:
            return failure("缺少 id", status_code=400)
        return success({"id": row_id})


    # ================= 账号 =================
    async def accounts_index(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        page, size = _page(payload)
        try:
            with request.app.state.laike_session_factory() as session:
                stmt = select(Account).order_by(Account.id.desc())
                keyword = str(payload.get("keyword", "")).strip()
                if keyword:
                    stmt = stmt.where(Account.username.like(f"%{keyword}%") | Account.account_name.like(f"%{keyword}%") | Account.account_id.like(f"%{keyword}%"))
                total = int(session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0)
                rows = _rows(session, stmt.offset((page - 1) * size).limit(size))
                product_nums = {}
                for r in rows:
                    product_nums[r.id] = int(session.scalar(select(func.count()).select_from(AccountProduct).where(AccountProduct.account_id == r.id)) or 0)
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        list_data = []
        for r in rows:
            d = _to_dict(r, ["id", "username", "account_name", "account_id", "check_msg", "memo", "status"])
            d["product_num"] = product_nums.get(r.id, 0)
            d["status_str"] = "正常" if r.status else "禁用"
            list_data.append(d)
        return success({"total": total, "list": list_data})

    async def accounts_add(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        username = str(payload.get("username", "")).strip()
        password = str(payload.get("password", ""))
        if not username or not password:
            return failure("账号和密码不能为空", status_code=400)
        import hashlib
        try:
            with request.app.state.laike_session_factory() as session:
                exists = session.scalar(select(Account).where(Account.username == username))
                if exists is not None:
                    return failure("账号已存在", status_code=400)
                row = Account(
                    username=username,
                    password_hash=hashlib.sha256(password.encode("utf-8")).hexdigest(),
                    account_name=str(payload.get("account_name", "")).strip() or None,
                    account_id=str(payload.get("account_id", "")).strip() or None,
                    check_msg=str(payload.get("check_msg", "")).strip() or None,
                    memo=str(payload.get("memo", "")).strip() or None,
                    staff_id=_id(payload, "staff_id"),
                    status=bool(payload.get("status", 1)),
                )
                session.add(row)
                session.commit()
                session.refresh(row)
                result = _to_dict(row, ["id", "username", "account_name", "account_id", "check_msg", "memo", "status"])
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success(result)

    async def accounts_edit(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        row_id = _id(payload)
        if row_id is None:
            return failure("缺少 id", status_code=400)
        import hashlib
        try:
            with request.app.state.laike_session_factory() as session:
                row = session.scalar(select(Account).where(Account.id == row_id))
                if row is None:
                    return failure("账号不存在", status_code=404)
                for key, field in (("account_name", "account_name"), ("account_id", "account_id"), ("check_msg", "check_msg"), ("memo", "memo")):
                    if key in payload:
                        setattr(row, field, str(payload.get(key, "")).strip() or None)
                if "staff_id" in payload:
                    row.staff_id = _id(payload, "staff_id")
                if "status" in payload:
                    row.status = bool(payload.get("status"))
                if payload.get("password"):
                    row.password_hash = hashlib.sha256(str(payload.get("password")).encode("utf-8")).hexdigest()
                row.updated_at = _utcnow()
                session.commit()
                result = _to_dict(row, ["id", "username", "account_name", "account_id", "check_msg", "memo", "status"])
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success(result)

    async def accounts_del(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        row_id = _id(payload)
        if row_id is None:
            return failure("缺少 id", status_code=400)
        try:
            with request.app.state.laike_session_factory() as session:
                row = session.scalar(select(Account).where(Account.id == row_id))
                if row is None:
                    return failure("账号不存在", status_code=404)
                session.delete(row)
                session.commit()
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success({})

    # ================= 账号-商品 =================
    async def account_product_list(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        account_id = _id(payload, "account_id")
        try:
            with request.app.state.laike_session_factory() as session:
                stmt = select(AccountProduct).order_by(AccountProduct.sort_order)
                if account_id is not None:
                    stmt = stmt.where(AccountProduct.account_id == account_id)
                rows = _rows(session, stmt)
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success({"list": [_to_dict(r, ["id", "account_id", "product_id", "out_product_id", "product_name", "sort_order"]) for r in rows]})

    async def account_product_add(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        account_id = _id(payload, "account_id")
        product_id = str(payload.get("product_id", "")).strip()
        if account_id is None or not product_id:
            return failure("账号和商品不能为空", status_code=400)
        try:
            with request.app.state.laike_session_factory() as session:
                row = AccountProduct(
                    account_id=account_id,
                    product_id=product_id,
                    out_product_id=str(payload.get("out_product_id", "")).strip() or None,
                    product_name=str(payload.get("product_name", "")).strip() or None,
                    sort_order=int(payload.get("sort_order", 0) or 0),
                )
                session.add(row)
                session.commit()
                session.refresh(row)
                result = _to_dict(row, ["id", "account_id", "product_id", "out_product_id", "product_name", "sort_order"])
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success(result)

    async def account_product_edit(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        row_id = _id(payload)
        if row_id is None:
            return failure("缺少 id", status_code=400)
        try:
            with request.app.state.laike_session_factory() as session:
                row = session.scalar(select(AccountProduct).where(AccountProduct.id == row_id))
                if row is None:
                    return failure("关联不存在", status_code=404)
                if "product_name" in payload:
                    row.product_name = str(payload.get("product_name", "")).strip() or None
                if "out_product_id" in payload:
                    row.out_product_id = str(payload.get("out_product_id", "")).strip() or None
                if "sort_order" in payload:
                    row.sort_order = int(payload.get("sort_order", 0) or 0)
                row.updated_at = _utcnow()
                session.commit()
                result = _to_dict(row, ["id", "account_id", "product_id", "out_product_id", "product_name", "sort_order"])
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success(result)

    async def account_product_del(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        row_id = _id(payload)
        if row_id is None:
            return failure("缺少 id", status_code=400)
        try:
            with request.app.state.laike_session_factory() as session:
                row = session.scalar(select(AccountProduct).where(AccountProduct.id == row_id))
                if row is None:
                    return failure("关联不存在", status_code=404)
                session.delete(row)
                session.commit()
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success({})


    # ================= 客服分类 =================
    async def cate_index(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        page, size = _page(payload)
        try:
            with request.app.state.laike_session_factory() as session:
                stmt = select(CustomServiceCate).order_by(CustomServiceCate.id.desc())
                total = int(session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0)
                rows = _rows(session, stmt.offset((page - 1) * size).limit(size))
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success({"total": total, "list": [_to_dict(r, ["id", "name", "status", "created_at"]) for r in rows]})

    async def cate_add(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        name = str(payload.get("name", "")).strip()
        if not name:
            return failure("分类名称不能为空", status_code=400)
        try:
            with request.app.state.laike_session_factory() as session:
                row = CustomServiceCate(name=name, status=bool(payload.get("status", 1)))
                session.add(row)
                session.commit()
                session.refresh(row)
                result = _to_dict(row, ["id", "name", "status"])
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success(result)

    async def cate_edit(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        row_id = _id(payload)
        if row_id is None:
            return failure("缺少 id", status_code=400)
        try:
            with request.app.state.laike_session_factory() as session:
                row = session.scalar(select(CustomServiceCate).where(CustomServiceCate.id == row_id))
                if row is None:
                    return failure("分类不存在", status_code=404)
                if "name" in payload:
                    row.name = str(payload.get("name", "")).strip() or row.name
                if "status" in payload:
                    row.status = bool(payload.get("status"))
                row.updated_at = _utcnow()
                session.commit()
                result = _to_dict(row, ["id", "name", "status"])
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success(result)

    async def cate_del(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        row_id = _id(payload)
        if row_id is None:
            return failure("缺少 id", status_code=400)
        try:
            with request.app.state.laike_session_factory() as session:
                row = session.scalar(select(CustomServiceCate).where(CustomServiceCate.id == row_id))
                if row is None:
                    return failure("分类不存在", status_code=404)
                session.delete(row)
                session.commit()
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success({})

    async def cate_search(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        try:
            with request.app.state.laike_session_factory() as session:
                stmt = select(CustomServiceCate).order_by(CustomServiceCate.id)
                keyword = str(payload.get("keyword", "")).strip()
                if keyword:
                    stmt = stmt.where(CustomServiceCate.name.like(f"%{keyword}%"))
                rows = _rows(session, stmt.limit(50))
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success({"list": [_to_dict(r, ["id", "name"]) for r in rows]})

    # ================= 客服组 =================
    async def group_index(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        page, size = _page(payload)
        try:
            with request.app.state.laike_session_factory() as session:
                stmt = select(CustomServiceGroup).order_by(CustomServiceGroup.ordid, CustomServiceGroup.id)
                keyword = str(payload.get("keyword", "")).strip()
                if keyword:
                    stmt = stmt.where(CustomServiceGroup.name.like(f"%{keyword}%"))
                total = int(session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0)
                rows = _rows(session, stmt.offset((page - 1) * size).limit(size))
                dept_map = {}
                dept_ids = {r.department_id for r in rows if r.department_id}
                if dept_ids:
                    depts = _rows(session, select(Department).where(Department.id.in_(dept_ids)))
                    dept_map = {d.id: d.name for d in depts}
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        list_data = []
        for r in rows:
            d = _to_dict(r, ["id", "name", "allocation_type", "department_id", "web_hook", "memo", "ordid", "status"])
            d["department_name"] = dept_map.get(r.department_id, "")
            list_data.append(d)
        return success({"total": total, "list": list_data})

    async def group_add(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        name = str(payload.get("name", "")).strip()
        if not name:
            return failure("组名称不能为空", status_code=400)
        try:
            with request.app.state.laike_session_factory() as session:
                row = CustomServiceGroup(
                    name=name,
                    allocation_type=str(payload.get("allocation_type", "")).strip() or None,
                    department_id=_id(payload, "department_id"),
                    web_hook=str(payload.get("web_hook", "")).strip() or None,
                    memo=str(payload.get("memo", "")).strip() or None,
                    ordid=_int(payload.get("ordid", 0)) or 0,
                    cate_id=_id(payload, "cate_id"),
                    status=bool(payload.get("status", 1)),
                )
                session.add(row)
                session.commit()
                session.refresh(row)
                result = _to_dict(row, ["id", "name", "allocation_type", "department_id", "web_hook", "memo", "ordid", "status"])
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success(result)

    async def group_edit(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        row_id = _id(payload)
        if row_id is None:
            return failure("缺少 id", status_code=400)
        try:
            with request.app.state.laike_session_factory() as session:
                row = session.scalar(select(CustomServiceGroup).where(CustomServiceGroup.id == row_id))
                if row is None:
                    return failure("组不存在", status_code=404)
                for key, field in (("name", "name"), ("allocation_type", "allocation_type"), ("web_hook", "web_hook"), ("memo", "memo")):
                    if key in payload:
                        setattr(row, field, str(payload.get(key, "")).strip() or None)
                if "department_id" in payload:
                    row.department_id = _id(payload, "department_id")
                if "cate_id" in payload:
                    row.cate_id = _id(payload, "cate_id")
                if "ordid" in payload:
                    row.ordid = _int(payload.get("ordid", 0)) or 0
                if "status" in payload:
                    row.status = bool(payload.get("status"))
                row.updated_at = _utcnow()
                session.commit()
                result = _to_dict(row, ["id", "name", "allocation_type", "department_id", "web_hook", "memo", "ordid", "status"])
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success(result)

    async def group_del(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        row_id = _id(payload)
        if row_id is None:
            return failure("缺少 id", status_code=400)
        try:
            with request.app.state.laike_session_factory() as session:
                row = session.scalar(select(CustomServiceGroup).where(CustomServiceGroup.id == row_id))
                if row is None:
                    return failure("组不存在", status_code=404)
                session.delete(row)
                session.commit()
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success({})

    async def group_changestatus(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        row_id = _id(payload)
        if row_id is None:
            return failure("缺少 id", status_code=400)
        try:
            with request.app.state.laike_session_factory() as session:
                row = session.scalar(select(CustomServiceGroup).where(CustomServiceGroup.id == row_id))
                if row is None:
                    return failure("组不存在", status_code=404)
                row.status = bool(payload.get("status"))
                row.updated_at = _utcnow()
                session.commit()
                result = _to_dict(row, ["id", "name", "status"])
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success(result)

    async def group_search(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        try:
            with request.app.state.laike_session_factory() as session:
                stmt = select(CustomServiceGroup).order_by(CustomServiceGroup.id)
                keyword = str(payload.get("keyword", "")).strip()
                if keyword:
                    stmt = stmt.where(CustomServiceGroup.name.like(f"%{keyword}%"))
                rows = _rows(session, stmt.limit(50))
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success({"list": [_to_dict(r, ["id", "name"]) for r in rows]})


    # ================= 客服组成员 =================
    async def member_index(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        page, size = _page(payload)
        group_id = _id(payload, "group_id")
        try:
            with request.app.state.laike_session_factory() as session:
                stmt = select(CustomServiceGroupMember).order_by(CustomServiceGroupMember.id.desc())
                if group_id is not None:
                    stmt = stmt.where(CustomServiceGroupMember.group_id == group_id)
                total = int(session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0)
                rows = _rows(session, stmt.offset((page - 1) * size).limit(size))
                staff_ids = {r.staff_id for r in rows}
                staff_map = {}
                if staff_ids:
                    staffs = _rows(session, select(Staff).where(Staff.id.in_(staff_ids)))
                    staff_map = {s.id: s for s in staffs}
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        list_data = []
        for r in rows:
            d = _to_dict(r, ["id", "group_id", "staff_id", "custom_uid", "rate", "day_limit_num", "status", "work_time"])
            s = staff_map.get(r.staff_id)
            d["custom_name"] = (s.nickname or s.name) if s else ""
            list_data.append(d)
        return success({"total": total, "list": list_data})

    async def member_add(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        group_id = _id(payload, "group_id")
        staff_id = _id(payload, "staff_id")
        if group_id is None or staff_id is None:
            return failure("组和成员不能为空", status_code=400)
        try:
            with request.app.state.laike_session_factory() as session:
                row = CustomServiceGroupMember(
                    group_id=group_id,
                    staff_id=staff_id,
                    custom_uid=str(payload.get("custom_uid", "")).strip() or None,
                    rate=_int(payload.get("rate", 0)) or 0,
                    day_limit_num=_int(payload.get("day_limit_num")),
                    status=bool(payload.get("status", 1)),
                    work_time=str(payload.get("work_time", "")).strip() or None,
                )
                session.add(row)
                session.commit()
                session.refresh(row)
                result = _to_dict(row, ["id", "group_id", "staff_id", "custom_uid", "rate", "day_limit_num", "status", "work_time"])
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success(result)

    async def member_edit(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        row_id = _id(payload)
        if row_id is None:
            return failure("缺少 id", status_code=400)
        try:
            with request.app.state.laike_session_factory() as session:
                row = session.scalar(select(CustomServiceGroupMember).where(CustomServiceGroupMember.id == row_id))
                if row is None:
                    return failure("成员不存在", status_code=404)
                if "group_id" in payload:
                    row.group_id = _id(payload, "group_id")
                if "staff_id" in payload:
                    row.staff_id = _id(payload, "staff_id")
                if "custom_uid" in payload:
                    row.custom_uid = str(payload.get("custom_uid", "")).strip() or None
                if "rate" in payload:
                    row.rate = _int(payload.get("rate", 0)) or 0
                if "day_limit_num" in payload:
                    row.day_limit_num = _int(payload.get("day_limit_num"))
                if "status" in payload:
                    row.status = bool(payload.get("status"))
                if "work_time" in payload:
                    row.work_time = str(payload.get("work_time", "")).strip() or None
                row.updated_at = _utcnow()
                session.commit()
                result = _to_dict(row, ["id", "group_id", "staff_id", "custom_uid", "rate", "day_limit_num", "status", "work_time"])
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success(result)

    async def member_del(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        row_id = _id(payload)
        if row_id is None:
            return failure("缺少 id", status_code=400)
        try:
            with request.app.state.laike_session_factory() as session:
                row = session.scalar(select(CustomServiceGroupMember).where(CustomServiceGroupMember.id == row_id))
                if row is None:
                    return failure("成员不存在", status_code=404)
                session.delete(row)
                session.commit()
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success({})

    async def member_changestatus(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        row_id = _id(payload)
        if row_id is None:
            return failure("缺少 id", status_code=400)
        try:
            with request.app.state.laike_session_factory() as session:
                row = session.scalar(select(CustomServiceGroupMember).where(CustomServiceGroupMember.id == row_id))
                if row is None:
                    return failure("成员不存在", status_code=404)
                row.status = bool(payload.get("status"))
                row.updated_at = _utcnow()
                session.commit()
                result = _to_dict(row, ["id", "group_id", "staff_id", "status"])
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success(result)

    async def member_setworktime(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        row_id = _id(payload)
        if row_id is None:
            return failure("缺少 id", status_code=400)
        try:
            with request.app.state.laike_session_factory() as session:
                row = session.scalar(select(CustomServiceGroupMember).where(CustomServiceGroupMember.id == row_id))
                if row is None:
                    return failure("成员不存在", status_code=404)
                row.work_time = str(payload.get("work_time", "")).strip() or None
                row.updated_at = _utcnow()
                session.commit()
                result = _to_dict(row, ["id", "group_id", "staff_id", "work_time"])
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success(result)

    async def member_search(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        group_id = _id(payload, "group_id")
        try:
            with request.app.state.laike_session_factory() as session:
                stmt = select(CustomServiceGroupMember).order_by(CustomServiceGroupMember.id)
                if group_id is not None:
                    stmt = stmt.where(CustomServiceGroupMember.group_id == group_id)
                rows = _rows(session, stmt.limit(100))
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success({"list": [_to_dict(r, ["id", "group_id", "staff_id", "custom_uid", "rate", "day_limit_num", "work_time"]) for r in rows]})

    async def member_getworktime(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        row_id = _id(payload)
        try:
            with request.app.state.laike_session_factory() as session:
                if row_id is not None:
                    row = session.scalar(select(CustomServiceGroupMember).where(CustomServiceGroupMember.id == row_id))
                    if row is None:
                        return failure("成员不存在", status_code=404)
                    return success({"work_time": row.work_time})
                stmt = select(CustomServiceGroupMember).order_by(CustomServiceGroupMember.id)
                rows = _rows(session, stmt.limit(200))
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success({"list": [_to_dict(r, ["id", "group_id", "staff_id", "work_time"]) for r in rows]})

    # ================= 用户/认证 =================
    async def user_getinfo(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        return success({"id": 1, "user_id": 1, "mobile": "admin", "nickname": "测试管理员", "roles": ["demo:all"]})

    async def auth_register(request: Request):
        return failure("测试环境不开放注册", status_code=403)

    async def auth_resettoken(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        return success({})

    async def user_changepwd(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        old_pwd = str(payload.get("old_password", "")).strip()
        new_pwd = str(payload.get("new_password", "")).strip()
        if not old_pwd or not new_pwd:
            return failure("旧密码和新密码不能为空", status_code=400)
        return success({})

    async def user_changenoticeflg(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        return success({})

    async def set_system_upnum(request: Request):
        if not _has_demo_session(request):
            return failure("请先登录", status_code=401)
        payload = await _payload(request)
        try:
            with request.app.state.laike_session_factory() as session:
                row = session.scalar(select(SystemConfig).where(SystemConfig.config_key == "upversion_num"))
                if row is None:
                    row = SystemConfig(config_key="upversion_num", config_value=str(payload.get("num", 0)))
                    session.add(row)
                else:
                    row.config_value = str(payload.get("num", 0))
                row.updated_at = _utcnow()
                session.commit()
        except (RuntimeError, SQLAlchemyError):
            return failure("业务库未配置", status_code=503)
        return success({"num": int(payload.get("num", 0) or 0)})


    routes = {
        "/apiv1/user/departments/index": departments_index,
        "/apiv1/user/departments/add": departments_add,
        "/apiv1/user/departments/edit": departments_edit,
        "/apiv1/user/departments/del": departments_del,
        "/apiv1/user/departments/searchdepartment": departments_search,
        "/apiv1/user/staff/index": staff_index,
        "/apiv1/user/staff/add": staff_add,
        "/apiv1/user/staff/edit": staff_edit,
        "/apiv1/user/staff/del": staff_del,
        "/apiv1/user/staff/change": staff_change,
        "/apiv1/user/staff/changecustomstatus": staff_changecustomstatus,
        "/apiv1/user/staff/getauthinfo": staff_getauthinfo,
        "/apiv1/user/staff/updateauthinfo": staff_updateauthinfo,
        "/apiv1/user/accounts/index": accounts_index,
        "/apiv1/user/accounts/add": accounts_add,
        "/apiv1/user/accounts/edit": accounts_edit,
        "/apiv1/user/accounts/del": accounts_del,
        "/apiv1/user/accounts/productlist": account_product_list,
        "/apiv1/user/accounts/productadd": account_product_add,
        "/apiv1/user/accounts/productadd2": account_product_add,
        "/apiv1/user/accounts/productedit": account_product_edit,
        "/apiv1/user/accounts/productedit2": account_product_edit,
        "/apiv1/user/accounts/productdel": account_product_del,
        "/apiv1/user/accounts/productupdateorder": account_product_edit,
        "/apiv1/user/customservicecates/index": cate_index,
        "/apiv1/user/customservicecates/add": cate_add,
        "/apiv1/user/customservicecates/edit": cate_edit,
        "/apiv1/user/customservicecates/del": cate_del,
        "/apiv1/user/customservicecates/searchcate": cate_search,
        "/apiv1/user/customservicegroups/index": group_index,
        "/apiv1/user/customservicegroups/add": group_add,
        "/apiv1/user/customservicegroups/edit": group_edit,
        "/apiv1/user/customservicegroups/del": group_del,
        "/apiv1/user/customservicegroups/changestatus": group_changestatus,
        "/apiv1/user/customservicegroups/searchgroup": group_search,
        "/apiv1/user/customservicegroupmembers/index": member_index,
        "/apiv1/user/customservicegroupmembers/add": member_add,
        "/apiv1/user/customservicegroupmembers/edit": member_edit,
        "/apiv1/user/customservicegroupmembers/del": member_del,
        "/apiv1/user/customservicegroupmembers/changestatus": member_changestatus,
        "/apiv1/user/customservicegroupmembers/setworktime": member_setworktime,
        "/apiv1/user/customservicegroupmembers/searchmember": member_search,
        "/apiv1/user/customservicegroupmembers/getworktime": member_getworktime,
        "/apiv1/user/getinfo": user_getinfo,
        "/apiv1/user/register": auth_register,
        "/apiv1/user/resettoken": auth_resettoken,
        "/apiv1/user/user/register": auth_register,
        "/apiv1/user/user/changepwd": user_changepwd,
        "/apiv1/user/user/changenoticeflg": user_changenoticeflg,
        "/apiv1/user/setsystemupnum": set_system_upnum,
    }
    for path, handler in routes.items():
        router.add_api_route(path, handler, methods=["POST"])

    return router
