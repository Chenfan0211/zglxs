from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Boolean, DateTime, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class LaikeWebhookEvent(Base):
    __tablename__ = "laike_webhook_event"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    headers_json: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False)
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="received")
    claim_token: Mapped[str | None] = mapped_column(String(36), nullable=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class LaikeOrder(Base):
    __tablename__ = "laike_order"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider_order_id: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True
    )
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[str | None] = mapped_column(String(255), nullable=True)


class LaikeSyncCursor(Base):
    __tablename__ = "laike_sync_cursor"
    __table_args__ = (UniqueConstraint("account_id", name="uq_laike_sync_cursor_account"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[str] = mapped_column(String(255), nullable=False)
    cursor: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )


class LaikeSyncRun(Base):
    __tablename__ = "laike_sync_run"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="running")
    start_time: Mapped[str | None] = mapped_column(String(255), nullable=True)
    end_time: Mapped[str | None] = mapped_column(String(255), nullable=True)
    processed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
