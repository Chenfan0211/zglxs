"""订单业务扩展模型。

在来客订单（laike_order，真实同步数据）基础上，扩展跟进、分配、认领、备注等
业务操作数据。所有扩展数据存储在本地业务库，通过 provider_order_id 关联来客订单。
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class OrderFollow(Base):
    """订单跟进状态（客服/售后跟进）。"""

    __tablename__ = "order_follow"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider_order_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    follow_status: Mapped[str] = mapped_column(String(32), nullable=False, default="new", server_default="new")
    owner_staff_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    follow_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    memo: Mapped[str | None] = mapped_column(Text, nullable=True)
    tel: Mapped[str | None] = mapped_column(String(32), nullable=True)
    lock_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    # 分配相关
    custom_department_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    custom_service_group_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    custom_cate_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    custom_staff_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    custom_allocation_time: Mapped[str | None] = mapped_column(String(64), nullable=True)
    custom_allocation_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    maintenance_department_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    maintenance_staff_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 直播相关
    live_room_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    anchor_staff_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    console_staff_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sale_user_role: Mapped[str | None] = mapped_column(String(32), nullable=True)
    sale_channel: Mapped[str | None] = mapped_column(String(32), nullable=True)
    sale_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 财务相关
    add_price_fen: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    refund_money_fen: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    refund_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    cost_amount_fen: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    profit_amount_fen: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


class OrderFollowLog(Base):
    """订单跟进日志。"""

    __tablename__ = "order_follow_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider_order_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    staff_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


class OrderClaim(Base):
    """订单认领记录。"""

    __tablename__ = "order_claim"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider_order_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    staff_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="claimed", server_default="claimed")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


class FollowStatus(Base):
    """跟进状态配置。"""

    __tablename__ = "follow_status"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    status: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
