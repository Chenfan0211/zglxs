# Task 3 报告：Webhook 接入、外部客户端边界和 Celery 任务

## 状态

已完成，已通过验证。

## TDD RED

先新增：

- `tests/test_laike_webhook.py`
- `tests/test_laike_tasks.py`

首次运行焦点测试：

```text
python -m pytest tests/test_laike_webhook.py tests/test_laike_tasks.py -q
```

结果：

```text
ERROR collecting tests/test_laike_tasks.py
ImportError: cannot import name 'laike_tasks' from 'app.worker'
```

失败原因是 Task 3 的 Celery 任务模块尚不存在，符合目标接口缺失的 RED。

## TDD GREEN

实现最小边界：

- `LaikeClient` 协议定义 `fetch_orders(...)` 和 `verify_webhook(...)`。
- `HmacLaikeClient` 使用 HMAC-SHA256 和 `hmac.compare_digest`，支持常见签名头及 `sha256=` 前缀。
- `POST /internal/laike/webhook` 使用 loopback 保护，默认关闭时返回 503 失败 envelope。
- secret 缺失返回 503；签名缺失或错误、空体、非法 JSON、非对象 JSON 返回稳定 400 失败 envelope。
- 合法请求先完成签名校验，再调用 `LaikeSyncService.receive_webhook`；原始事件保存和 Celery 入队仍由现有 service 状态机负责。
- FastAPI 的 `app.state` 暴露 client、session factory、enqueuer 和 service factory，测试及 worker 不连接真实 Redis、MySQL 或 provider。
- 新增 `process_laike_webhook`、`reconcile_laike_account`、`retry_failed_laike_events`。
- Webhook 消费通过条件状态转移 `queued/failed -> consuming` 防止并发重复消费，成功后标记 `processed`，失败进入 `failed`，超过配置重试次数进入 `dead_letter`。
- 任务失败使用指数退避 `1, 2, 4...`，`retry_failed_laike_events` 只扫描 `failed` 状态。
- `app.worker.tasks` 保留 `health_task`，并 re-export 三个来客任务；未向 `MigrationRegistry` 加入任何未知 legacy action。

焦点 GREEN：

```text
python -m pytest tests/test_laike_webhook.py tests/test_laike_tasks.py -q
....................                                                     [100%]
20 passed in 1.03s
```

## 最终验证

完整测试：

```text
python -m pytest -q
........................................................................ [ 67%]
..................................                                       [100%]
106 passed in 1.59s
```

编译检查：

```text
python -m compileall -q app alembic tools
```

通过，无输出。

差异格式检查：

```text
git diff --check
```

通过；Git 仅提示 Windows 工作区的 LF/CRLF 换行转换，不是代码错误。

## 文件清单

- `app/laike/client.py`
- `app/laike/webhook.py`
- `app/worker/laike_tasks.py`
- `app/worker/tasks.py`
- `app/main.py`
- `tests/test_laike_webhook.py`
- `tests/test_laike_tasks.py`
- `.superpowers/sdd/2026-09-11-laike-order-sync/task-3-report.md`

## 自审

- [x] Webhook 默认关闭，关闭时不读 body、不调用 service、不落事件或订单。
- [x] secret 缺失、签名缺失/错误、空体和非法 JSON 均不会进入 service。
- [x] HMAC 校验使用常量时间比较。
- [x] HTTP 路由不执行订单业务处理，只调用已有 `LaikeSyncService.receive_webhook`。
- [x] Webhook 入队发生在事件持久化和 claim 之后，沿用 Task 2 的 claim token 状态机。
- [x] Celery 任务通过 service factory、session factory 和 client 注入测试。
- [x] 消费任务按 event ID 和状态幂等，重复处理已完成事件不会重复 upsert 订单。
- [x] 失败任务按 max retries 和指数退避处理，超过上限进入 dead letter 状态。
- [x] failed 扫描不会重新投递 queued、processed、consuming 或 dead_letter 事件。
- [x] reconcile 开关关闭时不调用 provider client；Webhook 开关关闭时消费和失败重试任务均 no-op。
- [x] 保留 Task 2 的 claim token、迁移、游标修复，未修改 `service.py`、Repository 或迁移文件。
- [x] 未解密 PHP，未写入真实凭据或 HAR，未增加 `migrated_routes`。

## 疑虑与边界

- Task 2 当前没有公开的单事件业务处理方法。为严格限制改动文件范围，消费任务优先支持注入的 `service.process_webhook`；现有 `LaikeSyncService` 则复用其页面处理原语 `_process_page`，订单 upsert 仍由 service 完成。后续若开放正式 public API，可将该兼容分支替换为公开方法。
- `HmacLaikeClient.fetch_orders` 目前明确抛出“未配置客户端”，没有猜测来客 provider 协议，也不会因测试或默认配置发起外部网络请求。真实 provider 适配需后续基于确认过的官方契约接入。
- Celery 使用现有 `create_celery_app` 配置壳；本任务验证任务注册、重试和注入边界，不启动真实 Redis worker。

## 审查修复追加（2026-09-12）

### 修复内容

