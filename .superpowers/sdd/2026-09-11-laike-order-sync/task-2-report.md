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

## 审查修复记录

审查未通过后，按 TDD 先新增回归测试，再修改实现。

### RED

新增测试覆盖：

- 入队失败后 event 保持可重试状态，下一次重复 webhook 可再次入队；
- 两页 reconcile 在第二页 fetch 失败时保留原游标；
- `has_more=True` 时拒绝缺失或未变化的 next cursor；
- Repository 唯一键冲突通过 nested transaction 回读已有事件；
- SQLite 执行 Alembic upgrade/downgrade 并检查四张同步表；
- 订单失败摘要写入 sync run 且不包含 payload 值。

初次运行新增回归测试得到 `6 failed, 6 passed`，失败分别对应原有的入队状态窗口、逐页推进游标、分页校验缺失、唯一键冲突未处理和迁移文件缺失。迁移测试最初还暴露仓库空的 `alembic/__init__.py` 遮蔽外部 Alembic 包的问题，随后删除该空包标记并改为真实 SQLite migration 测试。

### GREEN

实现修复：

- webhook 事件只在入队成功后标记 `queued`；入队异常返回失败，事件保留 `received`，后续重复到达会重试；
- reconcile 暂存最终游标，只有所有分页 fetch 和所有订单处理成功后统一推进；
- event/order/cursor 的插入使用 `Session.begin_nested()`，捕获 `IntegrityError` 后重新读取唯一键对应记录；
- `has_more=True` 时要求 next cursor 非空且不同于当前 cursor；
- 订单失败记录 `exception_type`、失败数量和经过 hash 的 order reference，不写原始 payload 或敏感值；
- `alembic/env.py` 导入 `app.db.models` 并绑定 `Base.metadata`；
- 新增 `alembic/versions/0002_laike_sync.py`，可升级/回滚四张同步表；
- 删除空的 `alembic/__init__.py`，避免遮蔽第三方 Alembic 包；补充 `alembic.ini` 的 `path_separator = os`。

验证输出：

```text
python -m pytest tests/test_laike_service.py tests/test_laike_migrations.py -q
.............                                                            [100%]
13 passed in 0.56s

python -m pytest -q
........................................................................ [ 97%]
..                                                                       [100%]
74 passed in 1.03s
```

`git diff --check` 通过。

### 审查后自审

- [x] 入队失败不会把 event 永久视为已处理。
- [x] 入队成功后才写入 `queued` 和 `processed_at`。
- [x] 多页同步仅在整次同步成功后推进 cursor。
- [x] fetch 失败、订单失败、非法分页游标均不推进 cursor。
- [x] 唯一键并发冲突在 Repository 层回读，不计为业务失败。
- [x] 订单失败可定位但不记录原始 payload。
- [x] Alembic upgrade/downgrade 已在 SQLite 上运行验证。
- [x] 未修改 Task 1 契约/normalizer，未解密 PHP，未使用凭据或 HAR。

### 审查后疑虑

真实生产环境下，多个 worker 同时处理同一 `received` 事件时仍应由队列消费者以 event ID 做幂等；本次 brief 未提供队列 claim/lease 契约，因此没有新增猜测字段或锁协议。Repository 已覆盖唯一键竞态的数据库层幂等。

## 复审 Important 修复报告

### TDD RED

针对本轮四项复审意见，先新增回归测试：

- 两个独立 `LaikeSyncService` 共享 SQLite session factory 处理同一 webhook，第二个请求不得调用 enqueuer；
- `A -> B -> A` 的历史游标环路必须停止，并且只发生两次 fetch；
- 最终页 `has_more=False`、`next_cursor=None` 时保留已有旧游标；
- 使用默认 `expire_on_commit=True` 的 session factory 时，enqueue 仍使用事务内复制的普通值。

运行：

```text
python -m pytest tests/test_laike_service.py -q
...FF....FF....                                                          [100%]
4 failed, 11 passed
```

失败准确暴露了四个问题：第二请求重复 enqueue、commit 后 ORM 属性访问失败、最终页清空旧游标、历史游标环路继续 fetch。

### TDD GREEN

- `LaikeRepository.claim_webhook_event` 使用 `UPDATE ... WHERE event_id=? AND status='received'` 的条件更新实现原子 claim，并新增 `processing -> received` 释放和 `processing -> queued` 完成状态边界。只有 claim 成功者调用 enqueuer，queued/processing 请求返回幂等成功。
- webhook 在 UoW 内先完成 insert/claim，并复制 `event_id` 与 `payload_json`；离开 UoW 后不再读取 ORM 对象。enqueue 失败会释放为 `received`，因此可重试。
- reconcile 维护本次运行的 `seen_cursors`，next cursor 命中历史集合时以安全摘要 `pagination cursor cycle` 失败退出。
- 最终页无 `next_cursor` 时保留当前 cursor；仅当最终 cursor 非空且相对初始值变化、并且所有页面和订单均成功时推进。

### 验证

```text
python -m pytest tests/test_laike_service.py -q
...............                                                          [100%]
15 passed in 0.40s

python -m pytest -q
........................................................................ [ 92%]
......                                                                   [100%]
78 passed in 1.12s
```

`git diff --check` 通过。

### 本轮自审

- [x] 同一事件只有原子 claim 成功者 enqueue。
- [x] queued 或 processing 事件不会重复 enqueue。
- [x] enqueue 失败回到 received，可由下一次 webhook 重试。
- [x] commit 后不访问已过期 ORM 属性。
- [x] 历史 cursor 环路会失败并停止继续 fetch。
- [x] 无新 checkpoint 不清空旧 cursor。
- [x] 未修改 Task 1 文件，未解密 PHP，未使用凭据或 HAR。

### 本轮边界

原子 claim 防止接收端重复 enqueue；真实 Celery 任务消费者仍需在后续 Task 3 以 event ID 实现消费幂等。本轮未引入锁表、猜测字段或额外业务协议。
