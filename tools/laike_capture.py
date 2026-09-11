import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any


REDACTED = "[REDACTED]"
SENSITIVE_KEY_PARTS = (
    "phone",
    "mobile",
    "address",
    "token",
    "secret",
    "signature",
    "authorization",
    "cookie",
)


def sanitize_payload(value: Any) -> Any:
    if isinstance(value, Mapping):
        sanitized = {}
        for key, item in value.items():
            if any(part in str(key).lower() for part in SENSITIVE_KEY_PARTS):
                sanitized[key] = REDACTED
            else:
                sanitized[key] = sanitize_payload(item)
        return sanitized
    if isinstance(value, list):
        return [sanitize_payload(item) for item in value]
    return value


def append_jsonl(path: str | Path, record: dict[str, Any]) -> None:
    if not isinstance(record, dict):
        raise TypeError("record must be a JSON object")

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as output:
        json.dump(sanitize_payload(record), output, ensure_ascii=False)
        output.write("\n")
