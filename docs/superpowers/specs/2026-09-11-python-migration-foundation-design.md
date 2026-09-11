# Python 迁移基础骨架设计

**日期：** 2026-09-11

## 目标

为抖音订单管理系统建立第一阶段可运行的 Python 迁移基础设施，支持 FastAPI 服务启动、数据库连通性检查、现有 `/apiv1/{controller}/{action}` 路径兼容，以及迁移期间对未迁移接口回退到内部 PHP 基线。

这一阶段不实现订单业务，不连接生产数据库，不复制压缩包中的 `.env`、Token、证书、日志或上传文件，也不解密或推测受保护的 PHP 文件。

## 当前输入与约束

- 现有代码仓库为空，仅包含用户已有的 `.idea/`。
- PHP 源码位于用户提供的 `wwwroot.zip`，其中部分业务控制器和模型不可直接阅读。
- 方案要求 Python 3.12、FastAPI、Pydantic 2、SQLAlchemy 2、PyMySQL、Alembic、Celery + Redis、pytest、httpx。
- 现有业务前端依赖 `/apiv1/...` 路径、方法、参数名、响应包装和登录状态。
- PHP 基线仅作为迁移期间的内部回退服务，地址通过配置提供，默认关闭。

## 方案

### 服务边界

工程按以下边界组织：

- `app/main.py`：创建 FastAPI 应用和生命周期对象。
- `app/core/settings.py`：从环境变量读取非敏感配置，敏感值只通过部署环境注入。
- `app/db/`：延迟创建 SQLAlchemy Engine 和 Session，不在模块导入时连接数据库。
- `app/api/`：健康检查和兼容 API 入口。
- `app/integrations/php_baseline.py`：把未迁移请求转发给内部 PHP 基线。
- `app/integrations/providers.py`：外部服务适配器协议和可重复的 Mock。
- `contracts/`：接口清单和契约记录入口。

### 迁移路由

使用显式 `MigrationRegistry` 保存已经由 Python 接管的接口。兼容入口收到请求后按以下顺序处理：

1. 查找 `(controller, action, HTTP method)` 的 Python handler。
2. 找到则由 Python handler 返回兼容响应。
3. 未找到且配置了 `PHP_BASELINE_URL`，调用 PHP 基线代理。
4. 未找到且没有 PHP 基线，返回 404，并说明接口尚未登记迁移。

第一阶段不登记任何真实业务接口，避免在没有 PHP 行为契约的情况下制造虚假兼容实现。测试使用独立的探针 handler 验证注册路径。

代理只转发业务请求需要的 headers、query string、body 和 cookies，剔除 `host`、`content-length` 等 hop-by-hop 头；代理失败时返回稳定的 502 错误，不暴露内部堆栈或凭据。

### 健康检查

- `/internal/health/live`：仅本机可访问，表示进程已启动，返回 JSON `{"status": "ok"}`。
- `/internal/health/ready`：仅本机可访问；未配置数据库时返回 503；配置数据库后执行 `SELECT 1`，成功返回 `{"status": "ok", "checks": {"database": "ok"}}`。
- 本地测试可以通过 FastAPI dependency override 注入本机请求，生产不放宽访问限制。

### 数据库基础

数据库 URL 由 `DATABASE_URL` 提供，默认 `None`。SQLAlchemy Engine 采用懒加载；测试使用 SQLite，正式配置使用 MySQL/PyMySQL。第一阶段只建立连接和探活能力，不创建或修改任何业务表。

### 外部服务 Mock

定义以下协议名称，保持后续业务模块的依赖方向稳定：

- `DouyinLaikeProvider`
- `SmsProvider`
- `CloudCallProvider`
- `WebhookProvider`

第一阶段提供固定响应的 Mock 实现。Mock 只记录不含 Token、手机号、订单个人信息的请求摘要，并支持成功和模拟失败两种结果，禁止访问真实外部域名。

## 错误和安全处理

- 未配置 PHP 基线时不得尝试网络访问。
- PHP 基线代理只允许连接配置的内部基线地址，不接受来自请求参数的目标 URL。
- 健康检查拒绝非回环地址请求。
- 配置文件提交 `.env.example`，不提交真实 `.env`。
- 应用日志不写入请求 body、Authorization、Cookie 或完整 URL 查询参数。
- 统一返回结构化、无堆栈的错误响应。

## 测试策略

第一阶段测试覆盖：

- 应用可以在无数据库、无 PHP 基线配置时创建。
- Python 已登记 handler 能通过兼容路径返回响应。
- 未登记路径在配置基线时转发，并保持状态码、响应体和内容类型。
- 未登记路径在未配置基线时返回 404。
- 健康接口的本机限制、存活结果和数据库 ready 结果。
- 四类外部 Provider Mock 的固定成功响应和失败行为。
- 配置读取不依赖真实 `.env`，并允许测试覆盖环境变量。

测试只使用本地内存/SQLite 和 ASGI/HTTPX 测试客户端，不触发真实 PHP、数据库或外部服务。

## 不在本阶段

- 登录、Token 生命周期和权限系统。
- 订单、部门、直播间、财务等业务模型及状态机。
- 从生产数据库导出、脱敏和初始化种子。
- 真实 PHP 服务部署、Nginx/Systemd 配置和服务器操作。
- 管理后台重建。
- Celery 任务和 Redis 连接。

## 验收标准

在干净 Python 3.12 环境中可以执行：

```powershell
python -m pip install -e ".[test]"
python -m pytest -q
python -m uvicorn app.main:app --host 127.0.0.1 --port 18083
```

并满足：

- 测试全部通过。
- `GET /internal/health/live` 返回 200。
- 未配置 `PHP_BASELINE_URL` 时，不发生外部网络调用。
- 代码和示例配置中没有来自压缩包 `.env` 的真实凭据。
