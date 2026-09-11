# Task 2 报告：同步表、Repository 和事务内幂等服务

## 状态

已完成实现并通过验证，已提交 git commit。

## TDD RED

先新增 `tests/test_laike_service.py`，覆盖：

- webhook 事件持久化；
- 重复 event ID 幂等；
- 重复 provider order ID upsert；
- 单条订单失败隔离；
- fetch 失败时游标不推进；
- 成功处理后游标推进。

首次运行命令：

```text
python -m pytest tests/test_laike_service.py -q
```

预期 RED 输出：

```text
ModuleNotFoundError: No module named 'app.db.models.laike'
1 error during collection
```

失败原因是 Task 2 模型、Repository 和 Service 尚未实现，测试本身已进入收集阶段并因缺少目标模块失败。

## TDD GREEN

按最小范围实现四张 ORM 表、Repository 和服务：

- `laike_webhook_event`：唯一 `event_id`，保留原始 `payload_json` 和 headers；
- `laike_order`：唯一 `provider_order_id`，保留原始订单载荷和标准化 `status`/`created_at`；
- `laike_sync_cursor`：按 `account_id` 唯一保存游标；
- `laike_sync_run`：记录 reconcile 运行状态、时间、计数和错误信息。

服务行为：

- webhook 先调用注入 client 的验证方法，验证成功后在事务内写入事件；
- 已存在的 event ID 直接返回成功，不重复落库或入队；
- reconcile 每条订单独立 UnitOfWork，标准化或 upsert 失败不影响其他订单；
- fetch 异常或页面存在失败订单时不推进游标；
- 整页 fetch 和订单处理成功后才推进游标；
- 支持同步或异步形式的验证、拉页和入队 callable。

修正测试中一个不符合 Task 1 契约的坏样本后，focused GREEN 输出：

```text
python -m pytest tests/test_laike_service.py -q
......                                                                   [100%]
6 passed in 0.36s
```

## 最终测试输出

完整测试：

```text
python -m pytest -q
...................................................................      [100%]
67 passed in 0.84s
```

额外执行 `git diff --check`，无代码空白错误。

## 文件

- 新增 `app/db/models/laike.py`
- 修改 `app/db/models/__init__.py`
- 新增 `app/laike/repositories.py`
- 新增 `app/laike/service.py`
- 新增 `tests/test_laike_service.py`
- 新增本报告

Task 1 文件 `app/laike/contracts.py`、`app/laike/normalizer.py` 未修改；未解密 PHP，未写入真实凭据或 HAR。

## 自审

- [x] 四张表名与 brief 一致。
- [x] event ID 和 provider order ID 具有唯一约束。
- [x] 订单只保存已确认的 provider_order_id、payload_json、status、created_at。
- [x] 单条失败隔离。
- [x] fetch/处理不完整时游标不推进。
- [x] 成功页面推进游标。
- [x] 重复事件和重复订单具备幂等行为。
- [x] 使用通用 SQLAlchemy 类型，可用于 SQLite 测试和 MySQL。
- [x] 变更未超出指定代码/测试范围。

## 疑虑与边界

Task 1 未提供具体 `LaikeClient` 协议，因此服务约定优先调用 `fetch_orders`，缺失时回退到 `list_orders`；验证优先调用 `verify_webhook`。这些适配没有猜测来客字段。事件缺少显式 ID 时使用 header、payload 中已确认的 `event_id`，最后使用原始 body 的 SHA-256 作为稳定幂等键。真实契约接入时，如方法名或事件 ID 传递方式不同，只需调整客户端适配层。
