# 前端（soybean-admin）

本目录是「抖音订单管理系统」的前端，基于 [soybean-admin](https://github.com/soybeanjs/soybean-admin)（Vue3 + Vite + TypeScript + NaiveUI + UnoCSS + Pinia）。

## 环境要求

- Node >= 20.19.0
- pnpm >= 10.5.0

## 安装与启动

```powershell
pnpm install
pnpm dev        # 开发模式（走 test 环境，代理到后端）
pnpm build      # 生产构建，产物在 dist/
pnpm typecheck  # 类型检查
```

开发模式下，请求通过 `/proxy-default` 前缀代理到后端（默认 `http://127.0.0.1:18083`，见 `.env.test` 的 `VITE_SERVICE_BASE_URL`）。

## 生产构建与部署

```powershell
pnpm build   # 产物输出到 dist/
```

生产环境由 nginx 服务 `frontend/dist`（见 `deploy/nginx/douyin-order-python.conf` 的 `root`），
`/apiv1` 反代到后端 gunicorn。发布前需确保 `frontend/dist/index.html` 已生成（`deploy/scripts/publish.sh` 会校验）。

## 与后端对接说明

- 后端统一响应格式：`{ code, msg, data }`，成功 `code=1`、失败 `code=0`（见 `app/api/responses.py`）。
- 前端请求封装已对齐：`VITE_SERVICE_SUCCESS_CODE=1`（见 `.env`）。
- 登录：对接后端 demo 登录（`POST /apiv1/common/captcha` + `POST /apiv1/user/login`，带验证码）。
- 来客订单：对接 `/api/laike/orders`（见 `src/service/api/laike.ts`、`src/views/laike-order/index.vue`）。

## 已对接业务

| 模块 | 前端文件 | 后端接口 |
|------|---------|---------|
| 登录（验证码） | `src/views/_builtin/login/modules/pwd-login.vue` | `/apiv1/common/captcha`、`/apiv1/user/login` |
| 来客订单列表 | `src/views/laike-order/index.vue` | `/api/laike/orders` |

## 待办（后端接口就绪后再补）

- 其余 `/apiv1/*` 业务页面（当前后端 `register_business_routes` 为空，300+ 路由未迁移）。
