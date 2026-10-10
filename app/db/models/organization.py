"""组织模块业务模型（按老系统前端源码一比一还原字段）。

部门、员工、账号、客服分类、客服组、客服组成员。
数据来源为本地业务库。
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Department(Base):
    """部门。老系统字段：department_name/type/ordid。"""

    __tablename__ = "department"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    # 部门类型：live 直播部门 / custom 转化部门 / maintenance 售后部门
    dept_type: Mapped[str] = mapped_column(String(32), nullable=False, default="live", server_default="live")
    # 排序号
    ordid: Mapped[int] = mapped_column(Integer, nullable=False, default=255, server_default="255")
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


class Staff(Base):
    """员工。老系统字段：nickname/mobile/name/department_id/service_cate_id/password/role。"""

    __tablename__ = "staff"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    nickname: Mapped[str | None] = mapped_column(String(128), nullable=True)
    mobile: Mapped[str | None] = mapped_column(String(32), nullable=True)
    department_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 客服分类（逗号分隔多个分类 id）
    service_cate_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # 登录密码（明文占位，正式应哈希）
    password: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # 角色：super/live_leader/custom_leader/live_staff/custom_staff/console_staff/maintenance_leader/maintenance_staff/staff
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="staff", server_default="staff")
    status: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


class Account(Base):
    """登录账号。老系统字段：account_name/account_id/check_msg/memo/status。"""

    __tablename__ = "account"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    # 账号名称（来客账号名）
    account_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # 来客账号ID
    account_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # 审核失败原因
    check_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    memo: Mapped[str | None] = mapped_column(Text, nullable=True)
    staff_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


class CustomServiceCate(Base):
    """客服分类。"""

    __tablename__ = "custom_service_cate"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


class CustomServiceGroup(Base):
    """客服组。老系统字段：name/allocation_type/department_id/web_hook/memo/ordid/status。"""

    __tablename__ = "custom_service_group"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    # 分配规则：轮询/权重等
    allocation_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    department_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 群报单机器人 WebHook 地址
    web_hook: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cate_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    memo: Mapped[str | None] = mapped_column(Text, nullable=True)
    ordid: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    status: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


class CustomServiceGroupMember(Base):
    """客服组成员。老系统字段：custom_uid/rate/day_limit_num/work_time。"""

    __tablename__ = "custom_service_group_member"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    group_id: Mapped[int] = mapped_column(Integer, nullable=False)
    staff_id: Mapped[int] = mapped_column(Integer, nullable=False)
    # 客服 uid
    custom_uid: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # 权重
    rate: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    # 每日接待限制
    day_limit_num: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    work_time: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


class AccountProduct(Base):
    """账号与商品（店铺/项目）的关联。老系统字段：product_id/out_product_id。"""

    __tablename__ = "account_product"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(Integer, nullable=False)
    product_id: Mapped[str] = mapped_column(String(255), nullable=False)
    # 直连商品编码
    out_product_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    product_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
