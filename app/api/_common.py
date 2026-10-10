"""API 模块公共工具函数。

统一各业务模块重复的请求解析、演示会话校验、分页、序列化等工具，
避免在 order/live/finance/system/organization/notices 等模块间复制粘贴。
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qs

from fastapi import Request


def utcnow() -> datetime:
    """当前 UTC 时间。"""
    return datetime.now(timezone.utc)


async def payload(request: Request) -> dict[str, Any]:
    """合并 query 与 body（json / form-urlencoded）得到请求参数字典。"""
    result: dict[str, Any] = dict(request.query_params)
    body = await request.body()
    if not body:
        return result
    content_type = request.headers.get("content-type", "").lower()
    if "application/x-www-form-urlencoded" in content_type:
        parsed = parse_qs(body.decode("utf-8", errors="replace"), keep_blank_values=True)
        result.update({k: v[-1] for k, v in parsed.items() if v})
        return result
    try:
        parsed = json.loads(body)
    except (TypeError, json.JSONDecodeError):
        return result
    if isinstance(parsed, dict):
        result.update(parsed)
    return result


def has_demo_session(request: Request) -> bool:
    """判断请求是否携带有效的演示登录会话（Bearer DEMO- 或 access_token cookie）。"""
    authorization = request.headers.get("authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() == "bearer" and token.startswith("DEMO-"):
        return True
    return request.cookies.get("access_token", "").startswith("DEMO-")


def to_int(raw: Any, key: str = "id") -> int | None:
    """将原始值安全转换为 int；空值 / 非法值返回 None。"""
    del key  # 保留签名兼容历史调用
    try:
        return int(raw) if raw not in (None, "", "null") else None
    except (TypeError, ValueError):
        return None


def id_from_payload(payload: Mapping[str, Any], key: str = "id") -> int | None:
    """从参数字典中安全提取 int 主键。"""
    return to_int(payload.get(key))


def page(payload: Mapping[str, Any]) -> tuple[int, int]:
    """从参数字典解析分页 (page, size)，带上下限保护。"""
    try:
        page_num = max(1, int(payload.get("page", payload.get("page_num", 1))))
    except (TypeError, ValueError):
        page_num = 1
    try:
        size = max(1, min(200, int(payload.get("page_size", payload.get("limit", 20)))))
    except (TypeError, ValueError):
        size = 20
    return page_num, size


def serialize(value: Any) -> Any:
    """序列化 datetime 为 ISO 字符串，其余原样返回。"""
    if isinstance(value, datetime):
        return value.isoformat()
    return value
