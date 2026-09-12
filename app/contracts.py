from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class ContractCase:
    """A redacted legacy request captured for PHP/Python replay."""

    request_id: str
    method: str
    controller: str
    action: str
    query: dict[str, Any]
    path: dict[str, str]
    body: dict[str, Any] | None
    headers: dict[str, str]
    cookies: dict[str, str]

    def to_record(self) -> dict[str, Any]:
        values = asdict(self)
        request = {
            key: values.pop(key)
            for key in ("query", "path", "body", "headers", "cookies")
        }
        return {**values, "request": request}
