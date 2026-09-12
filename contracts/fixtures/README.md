# 正式业务契约夹具

`organization`、`order` 和 `finance` 目录由 `python -m tools.contract_scaffold`
创建。空的 JSONL 和 JSON 文件只是采集占位，不代表接口契约已经通过，也不会自动加入
`contracts/api-manifest.json` 的 `migrated_routes`。

提交前必须脱敏：密码、Token、Cookie、手机号、地址、完整订单 payload 和第三方签名
统一替换为 `[REDACTED]`。只有 PHP/Python 回放、数据库副作用、权限、错误、事务和幂等
证明全部通过后，才能使用 `tools.promote_routes` 登记路由。
