# 迁移状态

## 已完成

- FastAPI、SQLAlchemy、认证/权限、统一响应、事务和 Repository 基础能力。
- Celery/Redis 配置壳和 Alembic 空基线。
- PHP/Python JSONL 契约比较工具、动态字段归一化和数据库快照差异入口。
- 从 `wwwroot.zip` 编译前端提取旧 `/apiv1` 路径的黑盒证据清单，保存在
  `contracts/frontend-route-inventory.json`；接口方法仍标记为 `UNKNOWN`，未注册迁移。
- `life.localhost.com` 前端静态包安全提取与 `/apiv1` 地址替换工具。
- Nginx、Systemd、发布和回滚模板。

## 当前阻塞

- 不能从压缩包直接启动隔离 PHP 基线；业务 PHP 控制器/模型是加密二进制。
- 压缩包没有业务数据库快照或业务结构 SQL，只有 FastAdmin 安装 SQL。
- 测试服务器 `18082` 当前返回通用站点页面，不是可调用的 PHP 业务基线，无法进行正式接口回放。
- 当前没有可用于行为对比的脱敏种子数据、PHP 服务地址或测试数据库凭据。
- 仍需外部提供真实 PHP 基线、脱敏业务数据库快照、真实 HAR、真实 Webhook 路径、
  真实签名、真实事件 ID、真实订单 ID 和测试凭据；这些信息不写入仓库。
- 安全模式默认值为 `LAIKE_SYNC_MODE=observe`、`LAIKE_WEBHOOK_ENABLED=false`、
  `LAIKE_RECONCILE_ENABLED=false`、`LAIKE_WRITE_ENABLED=false`。
- 在 PHP/Python 回放和数据库副作用比较全部通过前，migrated_routes 保持为空。
- 分页单条失败时，已成功订单会保留而游标不推进；后续重试可重放整页，依靠订单唯一键幂等更新实现 at-least-once 语义。

## 下一步

1. 提供可运行的 PHP 隔离基线和脱敏数据库快照，并确认测试账号可以访问所有菜单。
2. 使用 `contracts/frontend-route-inventory.json` 作为请求采集范围，补录每条接口的真实方法和参数。
3. 录制 PHP/Python JSONL 请求结果和数据库快照，执行响应及副作用比较。
4. 按组织账号、直播、订单、财务、系统集成的顺序逐接口登记和迁移。
