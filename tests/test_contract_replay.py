from __future__ import annotations

import json

import httpx

from tools.contract_replay import replay_cases


async def test_replay_cases_preserves_legacy_request_and_redacts_response(tmp_path):
    request_path = tmp_path / "cases.jsonl"
    output_path = tmp_path / "recordings.jsonl"
    request_path.write_text(
        json.dumps(
            {
                "request_id": "demo-staff-index",
                "method": "POST",
                "controller": "user",
                "action": "staff/index",
                "request": {
                    "query": {"page": 1},
                    "path": {},
                    "body": {"status": "active"},
                    "headers": {"X-Demo": "1"},
                    "cookies": {"session": "DEMO-SESSION"},
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["url"] = str(request.url)
        seen["body"] = request.content
        seen["cookie"] = request.headers.get("cookie")
        return httpx.Response(
            200,
            headers={"content-type": "application/json", "set-cookie": "token=secret"},
            json={"code": 1, "msg": "success", "data": {"token": "secret"}},
        )

    await replay_cases(
        "http://php.test",
        request_path,
        output_path,
        transport=httpx.MockTransport(handler),
    )

    assert seen == {
        "method": "POST",
        "url": "http://php.test/apiv1/user/staff/index?page=1",
        "body": b'{"status":"active"}',
        "cookie": "session=DEMO-SESSION",
    }
    recording = json.loads(output_path.read_text(encoding="utf-8"))
    assert recording == {
        "request_id": "demo-staff-index",
        "method": "POST",
        "controller": "user",
        "action": "staff/index",
        "status_code": 200,
        "body": {"code": 1, "msg": "success", "data": {"token": "[REDACTED]"}},
        "headers": {
            "content-length": "52",
            "content-type": "application/json",
            "set-cookie": "[REDACTED]",
        },
        "database": {},
    }


async def test_replay_cases_sends_legacy_form_body_when_content_type_requires_it(
    tmp_path,
):
    request_path = tmp_path / "cases.jsonl"
    output_path = tmp_path / "recordings.jsonl"
    request_path.write_text(
        json.dumps(
            {
                "request_id": "staff-page-1",
                "method": "POST",
                "controller": "user",
                "action": "staff/index",
                "request": {
                    "query": {},
                    "path": {},
                    "body": {"page": 1, "page_size": 10},
                    "headers": {
                        "content-type": "application/x-www-form-urlencoded"
                    },
                    "cookies": {},
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.content == b"page=1&page_size=10"
        return httpx.Response(200, json={"code": 1, "msg": "success", "data": {}})

    await replay_cases(
        "http://php.test",
        request_path,
        output_path,
        transport=httpx.MockTransport(handler),
    )

    recording = json.loads(output_path.read_text(encoding="utf-8"))
    assert recording["method"] == "POST"
    assert recording["controller"] == "user"
    assert recording["action"] == "staff/index"
