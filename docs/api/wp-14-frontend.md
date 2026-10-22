# 前端接口类型

前端以 `docs/api/openapi.wp14.json` 为机器可读契约，并生成 `frontend/src/generated/api-schema.ts`（文件名沿用开发阶段的编号）。后端接口改动后两者都要重新生成，否则 CI 的接口一致性检查会失败。

```powershell
cd E:\Work\xiutu-v5\frontend
npm.cmd run api:generate
npm.cmd run api:check
```

`api:check` 同时检查当前后端 OpenAPI 与封存 JSON，以及生成的 TypeScript 与工作区文件是否一致。

写请求由统一客户端（`frontend/src/formal/api-client.ts`）添加内存 CSRF 和每个逻辑操作的 `Idempotency-Key`。错误保留 HTTP 状态、服务端 code、details 和 trace_id；401 会清理客户端会话状态，409/413/422 不映射成空结果。
