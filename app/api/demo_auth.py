from __future__ import annotations

import base64
import hmac
import json
import secrets
from collections.abc import Mapping
from html import escape
from urllib.parse import parse_qs

from fastapi import APIRouter, Request

from app.api.responses import failure, success
from app.core.settings import Settings


def create_demo_auth_router(settings: Settings) -> APIRouter:
    router = APIRouter()

    @router.post("/apiv1/common/captcha")
    async def captcha():
        if not _demo_enabled(settings):
            return failure("测试登录未启用", status_code=200)
        return success(
            {
                "content": _captcha_data_uri(settings.demo_captcha_code),
                "key": settings.demo_captcha_key,
            }
        )

    @router.post("/apiv1/user/user/login")
    async def login(request: Request):
        if not _demo_enabled(settings):
            return failure("测试登录未启用", status_code=200)
        if not settings.demo_login_username or not settings.demo_login_password:
            return failure("测试登录凭据未配置", status_code=200)

        payload = await _request_payload(request)
        mobile = str(payload.get("mobile", "")).strip()
        password = str(payload.get("password", ""))
        captcha_code = str(payload.get("captcha", "")).strip()
        captcha_key = str(payload.get("captcha_key", "")).strip()

        if not mobile or not password or not captcha_code:
            return failure("请输入账号、密码和验证码", status_code=200)
        if not hmac.compare_digest(captcha_key, settings.demo_captcha_key):
            return failure("验证码已失效，请刷新", status_code=200)
        if not hmac.compare_digest(captcha_code, settings.demo_captcha_code):
            return failure("验证码错误", status_code=200)
        if not (
            hmac.compare_digest(mobile, settings.demo_login_username)
            and hmac.compare_digest(password, settings.demo_login_password)
        ):
            return failure("测试账号或密码错误", status_code=200)

        token = f"DEMO-{secrets.token_urlsafe(24)}"
        auth_info = {
            "id": 1,
            "user_id": 1,
            "mobile": settings.demo_login_username,
            "nickname": "测试管理员",
            "group_id": 1,
            "menuPrivCodes": [{"privCode": "demo:all"}],
            "dashboardPrivCodes": [],
            "orderPrivCodes": [],
            "employLivePrivCodes": [],
            "employTransformPrivCodes": [],
            "employAfterServeCodes": [],
        }
        data = {
            **auth_info,
            "token": token,
            "auth_info": json.dumps(
                auth_info,
                ensure_ascii=False,
                separators=(",", ":"),
            ),
        }
        response = success(data)
        response.set_cookie(
            "access_token",
            token,
            httponly=False,
            samesite="lax",
        )
        return response

    @router.post("/apiv1/user/user/logout")
    async def logout():
        if not _demo_enabled(settings):
            return failure("测试登录未启用", status_code=200)
        response = success({})
        response.delete_cookie("access_token", path="/")
        return response

    return router


def _demo_enabled(settings: Settings) -> bool:
    allowed_environment = settings.app_env.lower() in {"test", "staging"} or (
        settings.environment.lower() in {"test", "staging"}
    )
    return settings.demo_login_enabled and allowed_environment


def _captcha_data_uri(code: str) -> str:
    safe_code = escape(code)
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="120" height="42" '
        'viewBox="0 0 120 42">'
        '<rect width="120" height="42" rx="4" fill="#f3f6fb"/>'
        '<path d="M5 10h110M5 32h110" stroke="#d8e1ef" stroke-width="1"/>'
        '<text x="60" y="29" text-anchor="middle" '
        'font-family="Arial,sans-serif" font-size="22" font-weight="700" '
        'letter-spacing="3" fill="#2f5bea">'
        f"{safe_code}</text></svg>"
    )
    encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


async def _request_payload(request: Request) -> Mapping[str, object]:
    body = await request.body()
    if not body:
        return {}

    content_type = request.headers.get("content-type", "").lower()
    if "application/json" in content_type:
        try:
            parsed = json.loads(body)
        except (TypeError, json.JSONDecodeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}

    parsed = parse_qs(body.decode("utf-8", errors="replace"), keep_blank_values=True)
    return {key: values[-1] for key, values in parsed.items() if values}
