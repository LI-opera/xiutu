# WP-14 正式前端与资料中心实施契约

状态：`IMPLEMENTED_NOT_ACCEPTED`  
日期：2026-09-21  
范围：仅 WP-14；不实施 WP-15 的诊断联调、SSE、观察、区域切换或报告交互。

## 1. 基准与边界

- 依赖 WP-13 限定接受基准，以及已接受的资料预览、资料待核实入口、DKVB 专题和诊断切片。
- 正式应用在现有 `frontend` 工程中增加 `/workbench`、`/documents`、`/history` 可恢复路由；`/preview` 与既有 hash 入口继续加载原预览界面。
- 本包不操作或部署 5180/5196，不改变其数据库、storage、会话、索引或现用构建。
- 真实资料仍为 `NOT_MET`。`unknown` 不显示为确诊、排除或最终报告就绪。

## 2. 接口与调用顺序

### 2.1 会话与统一客户端

1. `GET /api/v2/auth/session` 恢复 cookie 会话；401 显示登录页。
2. `POST /api/v2/auth/login` 仅提交访问令牌，响应中的 CSRF 只保存在内存。
3. 同源写请求携带 `Origin`（由浏览器生成）、`X-CSRF-Token` 与调用方生成的 `Idempotency-Key`。
4. 客户端统一处理超时、取消、401/409/413/422、结构化 `details` 与可复制 `trace_id`；不得把错误映射为空结果。

### 2.2 资料中心

1. `GET /api/v2/client-config` 读取服务端实际 `upload_max_bytes`。
2. 上传使用 `POST /api/v2/documents`，metadata 严格采用服务端 `DocumentInput`；未知适配字段保持空值。
3. 轮询真实版本状态，人工审核调用版本 `review`，索引状态来自服务端。
4. 原文与切块读取实际版本接口；试搜调用 `/api/v2/evidence/search`，只显示返回的命中和排除原因。
5. 合成、待核实非虚构、`needs_ocr`、`formal_usable` 与索引资格分别展示；前端不改写资格。

### 2.3 工作台与历史

1. `/workbench` 只显示车辆/病例创建表单；`/workbench/:caseId` 以 URL 中的 case id 读取快照。
2. 创建请求严格区分 `engine_family` 和 `engine_code`；可未知字段留空。
3. 三栏仅展示现有 snapshot 或明确空态，不提供 WP-15 按钮。
4. `/history` 在用户提交搜索后才读取病例列表；用户选择后才导航到病例，不自动打开最新病例。

## 3. 类型与状态所有权

- 从正式 `create_app()` OpenAPI 导出 `docs/api/openapi.wp14.json`，由生成器产生 `frontend/src/generated/api-schema.ts`；`api:check` 对两者做无写入差异检查。
- 现有 `frontend/src/api-schema.ts` 明确作为预览兼容类型保留，正式页面不得导入它。
- TanStack Query 保存服务端事实；React 本地状态只保存路由选择、展开项和未提交草稿，不将完整病例写入 localStorage。

## 4. 实际文件

- 后端薄接口：`backend/app/api/client_config.py`、`backend/app/domain/schemas.py`、`backend/app/main.py`。
- OpenAPI：`scripts/export_frontend_openapi.py`、`docs/api/openapi.wp14.json`、`frontend/src/generated/api-schema.ts`。
- 正式前端：`frontend/src/formal/`、`frontend/src/tokens.css`、`frontend/src/formal.css`、`frontend/vite.config.ts`，以及入口 `frontend/src/main.tsx` 的最小分流。
- 验证：正式前端组件/状态测试、客户端测试、配置接口测试和独立构建/浏览器证据。

## 5. 验证顺序

1. 配置接口与 OpenAPI 生成/差异检查。
2. API 客户端、输入边界、状态失效、history 主动选择与路由恢复的定点测试。
3. 既有预览状态测试，确认原入口无明显回退。
4. TypeScript typecheck 与独立 production build，不覆盖 `frontend/dist`。
5. 新隔离 PostgreSQL、storage、后端与浏览器会话走通 documents、history、workbench；保存 1440×900、1024×768、390×844 截图。
6. 运行一次适合 WP-14 的前端/接口回归。只有发现明确共享后端风险才扩大测试，不运行约 41 分钟的全后端入口。

## 6. 完成条件

- 三个正式路由可刷新恢复，所有按钮调用真实接口并反馈真实状态。
- OpenAPI 生成与差异检查通过，正式页面没有手写同名 API schema。
- 三视口无关键溢出、遮挡或焦点缺失，预览入口仍可访问。
- 交付结果和证据后，状态只到 `IMPLEMENTED_NOT_ACCEPTED`，等待集中审核。
