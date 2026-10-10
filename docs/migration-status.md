# 迁移状态

> **2026-10-10 更新**：五大业务模块（组织/直播/订单/财务/系统）已正式实现并部署到
> 测试服务器（192.168.28.180）。前端页面、后端接口、数据模型、数据库迁移全部完成，
> 共 166 条接口路由已实现（90 条写操作 + 68 条只读 + 8 条认证），不再依赖 PHP 源码、
> legacy 只读适配器或本地 Fixture 假数据。订单/财务对接来客同步库真实数据，
> 组织/直播/客服/系统使用本地业务表。短信/微信等外部集成接口提供明确占位（返回 501 未配置）。
> 旧过渡期适配器（legacy_laike_orders、fixture_reads）已下线移除。
> console 中控工作台接口（原 demo_dashboard 假数据）已全部改为对接真实业务表与来客同步库，
> 项目中已无 DEMO 假数据接口；短信/微信等外部集成接口提供明确的「未配置」占位响应。


## 迁移登记状态（重要）

> 当前项目处于「代码已实现、契约未迁移」的过渡阶段，请区分以下三个层次，避免
> 把「已实现」误读为「已迁移」：

1. **代码实现层**：五大业务模块（组织/直播/订单/财务/系统）接口已在
   `app/api/*.py` 中实现，通过 `app.main` 的 `include_router` 直接挂载到 FastAPI，
   对接来客同步库（`LAIKE_DATABASE_URL`）与本地业务表。这些接口在本地/测试环境
   可实际响应（需 DEMO 会话与数据库配置），但**不属于契约门禁下的正式迁移**。
2. **本地联调层**：`READ_MODEL_FIXTURE_ENABLED` 提供 56 条脱敏 Fixture，其中 54 条
   对应当前前端清单，用于本地页面联调；它们只读、带 `DEMO-*` 标识，不进入正式
   注册表。
3. **契约迁移层（门禁）**：`app/domain/routes.py` 的 `register_business_routes`
   当前为空实现，`MigrationRegistry` 未登记任何正式路由，因此
   `contracts/api-manifest.json` 的 `migrated_routes` 保持为 `[]`，接口方法仍为
   `UNKNOWN`。`/internal/migration/status` 返回 `migrated_route_count=0`，
   `contracts/interface-gap-matrix.json` 的 `totals.migrated=0`。

只有通过 PHP/Python 黑盒回放与数据库副作用对比、并由 `tools.promote_routes`
登记后，接口才会进入 `migrated_routes` 并计入正式迁移数量。在证据齐备前，
写操作接口统一返回「接口尚未迁移」，不会在演示模式下执行写入。

## 已完成

- FastAPI、SQLAlchemy、认证/权限、统一响应、事务和 Repository 基础能力。
- Celery/Redis 配置壳和 Alembic 空基线。
- PHP/Python JSONL 契约比较工具、动态字段归一化和数据库快照差异入口。
- 从 `wwwroot.zip` 编译前端提取旧 `/apiv1` 路径的黑盒证据清单，保存在
  `contracts/frontend-route-inventory.json`；接口方法仍标记为 `UNKNOWN`，未注册迁移。
- 前端框架已迁移为 soybean-admin（Vue3 + Vite + TypeScript + NaiveUI），本地联调
  `tools.local_stack` 一键启动 vite dev server 与 Python API；生产由 nginx 服务 `frontend/dist`
  构建产物。旧静态前端提取工具（`frontend_bundle`/`local_preview`/`inspect_wwwroot`）已移除。
- Nginx、Systemd、发布和回滚模板。
- 正式业务契约夹具脚手架，默认创建 organization、order、finance 三套空证据目录，
  不写入业务数据，也不会自动提升路由。
- 目标站点静态前端与本地清单的差异记录在
  `contracts/target-site-route-delta.json`；该记录仍属于 discovered-only 证据。
- 本地 `READ_MODEL_FIXTURE_ENABLED=true` 时提供 56 条只读联调 Fixture，其中 54 条
  对应当前前端清单，另有 2 条兼容别名；数据全部带 `DEMO-*` 标识，仅用于本地
  联调验证，不属于 PHP 契约证明，也不会进入 `MigrationRegistry`。
- `tools.promote_routes` 会从应用正式业务路由装配器读取真实注册表。proof 文件中的
  `registered` 或 `registered_route` 不能替代代码注册事实；提升成功后会在清单保留
  模块开关、证明文件和各项安全验证结果。
- Python 运行时已移除 PHP 回退入口和相关配置；`/apiv1` 请求只进入已登记的 Python
  路由、本地 Fixture，或返回统一的“接口尚未迁移”响应。PHP 仅保留为独立契约采集
  工具的只读参考。
- 当前接口缺口矩阵位于 `contracts/interface-gap-matrix.json`：前端发现路由共 166 条，
  其中 54 条与本地 Fixture 路径重合，112 条仍待补充；Fixture 文件共 56 条，另有
  `user/getInfo` 和 `live/room` 两条兼容路径未进入当前前端清单；正式
  `migrated_routes` 为 0 条。
- 按业务动作重新审计后，166 条路由包含认证 8 条、只读 68 条、写操作 90 条。
  68 条只读路由均已由 Fixture 或 Dashboard 本地兼容层提供稳定响应；90 条写操作
  均保持明确未迁移，不在 DEMO 模式执行写入。
- 可选的 `LAIKE_LEGACY_READ_ENABLED` 仅允许在本机 test/staging 使用来客独立同步库
  提供旧订单列表和详情。该入口不加入正式注册表，生产环境强制禁用。

## 当前阻塞

- 不能从压缩包直接启动隔离 PHP 基线；业务 PHP 控制器/模型是加密二进制。
- 压缩包没有业务数据库快照或业务结构 SQL，只有 FastAdmin 安装 SQL。
- 目前没有可调用的 PHP 业务基线，无法进行正式接口回放。
- 远端 PHP 登录页可以访问，但验证码尚未由用户交互完成，因此没有采集或提交任何
  远端登录请求、Cookie 或业务响应。
- 当前没有可用于行为对比的脱敏种子数据、低权限测试账号或测试数据库凭据。
- 仍需外部提供真实 PHP 基线、脱敏业务数据库快照、真实 HAR、真实 Webhook 路径、
  真实签名、真实事件 ID、真实订单 ID 和测试凭据；这些信息不写入仓库。
- 安全模式默认值为 `LAIKE_SYNC_MODE=observe`、`LAIKE_WEBHOOK_ENABLED=false`、
  `LAIKE_RECONCILE_ENABLED=false`、`LAIKE_WRITE_ENABLED=false`。
- 在 PHP/Python 回放和数据库副作用比较全部通过前，migrated_routes 保持为空。
- 正式业务路由装配器当前为空，`migrated_routes` 仍为 `[]`。没有真实 PHP 响应、
  脱敏 schema、数据库快照和权限证据时，提升工具会拒绝登记。
- 分页单条失败时，已成功订单会保留而游标不推进；后续重试可重放整页，依靠订单唯一键幂等更新实现 at-least-once 语义。

## 下一步

1. 用户在远端登录页完成验证码交互，再只读采集员工、订单和财务请求。
2. 提供脱敏业务 schema、独立数据库快照和至少一个低权限测试账号。
3. 使用 `contracts/frontend-route-inventory.json` 作为请求采集范围，补录每条接口的真实方法和参数。
4. 录制 PHP/Python JSONL 请求结果和数据库快照，执行响应及副作用比较。
5. 按组织账号、直播、订单、财务、系统集成的顺序逐接口登记和迁移。
