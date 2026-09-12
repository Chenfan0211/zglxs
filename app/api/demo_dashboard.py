from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any
from urllib.parse import parse_qs

from fastapi import APIRouter, Request

from app.api.responses import failure, success
from app.core.settings import Settings


_DEMO_DEPARTMENTS = [
    {"key": "DEMO-DEPT-001", "value": "DEMO 直播部门"},
]
_DEMO_CUSTOM_DEPARTMENTS = [
    {"key": "DEMO-CUSTOM-DEPT-001", "value": "DEMO 转化部门"},
]
_DEMO_MAINTENANCE_DEPARTMENTS = [
    {"key": "DEMO-AFTER-DEPT-001", "value": "DEMO 售后部门"},
]
_DEMO_LIVE_ROOMS = [
    {"id": "DEMO-LIVE-ROOM-001", "live_name": "DEMO 直播间 A"},
    {"id": "DEMO-LIVE-ROOM-002", "live_name": "DEMO 直播间 B"},
]
_DEMO_ANCHORS = [
    {"id": "DEMO-ANCHOR-001", "nickname": "DEMO 主播 A"},
    {"id": "DEMO-ANCHOR-002", "nickname": "DEMO 主播 B"},
]
_DEMO_SERVICE_GROUPS = [
    {"id": "DEMO-GROUP-001", "name": "DEMO 客服组"},
]
_DEMO_CUSTOMERS = [
    {"id": "DEMO-CUSTOMER-001", "nickname": "DEMO 客服 A"},
]
_DEMO_MAINTENANCE = [
    {"id": "DEMO-MAINTENANCE-001", "nickname": "DEMO 售后 A"},
]
_DEMO_CONSOLES = [
    {"id": "DEMO-CONSOLE-001", "nickname": "DEMO 中控 A"},
]


def create_demo_dashboard_router(settings: Settings) -> APIRouter:
    router = APIRouter()

    async def center(request: Request):
        if not _demo_enabled(settings):
            return _disabled()
        return success(
            {
                "info": _center_info(),
                "department_list": _DEMO_DEPARTMENTS,
                "custom_department_list": _DEMO_CUSTOM_DEPARTMENTS,
                "maintenance_department_list": _DEMO_MAINTENANCE_DEPARTMENTS,
            }
        )

    async def live_rooms(request: Request):
        return _list_response(settings, _DEMO_LIVE_ROOMS)

    async def anchors(request: Request):
        return _list_response(settings, _DEMO_ANCHORS)

    async def service_groups(request: Request):
        return _list_response(settings, _DEMO_SERVICE_GROUPS)

    async def custom_live_rooms(request: Request):
        return _list_response(settings, _DEMO_LIVE_ROOMS)

    async def customers(request: Request):
        payload = await _request_payload(request)
        keyword = str(payload.get("keyword", "")).strip()
        rows = _filter_rows(_DEMO_CUSTOMERS, keyword, "nickname")
        return _list_response(settings, rows)

    async def maintenance(request: Request):
        return _list_response(settings, _DEMO_MAINTENANCE)

    async def consoles(request: Request):
        return _list_response(settings, _DEMO_CONSOLES)

    async def live_room_anchors(request: Request):
        if not _demo_enabled(settings):
            return _disabled()
        return success(
            {
                "is_view_button": "1",
                "list": _DEMO_ANCHORS,
            }
        )

    async def live_room_rank(request: Request):
        return _rank_response(
            settings,
            [
                {
                    "rank": 1,
                    "live_name": "DEMO 直播间 A",
                    "total_money": "DEMO-¥9,900",
                }
            ],
        )

    async def order_money_rank(request: Request):
        return _rank_response(
            settings,
            [
                {
                    "rank": 1,
                    "nickname": "DEMO 主播 A",
                    "total_money": "DEMO-¥8,800",
                }
            ],
        )

    async def order_use_money_rank(request: Request):
        return _rank_response(
            settings,
            [
                {
                    "rank": 1,
                    "nickname": "DEMO 主播 B",
                    "total_money": "DEMO-¥6,600",
                }
            ],
        )

    async def order_area(request: Request):
        if not _demo_enabled(settings):
            return _disabled()
        payload = await _request_payload(request)
        area_type = str(payload.get("type", "1"))
        if area_type == "2":
            rows = [
                {"rank": 1, "name": "DEMO-城市-A", "num": 7, "rate": "58.33%"},
                {"rank": 2, "name": "DEMO-城市-B", "num": 5, "rate": "41.67%"},
            ]
        else:
            rows = [
                {"rank": 1, "name": "DEMO-省份-A", "num": 12, "rate": "60.00%"},
                {"rank": 2, "name": "DEMO-省份-B", "num": 8, "rate": "40.00%"},
            ]
        return success({"list": rows})

    async def notices(request: Request):
        if not _demo_enabled(settings):
            return _disabled()
        rows = [
            {
                "id": "DEMO-NOTICE-001",
                "title": "DEMO 测试通知",
                "content": "DEMO 测试环境通知内容",
                "create_time": "2026-09-12 08:00:00",
                "type": 0,
                "type_str": "系统",
                "view_flg": 0,
                "order_no": "",
            }
        ]
        return success(
            {
                "total": len(rows),
                "list": rows,
                "notice_type_list": [
                    {"key": "DEMO-SYSTEM", "value": "系统"},
                ],
            }
        )

    async def notice_change_view(request: Request):
        return _empty_response(settings)

    async def notice_flag(request: Request):
        return _empty_response(settings)

    routes = {
        "/apiv1/console/center": center,
        "/apiv1/console/searchanchorliveroom": live_rooms,
        "/apiv1/console/searchanchor": anchors,
        "/apiv1/console/searchgroup": service_groups,
        "/apiv1/console/searchcustomliveroom": custom_live_rooms,
        "/apiv1/console/searchcustom": customers,
        "/apiv1/console/searchmaintenance": maintenance,
        "/apiv1/console/searchconsole": consoles,
        "/apiv1/console/liveroomanchorlist": live_room_anchors,
        "/apiv1/console/liveroomrank": live_room_rank,
        "/apiv1/console/ordermoneyrank": order_money_rank,
        "/apiv1/console/orderusemoneyrank": order_use_money_rank,
        "/apiv1/console/orderarea": order_area,
        "/apiv1/user/notices/index": notices,
        "/apiv1/user/notices/changeview": notice_change_view,
        "/apiv1/user/user/changenoticeflg": notice_flag,
    }
    for path, handler in routes.items():
        router.add_api_route(path, handler, methods=["POST"])
    return router


