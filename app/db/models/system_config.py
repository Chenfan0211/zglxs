"""系统配置业务模型。

系统配置（键值对）、表格列设置。
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SystemConfig(Base):
    """系统配置键值对。"""

    __tablename__ = "system_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    config_key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    config_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    remark: Mapped[str | None] = mapped_column(String(255), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


class TableColumnSetting(Base):
    """用户表格列设置。"""

    __tablename__ = "table_column_setting"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    table_key: Mapped[str] = mapped_column(String(128), nullable=False)
    user_key: Mapped[str] = mapped_column(String(128), nullable=False, default="default", server_default="default")
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
