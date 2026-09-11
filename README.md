# 抖音订单管理系统 Python 迁移基础服务

这是 PHP/ThinkPHP 系统渐进式迁移的 Python 基础工程。第一阶段只提供 FastAPI 启动、健康检查、兼容 API 分发、PHP 基线回退和外部服务 Mock，不实现真实订单业务。

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
python -m tools.inspect_wwwroot C:\path\to\wwwroot.zip
python -m tools.frontend_bundle C:\path\to\wwwroot.zip .\frontend
```

存活检查地址为 `http://127.0.0.1:18083/internal/health/live`。

接口迁移登记见 `contracts/api-manifest.json`。没有完成 PHP 基线对比的业务接口不会被标记为已迁移。

部署模板位于 `deploy/`。发布服务器使用 `/srv/douyin-order-python/releases/<timestamp>` 和 `current` 符号链接；当前工作区只生成模板，不会自动修改服务器。

Linux 发布后可执行 `deploy/scripts/check-deploy.sh` 做前端、API、Nginx 和
Systemd 验收。该脚本默认检查 `18084` 公网入口和 `18083` 本机 API 入口。

## 配置安全

复制 `.env.example` 后再按本地环境填写配置。真实 `.env`、生产数据库凭据、Token、证书、日志和上传文件禁止提交到 Git。PHP 基线回退只有在显式配置 `PHP_BASELINE_URL` 后才会启用。

## 来客同步前置条件与安全模式

来客契约回放仍依赖外部提供的真实 PHP 基线、脱敏业务数据库快照、真实 HAR、
真实 Webhook 路径、真实签名、真实事件 ID、真实订单 ID 和测试凭据；仓库不猜测
这些协议细节，也不保存真实凭据、Token、手机号或地址。

安全模式默认值必须保持为：`LAIKE_SYNC_MODE=observe`、
`LAIKE_WEBHOOK_ENABLED=false`、`LAIKE_RECONCILE_ENABLED=false`、
`LAIKE_WRITE_ENABLED=false`。在 PHP/Python 回放和数据库副作用比较全部通过前，
`contracts/api-manifest.json` 的 migrated_routes 保持为空。
