# 来客订单同步集中修复报告

日期：2026-09-12

本波次针对最终审查结论 A-H 完成集中修复。所有实现仍限制在 Python 自有同步表和测试库内，未修改加密 PHP，未注册任何真实 legacy route，也未发起外部网络请求。

## Findings 修复说明

- A Critical：在 `app/laike/repositories.py` 增加集中式 `sanitize_request_headers`。Authorization、Cookie、Token、Secret、Signature、Password、API-Key、Credential 相关 header 不再进入 `headers_json`，非敏感追踪 header 保留；真实 SQLite 持久化测试覆盖八类敏感 key。
- B Critical：`_process_page` 统一受模式闸门控制。observe 只归一化、计数和记录 run，不写 `laike_order`；shadow 写 Python 自有同步表；write 仅在 `laike_sync_mode == "write"` 且 `laike_write_enabled is True` 时写入。Webhook worker 在 observe 下即使没有订单写入也会成功处理事件，不会因计数为零重试。新增四种模式 SQLite 行为测试，并将依赖写入的旧 fixture 明确设为 shadow。
- C Critical：`HttpLaikeClient` 委托 `WebhookVerifier` 返回配置 event header；service 优先使用 `verification.event_id`。新增真实 HTTP client + verifier 测试，body 不含 event_id 时仍按 header 幂等。
- D Important：路由现在只负责开关和 JSON body 格式检查，验签与接收均由 service 完成一次。失败 envelope 使用 service 的安全 reason，且不回显内部结果数据；路由测试覆盖单次验签和敏感文案不泄漏。
- E Important：Repository 更新已有订单时仅用非 `None` 值覆盖字段，增量 payload 不会清空既有 subject、product、created time 等字段；完整非空快照更新行为保持不变，并新增回归测试。
- F Important：`pyproject.toml` 增加 `pythonpath = ["."]`，根目录 `pytest -q` 与 `python -m pytest -q` 均可直接收集和运行。
- G Important：保留分页部分成功、游标不推进、成功订单已提交的 at-least-once 方案，以及现有条件更新和 token fencing scanner。迁移状态文档补充整页幂等重放说明；既有 cursor/rollback 测试继续覆盖该语义。
- H P2：补充实际 `LAIKE_*` 环境变量 alias 读取测试，并用脱敏 demo 值覆盖配置字段；未写入真实凭据。header sanitizer 测试覆盖八类敏感 key。

## 验证记录

- `pytest -q`：194 passed
- `python -m pytest -q`：194 passed
- `python -m compileall -q app alembic tools`：通过
- `git diff --check`：通过

## 未覆盖的外部前置条件

真实来客 Webhook 路径、签名算法、订单唯一 ID、业务字段映射和 PHP/HAR/测试凭据仍未提供，因此没有进行生产协议猜测或 legacy route 接管。
