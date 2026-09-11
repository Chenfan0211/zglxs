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
