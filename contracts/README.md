# API 契约清单

`api-manifest.json` 是迁移过程中的接口登记入口：

- `discovered_routes`：从前端网络请求、PHP 基线和运行日志中发现但尚未完成对比的接口。
- `migrated_routes`：已经完成 PHP/Python 响应和数据库副作用对比、允许由 Python 接管的接口。
- `fallback_enabled_by_default`：默认必须为 `false`；只有部署环境显式配置 `PHP_BASELINE_URL` 才开启回退。
- `route_record_template`：登记接口时必须复制并填写的最小结构。

每个真实业务接口加入 `migrated_routes` 前，必须记录：

- HTTP 方法、controller、action。
- 请求参数位置、类型、默认值和空值行为。
- 成功响应包装、字段类型、分页、排序和筛选语义。
- 错误码、错误文案、认证和权限行为。
- 写操作影响的数据库表、事务边界和幂等行为。

第一阶段不登记任何真实业务接口。

## 来客契约回放门槛

回放前仍需从外部取得真实 PHP 基线、脱敏业务数据库快照、真实 HAR、真实 Webhook
路径、真实签名、真实事件 ID、真实订单 ID 和测试凭据。仓库只保留脱敏占位数据，
不包含真实凭据、Token、手机号或地址。

安全模式默认值必须是 `LAIKE_SYNC_MODE=observe`、`LAIKE_WEBHOOK_ENABLED=false`、
`LAIKE_RECONCILE_ENABLED=false`、`LAIKE_WRITE_ENABLED=false`。在 PHP/Python 回放和
数据库副作用比较全部通过前，`contracts/api-manifest.json` 的 migrated_routes
保持为空。
