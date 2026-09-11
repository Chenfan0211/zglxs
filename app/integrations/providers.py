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
    _FAILURE_CODES = {
        "timeout": "mock_timeout",
        "rate_limited": "mock_rate_limited",
        "signature_invalid": "mock_signature_invalid",
        "duplicate": "mock_duplicate",
    }

    def __init__(
        self,
        name: str,
        fail: bool = False,
        outcome: str | None = None,
    ) -> None:
        self._name = name
        self._outcome = outcome or ("failure" if fail else "success")
        self.last_request_summary: dict[str, Any] = {}

    async def send(self, payload: Mapping[str, Any]) -> ProviderResult:
        self.last_request_summary = {
            key: value
            for key, value in payload.items()
            if key in {"event", "operation", "source"}
        }
        code = self._FAILURE_CODES.get(self._outcome, "mock_failure")
        return ProviderResult(
            ok=self._outcome == "success",
            code="mock_ok" if self._outcome == "success" else code,
            request_id=f"mock-{self._name}-001",
        )
