# API 契约清单

`api-manifest.json` 是迁移过程中的接口登记入口：

- `discovered_routes`：从前端网络请求、PHP 基线和运行日志中发现但尚未完成对比的接口。
- `migrated_routes`：已经完成 PHP/Python 响应和数据库副作用对比、允许由 Python 接管的接口。
- `fallback_enabled_by_default`：默认必须为 `false`；只有部署环境显式配置 `PHP_BASELINE_URL` 才开启回退。

每个真实业务接口加入 `migrated_routes` 前，必须记录：

- HTTP 方法、controller、action。
- 请求参数位置、类型、默认值和空值行为。
- 成功响应包装、字段类型、分页、排序和筛选语义。
- 错误码、错误文案、认证和权限行为。
- 写操作影响的数据库表、事务边界和幂等行为。

第一阶段不登记任何真实业务接口。
