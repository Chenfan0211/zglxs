from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import httpx

from tools.laike_capture import append_jsonl, sanitize_payload


async def replay_cases(
    base_url: str,
    input_path: str | Path,
    output_path: str | Path,
    *,
    timeout: float = 10.0,
    transport: Any = None,
) -> None:
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("", encoding="utf-8")

    with Path(input_path).open("r", encoding="utf-8") as source:
        cases = [json.loads(line) for line in source if line.strip()]

    async with httpx.AsyncClient(
        base_url=base_url.rstrip("/"),
        timeout=timeout,
        transport=transport,
    ) as client:
        for case in cases:
            request = case.get("request") or {}
            path = f"/apiv1/{case['controller'].strip('/')}/{case['action'].strip('/')}"
            headers = dict(request.get("headers") or {})
            cookies = request.get("cookies") or {}
            if cookies and not any(key.lower() == "cookie" for key in headers):
                headers["Cookie"] = "; ".join(
                    f"{key}={value}" for key, value in cookies.items()
                )
            request_kwargs: dict[str, Any] = {
                "headers": headers,
                "params": request.get("query") or {},
            }
            if request.get("body") is not None:
                content_type = next(
                    (
                        str(value).lower()
                        for key, value in headers.items()
                        if key.lower() == "content-type"
                    ),
                    "",
                )
                if "application/x-www-form-urlencoded" in content_type:
                    request_kwargs["content"] = urlencode(
                        request["body"],
                        doseq=True,
                    ).encode("utf-8")
                else:
                    request_kwargs["json"] = request["body"]
            response = await client.request(case["method"], path, **request_kwargs)
            append_jsonl(
                destination,
                {
                    "request_id": case["request_id"],
                    "method": case["method"].upper(),
                    "controller": case["controller"],
                    "action": case["action"],
                    "status_code": response.status_code,
                    "body": _response_body(response),
                    "headers": sanitize_payload(dict(response.headers.items())),
                    "database": {},
                },
            )


def _response_body(response: httpx.Response) -> Any:
    content_type = response.headers.get("content-type", "").lower()
    if "json" in content_type:
        try:
            return response.json()
        except ValueError:
            pass
    return response.text


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Replay redacted legacy requests and record sanitized responses"
    )
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args()
    import asyncio

    asyncio.run(
        replay_cases(
            args.base_url,
            args.input,
            args.output,
            timeout=args.timeout,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
