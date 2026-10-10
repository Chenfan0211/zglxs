"""直播模块业务模型。

直播间、直播间成员（主播）、直播间中控、工作日志。
数据来源为本地业务库。
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class LiveRoom(Base):
    """直播间。"""

    __tablename__ = "live_room"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    # 抖音 uid
    live_uid: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # 抖音号
    live_uuid: Mapped[str | None] = mapped_column(String(128), nullable=True)
    department_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    room_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    memo: Mapped[str | None] = mapped_column(Text, nullable=True)
    ordid: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    status: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


class LiveRoomMember(Base):
    """直播间成员（主播）。"""

    __tablename__ = "live_room_member"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    live_room_id: Mapped[int] = mapped_column(Integer, nullable=False)
    staff_id: Mapped[int] = mapped_column(Integer, nullable=False)
    # 主播 uid
    anchor_uid: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # 是否场控
    is_control: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="anchor", server_default="anchor")
    status: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


class LiveRoomConsole(Base):
    """直播间中控。"""

    __tablename__ = "live_room_console"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    live_room_id: Mapped[int] = mapped_column(Integer, nullable=False)
    staff_id: Mapped[int] = mapped_column(Integer, nullable=False)
    # 中控 uid
    console_uid: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


class WorkLog(Base):
    """工作日志（排班/上下班）。"""

    __tablename__ = "work_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    live_room_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    staff_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    work_type: Mapped[str] = mapped_column(String(32), nullable=False, default="start", server_default="start")
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


class CustomGroupLiveRoom(Base):
    """客服组与直播间的关联。"""

    __tablename__ = "custom_group_live_room"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    group_id: Mapped[int] = mapped_column(Integer, nullable=False)
    live_room_id: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
