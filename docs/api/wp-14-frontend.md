# WP-14 正式前端接口绑定

正式前端以 `docs/api/openapi.wp14.json` 为机器可读契约，并生成 `frontend/src/generated/api-schema.ts`。`frontend/src/api-schema.ts` 只属于旧预览入口，正式页面不得导入它。

```powershell
cd E:\Work\xiutu-v5\frontend
npm.cmd run api:generate
npm.cmd run api:check
```

`api:check` 同时检查当前后端 OpenAPI 与封存 JSON，以及生成 TypeScript 与工作区文件是否一致。

## 主要绑定

- 会话：`/auth/login`、`/auth/session`、`/auth/logout`。
- 前端运行配置：`GET /client-config`，仅返回有界上传上限和服务端固定的检索 profile，不返回凭据。
- 病例：`POST /cases`、`GET /cases/{case_id}`、`GET /cases`、`GET /cases/{case_id}/diagnosis/snapshot`。
- 资料：上传、版本读取、审核、不可变原件、切块和 `/evidence/search`。

写请求由统一客户端添加内存 CSRF 和每个逻辑操作的 `Idempotency-Key`。错误保留 HTTP 状态、服务端 code、details 和 trace_id；401 会清理客户端会话状态，409/413/422 不映射成空结果。

## 边界

WP-14 工作台只创建/读取病例和展示三栏骨架。诊断启动、SSE、观察表单、区域切换和报告交互不在本包。
