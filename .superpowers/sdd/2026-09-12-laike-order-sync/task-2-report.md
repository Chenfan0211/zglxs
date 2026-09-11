# Task 2 Report

## Status

完成来客协议层、注入式 HTTP 客户端、Webhook HMAC 验证器和显式字段归一化，同时保持上一轮调用兼容。

## Changed Files

- `app/laike/__init__.py`
- `app/laike/contracts.py`
- `app/laike/client.py`
- `app/laike/normalizer.py`
- `app/laike/webhook.py`
- `tests/test_laike_protocols.py`

兼容保留：

- `WebhookVerification(verified=...)` 和 `.verified`
- `LaikePage(items=..., has_more=...)` 和 `.has_more`
- `NormalizedOrder.created_at`、`.payload_json`
- `normalize_order(payload)`
- 现有 webhook router 行为

## RED/GREEN Evidence

### RED

先新增 `tests/test_laike_protocols.py`，运行：

```text
python -m pytest tests/test_laike_protocols.py -q
```

结果为收集失败，原因是当前实现缺少需求接口：

```text
ImportError: cannot import name 'HttpLaikeClient' from 'app.laike.client'
```

### GREEN

实现最小协议层后，运行：

```text
python -m pytest tests/test_laike_protocols.py -q
```

结果：

```text
24 passed
```

## Verification

相关旧回归：

```text
python -m pytest tests/test_laike_contracts.py tests/test_laike_webhook.py tests/test_laike_service.py -q
50 passed
```

全套测试：

```text
python -m pytest -q
160 passed
```

差异检查：

```text
git diff --check
```

通过；输出仅包含 Git 关于 LF/CRLF 的提示，没有 whitespace error。

## Commit

```text
9675f4762083ddc69eae9d20fa4f89acd58d0ede
feat: add laike protocol and normalization layer
```

## Concerns

- 未硬编码真实来客 endpoint、Webhook 事件头、签名约定或业务字段映射；这些仍需外部 HAR、官方文档或测试凭据确认。
- `tests/test_laike_contracts.py` 的 max retries 修改和 `docs/superpowers/plans/2026-09-12-laike-order-sync.md` 是任务开始前已存在的工作区变更，未纳入本 Task 2 功能提交。

## Review Fixes

针对 P1-1、P1-2、P1-3、P2-1、P2-2 追加了回归测试并完成修复：

- `LaikeSyncService` 支持注入 `OrderNormalizer` 或兼容 callable；省略 normalizer 时保留旧测试 double 行为，生产 `create_app` 显式传入 `None`，未确认 mapping 时不写订单。
- service 优先使用 `WebhookVerification.event_id`；新协议对象没有 event_id 时只使用 raw body SHA-256，旧 `verified=...` 构造形态才保留旧兼容 fallback。
- `main.py` 显式构造配置化 `WebhookVerifier`，默认 HMAC client 只使用 Settings 指定的签名头和事件头；直接构造的旧 `HmacLaikeClient(secret)` 仍保留兼容行为。
- legacy `normalize_order(payload).model_dump()` 恢复 `payload_json`/`created_at` 形状，显式 `OrderNormalizer` 保持新 shape。
- 默认 HMAC client 的订单请求为 async；同步 verification 结果实现可直接 await，service 继续通过 `_maybe_await` 接受同步测试 double。

### Review RED

新增回归测试首次运行：

```text
python -m pytest tests/test_laike_protocols.py -q
7 failed, 25 passed
```

失败原因分别覆盖：legacy dump 污染、默认 HMAC 不可 await、main 未使用配置签名头、main/service 不支持 normalizer 注入，以及 service 丢失配置化 event_id。随后新增 HMAC `fetch_orders` awaitability回归，修复前该单测也按预期失败。

### Review GREEN

```text
python -m pytest tests/test_laike_protocols.py -q
34 passed

python -m pytest tests/test_laike_protocols.py tests/test_laike_webhook.py tests/test_laike_service.py tests/test_laike_tasks.py -q
97 passed

python -m compileall -q app/laike app/main.py tests/test_laike_protocols.py
compileall passed

git diff --check
通过；仅有 LF/CRLF 提示。
```

### Review Fix Commit

```text
f7a5421
fix: address laike protocol review findings
```

## Final Concern

最终全套测试仍有一个任务外的既有基线不一致：

```text
tests/test_laike_contracts.py::test_laike_settings_are_disabled_and_have_safe_defaults
assert settings.laike_max_retries == 3
实际 Settings.laike_max_retries == 5
```

其余来客相关测试通过；未修改 Task 5 文件、加密 PHP 或该任务外的 settings/test 文件。

## Review Fix Round 2

限定 finding：`HmacLaikeClient.verify_webhook` 必须是真正的 async 方法并严格满足 `LaikeClient` Protocol。

### RED

先调整 `tests/test_laike_protocols.py` 与受影响的旧 HMAC 测试调用为真实 `await`，并增加：

- `inspect.iscoroutinefunction(client.verify_webhook)`
- `inspect.iscoroutinefunction(app.state.laike_client.verify_webhook)`
- 结果对象不再提供 `__await__`

运行：

```text
python -m pytest tests/test_laike_protocols.py tests/test_laike_webhook.py -q
```

结果：

```text
2 failed, 46 passed
```

失败均为 `inspect.iscoroutinefunction(...) == False`，确认失败来自 HMAC 方法仍是同步函数。

### GREEN

- 将 `HmacLaikeClient.verify_webhook` 改为真正的 `async def`。
- 删除 `WebhookVerification.__await__` 伪 await 实现。
- 更新旧同步直接调用测试为异步 await 调用。
- 保留 service/router 的 `_maybe_await`，继续兼容同步测试 double。

最终验证：

```text
python -m pytest tests/test_laike_protocols.py -q
34 passed

python -m pytest -q
177 passed

python -m compileall -q app/laike app/main.py tests/test_laike_protocols.py
compileall passed

git diff --check
通过；仅有 LF/CRLF 提示。
```

未修改 Task 5 文件、加密 PHP 或其他无关生产文件。
