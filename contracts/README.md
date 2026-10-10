# API 契约清单

`api-manifest.json` 是迁移过程中的接口登记入口：

- `discovered_routes`：从前端网络请求、PHP 基线和运行日志中发现但尚未完成对比的接口。
- `migrated_routes`：已经完成 PHP/Python 响应和数据库副作用对比、允许由 Python 接管的接口。
- `fallback_enabled_by_default`：历史兼容字段，必须为 `false`；Python 服务不提供 PHP 运行时回退。
  PHP 地址只能传给独立契约采集工具，不能通过服务配置启用运行时代理。
- `route_record_template`：登记接口时必须复制并填写的最小结构。

每个真实业务接口加入 `migrated_routes` 前，必须记录：

- HTTP 方法、controller、action。
- 请求参数位置、类型、默认值和空值行为。
- 成功响应包装、字段类型、分页、排序和筛选语义。
- 错误码、错误文案、认证和权限行为。
- 写操作影响的数据库表、事务边界和幂等行为。

登记必须通过 `tools.promote_routes`，不能手工修改 `migrated_routes`。证明文件的
每条路由必须同时包含 `registered=true`、`response_mismatches=[]`、
`http_status_codes_passed=true`、`response_schema_passed=true`、
`permission_cases_passed=true`、`error_cases_passed=true`、
`database_effects_passed=true`、`query_side_effects_passed=true`、
`transaction_rollback_passed=true`、`idempotency_passed=true` 和
`concurrency_passed=true`。对应模块开关必须开启，路由也必须已经存在于
`discovered_routes` 和应用正式注册表：

```powershell
python -m tools.promote_routes `
  --manifest contracts/api-manifest.json `
  --proof contracts/fixtures/organization/verification.json
```

任意响应差异、权限差异、数据库副作用差异、事务回滚失败、重复路由或缺少证明
都会拒绝登记，不会部分修改清单。

第一阶段不登记任何真实业务接口。当前缺口矩阵可通过以下命令生成，命令只读分析清单和本地 Fixture：

```powershell
python -m tools.contract_inventory `
  --manifest contracts/api-manifest.json `
  --fixtures contracts/fixtures/read-model.json `
  --gap-output contracts/interface-gap-matrix.json
```

矩阵中的 `fixture_covered` 仅表示本地页面联调覆盖，不表示正式接口已迁移。

## 来客契约回放门槛

回放前仍需从外部取得真实 PHP 基线、脱敏业务数据库快照、真实 HAR、真实 Webhook
路径、真实签名、真实事件 ID、真实订单 ID 和测试凭据。仓库只保留脱敏占位数据，
不包含真实凭据、Token、手机号或地址。

安全模式默认值必须是 `LAIKE_SYNC_MODE=observe`、`LAIKE_WEBHOOK_ENABLED=false`、
`LAIKE_RECONCILE_ENABLED=false`、`LAIKE_WRITE_ENABLED=false`。在 PHP/Python 回放和
数据库副作用比较全部通过前，`contracts/api-manifest.json` 的 migrated_routes
保持为空。

来客官方轮询协议的脱敏夹具位于 `contracts/fixtures/laike/`。其中
`douyin-token.jsonl` 和 `douyin-order-query.jsonl` 只描述官方请求形状，不包含真实
凭据或订单敏感字段。真实同步库必须通过 `LAIKE_DATABASE_URL` 单独配置，禁止回退到
`DATABASE_URL`。
