from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class ProviderResult:
    ok: bool
    code: str
    request_id: str


@runtime_checkable
class DouyinLaikeProvider(Protocol):
    async def send(self, payload: Mapping[str, Any]) -> ProviderResult: ...


@runtime_checkable
class SmsProvider(Protocol):
    async def send(self, payload: Mapping[str, Any]) -> ProviderResult: ...


@runtime_checkable
class CloudCallProvider(Protocol):
    async def send(self, payload: Mapping[str, Any]) -> ProviderResult: ...


@runtime_checkable
class WebhookProvider(Protocol):
    async def send(self, payload: Mapping[str, Any]) -> ProviderResult: ...


class MockProvider:
    def __init__(self, name: str, fail: bool = False) -> None:
        self._name = name
        self._fail = fail
        self.last_request_summary: dict[str, Any] = {}

    async def send(self, payload: Mapping[str, Any]) -> ProviderResult:
        self.last_request_summary = {
            key: value
            for key, value in payload.items()
            if key in {"event", "operation", "source"}
        }
        return ProviderResult(
            ok=not self._fail,
            code="mock_failure" if self._fail else "mock_ok",
            request_id=f"mock-{self._name}-001",
        )