def _demo_enabled(settings: Settings) -> bool:
    allowed_environment = settings.app_env.lower() in {"test", "staging"} or (
        settings.environment.lower() in {"test", "staging"}
    )
    return settings.demo_login_enabled and allowed_environment


def _disabled():
    return failure("测试首页兼容接口未启用", status_code=503)


def _list_response(settings: Settings, rows: list[dict[str, Any]]):
    if not _demo_enabled(settings):
        return _disabled()
    return success({"list": rows})


def _rank_response(settings: Settings, rows: list[dict[str, Any]]):
    return _list_response(settings, rows)


def _empty_response(settings: Settings):
    if not _demo_enabled(settings):
        return _disabled()
    return success({})


def _center_info() -> dict[str, int | str]:
    return {
        "today_order_num": 12,
        "yestoday_order_num": 10,
        "current_month_order_num": 86,
        "last_month_order_num": 73,
        "today_order_money": "DEMO-¥1,188",
        "yestoday_order_money": "DEMO-¥990",
        "current_month_order_money": "DEMO-¥8,600",
        "last_month_order_money": "DEMO-¥7,300",
        "today_use_num": 5,
        "yestoday_use_num": 4,
        "current_month_use_num": 41,
        "last_month_use_num": 35,
        "today_use_money": "DEMO-¥500",
        "yestoday_use_money": "DEMO-¥400",
        "current_month_use_money": "DEMO-¥4,100",
        "last_month_use_money": "DEMO-¥3,500",
        "last_month_use_rate": "48",
        "today_refund_num": 1,
        "yestoday_refund_num": 0,
        "current_month_refund_num": 3,
        "last_month_refund_num": 2,
        "today_refund_money": "DEMO-¥99",
        "yestoday_refund_money": "DEMO-¥0",
        "current_month_refund_money": "DEMO-¥297",
        "last_month_refund_money": "DEMO-¥198",
        "current_month_use_rate": "47",
        "total_use_rate": "48",
        "total_order_num": 159,
        "total_order_money": "DEMO-¥15,900",
        "total_use_num": 76,
        "total_use_money": "DEMO-¥7,600",
        "reservation_rate": "0",
        "total_order_reservation_num": 0,
        "total_repeat_order_num": 0,
        "reservation_rate_precise": "0",
        "reservation_precise_order_num": 0,
        "quick_refund_order_num": 0,
    }


def _filter_rows(
    rows: list[dict[str, Any]],
    keyword: str,
    field: str,
) -> list[dict[str, Any]]:
    if not keyword:
        return rows
    return [row for row in rows if keyword.lower() in str(row.get(field, "")).lower()]


async def _request_payload(request: Request) -> Mapping[str, Any]:
    body = await request.body()
    if not body:
        return {}
    content_type = request.headers.get("content-type", "").lower()
    if "application/x-www-form-urlencoded" in content_type:
        parsed = parse_qs(body.decode("utf-8", errors="replace"), keep_blank_values=True)
        return {key: values[-1] for key, values in parsed.items() if values}
    try:
        payload = json.loads(body)
    except (TypeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}
