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
```

存活检查地址为 `http://127.0.0.1:18083/internal/health/live`。

接口迁移登记见 `contracts/api-manifest.json`。没有完成 PHP 基线对比的业务接口不会被标记为已迁移。

## 配置安全

复制 `.env.example` 后再按本地环境填写配置。真实 `.env`、生产数据库凭据、Token、证书、日志和上传文件禁止提交到 Git。PHP 基线回退只有在显式配置 `PHP_BASELINE_URL` 后才会启用。
