# Task 1 完成报告：来客配置、协议对象和字段安全标准化

## 状态

已完成。目标实现和测试文件在本次操作开始时已存在于工作区但尚未提交；本次对照任务简报完成审阅、验证，并纳入本任务提交。

## 改动

- `app/core/settings.py`
  - 增加 `laike_sync_mode`，允许值为 `observe`、`reconcile`、`write`，默认 `observe`。
  - 增加 webhook、reconcile、write 三个开关，默认均为 `False`。
  - 增加 webhook secret、app id、app secret、access token 配置，默认均为 `None`。
  - 增加 `laike_max_retries`，默认 `3`，且不允许小于 `0`。
  - 对来客凭据和已有连接配置统一处理空白字符串，空值标准化为 `None`。
- `app/laike/contracts.py`
  - 增加 `LaikePage`、`WebhookVerification`、`NormalizedOrder`、`SyncResult` 四个 Pydantic 协议对象。
  - 协议对象禁止未声明字段。
  - `NormalizedOrder.log_metadata()` 只返回订单号和是否存在 payload，不输出原始 payload 或敏感字段。
- `app/laike/normalizer.py`
  - 增加 `normalize_order(payload)`。
  - 仅读取显式稳定键 `order_id`、`status`、`created_at`。
  - 完整复制输入到 `payload_json`，未知字段不丢弃、不提升为业务字段。
  - 缺少 `order_id` 时保持 `None`，不从 `id` 等未知字段猜测。
- `app/laike/__init__.py`
  - 导出来客协议对象和 `normalize_order`。
- `tests/test_laike_contracts.py`
  - 覆盖安全默认值、协议对象稳定形状、稳定键标准化、缺失 ID 和日志元数据脱敏。

## TDD RED/GREEN 证据

### RED

在仓库外创建基于 `HEAD`（`4d0e834`）的临时工作树，仅复制任务测试后运行：

```text
python -m pytest tests/test_laike_contracts.py -q
```

结果：

```text
ERROR collecting tests/test_laike_contracts.py
ModuleNotFoundError: No module named 'app.laike'
1 error in 0.24s
```

失败原因是目标模块尚不存在，符合预期的接口缺失 RED。

### GREEN

工作区实现完成后运行：

```text
python -m pytest tests/test_laike_contracts.py -q
.....                                                                    [100%]
5 passed in 0.12s
```

## 测试命令和输出

```text
python -m pytest tests/test_laike_contracts.py -q
5 passed in 0.12s

python -m pytest tests/test_business_foundation.py -q
10 passed in 0.68s

python -m pytest -q
53 passed in 0.94s
```

另外执行 `git diff --check`，未发现差异格式错误。

## 文件清单

- `app/core/settings.py`
- `app/laike/__init__.py`
- `app/laike/contracts.py`
- `app/laike/normalizer.py`
- `tests/test_laike_contracts.py`
- `.superpowers/sdd/2026-09-11-laike-order-sync/task-1-report.md`

## 自审

- 所有来客功能开关默认关闭，默认同步模式为只观察。
- 未读取或解密任何加密 PHP。
- 未加入真实凭据或真实 HAR。
- 未把未知来客字段映射为猜测的业务字段；完整 payload 保存在 `payload_json`。
- 日志元数据不包含原始请求体、token、secret、手机号等敏感值。
- 未修改其它任务文件。

## 疑虑

- 当前任务只定义基础协议和标准化边界，未实现 webhook、数据库持久化、重试任务或真实来客 API 调用；这些属于后续任务范围。
- RED 运行基于 `HEAD` 临时工作树，因为本任务测试和目标文件在本次操作开始时已作为未提交工作区草稿存在；工作区首次直接运行焦点测试已经是 GREEN。