- Worker 消费 claim 复用 `LaikeWebhookEvent.claim_token` 作为消费 fencing token；`queued`、`failed`、`retry_scheduled` 和过期/无时间的 `consuming` claim 都会生成新 token，并原子写入 `consuming`、`processed_at` 和 token。
- 完成、失败和 dead letter 都要求 `event_id + status=consuming + claim_token` 条件匹配；旧 worker 丢失租约后不能覆盖新 worker。
- 消费租约按 `Settings.laike_webhook_claim_timeout_seconds` 判定；process claim 和 retry scanner 都能恢复过期/无时间的 `consuming`，未过期租约不会重复消费。
- retry scanner 使用条件更新 `failed/过期 consuming -> retry_scheduled`，只对成功更新的事件调用 `delay`；`delay` 抛错时仅在事件仍为 `retry_scheduled` 时恢复为 `failed`，避免覆盖已接管的 worker。
- process task 接受 `retry_scheduled`，并为失败重试覆盖第二次退避 `2` 秒和达到上限后的 `dead_letter`。
- Celery app 在未显式注入 URL 时读取 `Settings.from_env().redis_url`；配置 Redis 时 broker/backend 均使用该 URL，无 Redis 时继续使用 memory。
- 多个签名 header 和 event ID 候选明确保留为测试/兼容占位，不代表真实来客协议；真实 HAR 或官方契约确认前不登记 `migrated_routes`，也不记录敏感 payload。

### TDD RED

先追加 worker、scanner 和 Celery 配置回归测试，再运行 focused：

```text
python -m pytest tests/test_laike_tasks.py tests/test_business_foundation.py -q
```

结果：

```text
9 failed, 20 passed
```

失败点覆盖消费 token 缺失、`consuming` 租约未恢复、旧 claim 未 fencing、scanner 未进入 `retry_scheduled`、delay 异常未恢复、`retry_scheduled` 未消费和 Redis URL 未从 Settings 读取。

### TDD GREEN

实现最小修复后运行同一 focused 测试：

```text
python -m pytest tests/test_laike_tasks.py tests/test_business_foundation.py -q
```

结果：

```text
30 passed in 1.11s
```

覆盖了第二次退避、max retries dead letter、过期/无时间 consuming 恢复、未过期 consuming 不重复消费、旧 worker fencing、重复 scanner 和双线程并发 scanner。

### 最终验证

完整测试：

```text
python -m pytest -q
```

结果：

```text
118 passed in 1.84s
```

编译检查：

```text
python -m compileall -q app alembic tools
```

通过，无输出。

差异格式检查：

```text
git diff --check
```

通过；仅有 Windows 工作区的 LF/CRLF 转换提示，无 whitespace 错误。

## 复审剩余问题修复（2026-09-12）

### 修复内容

- `LaikeWebhookEvent` 新增持久化 `retry_count`、`next_retry_at` 和 `retry_scheduled_at`，并新增 `0004_laike_retry_state` migration。
- 消费失败在当前 claim token 下原子写入下一次重试次数和到期时间；scanner 只投递到期的 `failed`，不会在 Celery countdown 期间重复派发。
- process task 以数据库中的 `retry_count` 为业务重试权威，第二次退避仍为 `2` 秒，达到 `max_retries` 时进入 `dead_letter`；Celery `request.retries` 不再决定事件是否 dead-letter。
- scanner 原子建立 `retry_scheduled_at` 投递租约；投递前崩溃后，后续 scanner 可回收过期租约。`delay` 异常只在同一租约仍有效时恢复 `failed`，保留原有计数和到期时间。
- 保留过期 `consuming` claim 的恢复和 claim token fencing；旧 token 不能覆盖新 worker 的状态。
- `create_app(settings=...)` 默认创建并保存与 resolved settings 相同 broker 的 Celery app；支持注入 `laike_task_app` 或 `laike_enqueuer_factory`，默认 enqueuer 使用该 app 的 `send_task`，app factory 不连接 Redis。

### TDD RED

先追加持久化重试、scanner 租约、迁移和 Celery app 绑定测试，再运行 focused：

```text
python -m pytest tests/test_laike_tasks.py tests/test_laike_webhook.py tests/test_laike_migrations.py -q
```

结果：

```text
9 failed, 31 passed
```

失败原因分别是事件模型缺少 retry 字段、迁移 `0004` 不存在，以及 `create_app` 尚未暴露/绑定 `laike_task_app`；没有提前修改生产实现。

### TDD GREEN

实现后运行同一 focused：

```text
python -m pytest tests/test_laike_tasks.py tests/test_laike_webhook.py tests/test_laike_migrations.py -q
```

结果：

```text
40 passed in 1.66s
```

覆盖失败 countdown 期间不重复派发、持久化第二次退避和最大次数、过期 `retry_scheduled` 回收、投递异常恢复、并发 scanner、旧 token fencing、disabled 无副作用，以及 settings/custom task app 的 broker 一致性。

### 最终验证

完整测试：

```text
python -m pytest -q
```

结果：

```text
125 passed in 2.01s
```

编译检查：

```text
python -m compileall -q app alembic tools
```

通过，无输出。

差异格式检查：

```text
git diff --check
```

通过；仅有 Windows 工作区的 LF/CRLF 转换提示，无 whitespace 错误。

HMAC signature header 和 event ID 候选仍仅作为兼容占位，报告不将其表述为真实来客协议；未解密 PHP，未写入凭据或 HAR，未登记新的 `migrated_routes`。
