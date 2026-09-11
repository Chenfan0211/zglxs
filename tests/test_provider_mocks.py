from collections.abc import Mapping
from typing import Any

import pytest

from app.integrations.providers import (
    CloudCallProvider,
    DouyinLaikeProvider,
    MockProvider,
    ProviderResult,
    SmsProvider,
    WebhookProvider,
)


@pytest.mark.parametrize(
    "provider_protocol",
    [DouyinLaikeProvider, SmsProvider, CloudCallProvider, WebhookProvider],
)
@pytest.mark.asyncio
async def test_mock_provider_returns_deterministic_result(provider_protocol):
    provider = MockProvider("sms")
    assert isinstance(provider, provider_protocol)

    result = await provider.send({"event": "DEMO_order_created"})

    assert result == ProviderResult(
        ok=True,
        code="mock_ok",
        request_id="mock-sms-001",
    )


@pytest.mark.asyncio
async def test_mock_provider_can_simulate_failure():
    result = await MockProvider("webhook", fail=True).send({"event": "DEMO"})

    assert result == ProviderResult(
        ok=False,
        code="mock_failure",
        request_id="mock-webhook-001",
    )


@pytest.mark.asyncio
async def test_mock_provider_does_not_retain_sensitive_payload_fields():
    provider = MockProvider("sms")
    payload: Mapping[str, Any] = {
        "event": "DEMO",
        "phone": "13800000000",
        "token": "secret",
    }

    await provider.send(payload)

    assert provider.last_request_summary == {"event": "DEMO"}
