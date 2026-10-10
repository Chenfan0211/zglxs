# 抖音订单管理系统 Python 迁移基础服务

这是 PHP/ThinkPHP 系统渐进式迁移的 Python 基础工程。服务运行时只使用 Python，提供 FastAPI 启动、健康检查、兼容 API 分发和外部服务 Mock；PHP 只作为独立契约采集阶段的只读参考，不参与运行时请求。

## 开发环境

要求 Python 3.12：

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
```

## 测试和启动

```powershell
python -m pytest -q
python -m uvicorn app.main:app --host 127.0.0.1 --port 18083
```

本地联调可一键同时启动前端（vite dev server）和 Python API：

```powershell
python -m tools.local_stack
```

前端首次运行前需安装依赖（Node >= 20、pnpm >= 10）：

```powershell
cd frontend
pnpm install
```

本地前端地址为 `http://127.0.0.1:9527/`，通过 vite 的 `/proxy-default` 代理访问
`http://127.0.0.1:18083`；API 文档仍在 `http://127.0.0.1:18083/docs`。
本地启动器使用仅存在于进程环境中的演示登录配置，不连接测试服务器或业务数据库。
启动器会在终端输出本次演示账号和随机密码；也可以只在当前进程环境中设置
`LOCAL_DEMO_USERNAME`、`LOCAL_DEMO_PASSWORD` 后启动。Fixture 模式提供员工、
组织、订单和财务的脱敏只读数据，写接口仍返回“接口尚未迁移”。

存活检查地址为 `http://127.0.0.1:18083/internal/health/live`。

接口迁移登记见 `contracts/api-manifest.json`。没有完成黑盒契约对比的业务接口不会被标记为已迁移；未登记路径统一返回“接口尚未迁移”。
`READ_MODEL_FIXTURE_ENABLED` 只控制本地页面联调，不会注册正式路由，也不会增加
`/internal/migration/status` 的 `migrated_route_count`。
前端清单中的 68 条只读业务路由已由本地 Fixture 或 Dashboard 兼容层覆盖；90 条
写路由继续统一返回“接口尚未迁移”，不会在演示模式下执行写入。

部署模板位于 `deploy/`。发布服务器使用 `/srv/douyin-order-python/releases/<timestamp>` 和 `current` 符号链接；当前工作区只生成模板，不会自动修改服务器。

Linux 发布后可执行 `deploy/scripts/check-deploy.sh` 做前端、API、Nginx 和
Systemd 验收。该脚本默认检查 `18084` 公网入口和 `18083` 本机 API 入口。

## 配置安全

复制 `.env.example` 后再按本地环境填写配置。真实 `.env`、生产数据库凭据、Token、证书、日志和上传文件禁止提交到 Git。服务端不提供 PHP 运行时回退；契约采集工具单独接收 PHP 基线地址。

## 来客同步前置条件与安全模式

来客契约回放仍依赖外部提供的真实 PHP 基线、脱敏业务数据库快照、真实 HAR、
真实 Webhook 路径、真实签名、真实事件 ID、真实订单 ID 和测试凭据；仓库不猜测
这些协议细节，也不保存真实凭据、Token、手机号或地址。

安全模式默认值必须保持为：`LAIKE_SYNC_MODE=observe`、
`LAIKE_WEBHOOK_ENABLED=false`、`LAIKE_RECONCILE_ENABLED=false`、
`LAIKE_WRITE_ENABLED=false`。在 PHP/Python 回放和数据库副作用比较全部通过前，
`contracts/api-manifest.json` 的 migrated_routes 保持为空。

## 来客订单轮询

官方订单轮询使用 `LAIKE_APP_ID`、`LAIKE_APP_SECRET` 获取 Client Token，调用
`https://open.douyin.com/goodlife/v1/trade/order/query/`。订单只写入独立的
`LAIKE_DATABASE_URL`，不会回退或共写 `DATABASE_URL`。默认同步模式为 `observe`，
只有显式使用 `shadow` 才写入同步订单表。查询地址为 `/api/laike/orders`、
`/api/laike/orders/{order_id}` 和 `/api/laike/sync-runs`，这些新 REST 接口不代表
旧 `/apiv1` 业务路由已经迁移。

如需让旧前端订单列表读取独立来客同步库，可仅在本机 test/staging 环境显式设置
`LAIKE_LEGACY_READ_ENABLED=true`。该兼容入口支持 `user/order/tradelist` 和
`user/order/detail`，要求 DEMO 会话并限制回环访问；其他旧订单查询返回稳定空结构
和“接口尚未迁移”。它不会登记到 `migrated_routes`，生产环境即使设置该开关也不会启用。

没有凭据时不会发起抖音网络请求。注入凭据后，先执行 `alembic upgrade head`，再启动
API 和 Celery Worker/Beat；建议先使用 `LAIKE_SYNC_MODE=shadow` 写入独立同步库，
确认数据后再调整模式。Mock 回归命令：

```powershell
python -m pytest tests/test_douyin_laike_client.py tests/test_laike_official_sync.py tests/test_laike_order_query_api.py -q
python -m compileall -q app alembic tools tests
git diff --check
```

