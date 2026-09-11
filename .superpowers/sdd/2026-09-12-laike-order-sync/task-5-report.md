# Task 5 Report

## Status

已完成契约回放比较、部署检查和文档声明；未修改来客业务服务、持久化或 Worker
运行逻辑，`contracts/api-manifest.json` 的 `migrated_routes` 保持为空。

## Changed Files

- `tools/contract_tools.py`
- `tools/compare_contracts.py`
- `tests/test_laike_contract_comparison.py`
- `README.md`
- `docs/migration-status.md`
- `contracts/README.md`
- `deploy/systemd/douyin-order-worker.service`
- `deploy/systemd/douyin-order-scheduler.service`
- `deploy/scripts/check-deploy.sh`

## RED/GREEN Evidence

### RED

先新建 `tests/test_laike_contract_comparison.py`，运行：

```text
python -m pytest tests/test_laike_contract_comparison.py -q
```

结果为 `4 failed, 3 passed`。失败原因符合预期：

- headers 未比较，缺少 `response.headers` mismatch。
- CLI 未因 header 差异返回退出码 `1`。
- 部署脚本没有 disabled/default webhook POST 安全探测。
- 文档没有外部前置条件、安全默认值和 manifest 门槛声明。

### GREEN

实现最小变更后，运行同一 focused test：

```text
python -m pytest tests/test_laike_contract_comparison.py -q
```

结果：

```text
7 passed
```

## Verification

Focused test：

```text
python -m pytest tests/test_laike_contract_comparison.py -q
7 passed
```

Full test suite：

```text
python -m pytest -q
167 passed, 8 failed
```

8 个失败均来自本任务开始后出现在工作区的既有来客配置/协议测试改动，不涉及
本次提交文件；包括 `laike_max_retries` 默认值断言、旧协议模型 dump 形状、
可 await 的 HMAC 返回值、显式签名头配置、显式 normalizer 注入和事件 ID 优先级。
这些运行逻辑不属于 Task 5，未修改或纳入提交。

编译检查：

```text
python -m compileall -q app alembic tools
```

通过。

差异检查：

```text
git diff --check
```

通过；仅有 Git 关于 LF/CRLF 的提示，没有 whitespace error。

## Commit

```text
678c55c2bf5f2f2ef11cc9fcfbde3822b81bc977
docs: document laike parity rollout and verification
```

## Concerns

- 完整回归仍有 8 个与 Task 5 无关的失败；它们反映工作区已有来客协议/运行逻辑
  改动与当前测试不一致，需要后续任务单独处理。
- 部署检查在 `LAIKE_WEBHOOK_ENABLED=false` 或未设置时只发送空 JSON，并要求返回
  disabled 状态；开关为 `true` 时跳过该安全探测，不猜测真实签名、事件 ID 或订单 ID。
- 真实 PHP 基线、脱敏业务数据库快照、HAR、Webhook 路径/签名/事件 ID/订单 ID 和
  测试凭据仍是外部前置条件，仓库未加入真实值。
