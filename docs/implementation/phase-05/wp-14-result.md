# WP-14 正式前端与资料中心实施结果

时间：2026-09-21  
状态：`IMPLEMENTED_NOT_ACCEPTED`  
范围：仅 WP-14，等待一次集中审核。

## 实际交付

1. 在现有 React/Vite 工程增加 `/workbench/:caseId?`、`/documents`、`/history` 正式路由和统一导航。根预览和已接受 hash 入口仍走旧实现，本包没有部署或操作 5180/5196。
2. 从服务端 `create_app()` 导出 OpenAPI，生成 TypeScript schema 并建立无写入差异检查。旧 `api-schema.ts` 明确隔离给预览入口。
3. 统一 API client 支持 cookie 会话、内存 CSRF、幂等键、取消/超时、结构化 details/trace_id 及 401/409/413/422 中文错误。任意后续请求的 401 会退回登录态。
4. 资料中心实际连接上传、版本轮询、人工审核、索引状态、不可变原件、切块和证据试搜。上传上限由新的受认证 `/client-config` 返回，后端原限制仍生效。页面分别显示 synthetic、非虚构待核实、needs_ocr、formal_usable 和索引排除原因。
5. 工作台只创建服务端病例并从 URL case id 读回 snapshot，明确分开 engine_family/engine_code。三栏不含诊断、观察、切区或报告假操作。
6. 历史页只在用户主动提交条件后搜索，点选后导航；无 case id 保持初始态。服务器数据由 TanStack Query 管理，没有用 localStorage 复制病例事实。
7. 新增 tokens、统一列标题/加载/空态/错误/状态标签、键盘焦点和响应式布局。

## 文件变化

- 后端薄接口：`backend/app/api/client_config.py`，以及 `main.py`、`api/openapi.py`、`domain/schemas.py` 的必要注册/schema。
- 正式前端：`frontend/src/formal/**`、`tokens.css`、`formal.css`、`main.tsx`、`vite.config.ts`、测试和生成 schema。
- 工具与说明：`scripts/export_frontend_openapi.py`、`scripts/wp14_frontend.py`、`docs/api/openapi.wp14.json`、`docs/api/wp-14-frontend.md`、`docs/runbooks/frontend.md`。
- 直接依赖：TanStack Query、React Router、openapi-typescript、Vitest/jsdom 和 Testing Library，已同步 `package-lock.json`。

## 验证结果

- 最终正式前端：15 项通过；TypeScript 检查、OpenAPI 差异检查、独立 production build 全部 exit 0。
- 预览兼容：24 项 Node 状态测试通过；对应后端预览定点在正确的新隔离库中 5 项通过。
- 配置接口：1 项通过，1 条既有 Starlette 弃用警告。首次 pytest 默认临时根权限失败未执行业务断言，已保留日志，后用独立 `--basetemp` 执行。
- 真实隔离浏览器走通 documents/history/workbench，包括真实解析、人工审核、worker 索引、检索和 case 刷新恢复。三个指定视口截图已保留在浏览器证据轨迹。
- 详细命令、失败/修正和浏览器结果见 [验证摘要](evidence/wp-14/verification-summary.md) 及同目录原始日志。

## 失败与修正记录

- 首次前端组件集 13/14 通过；唯一失败是测试错把 React Router 的路由文本当作可见 DOM，删除该无效测试假设后受影响 6 项通过。没有改变产品断言。
- 1024 截图首次发现旧全局 `header` 高度影响新布局，为正式 `.app-header` 显式设置自然高度；最终截图无重叠。
- product-preview 后端检查的两次 fixture 前置失败和 pytest 临时目录失败都保留；未通过重跑或放宽断言消除产品失败。

## 未验证与保留项

- 真实资料门槛仍为 `NOT_MET`；本包隔离数据是合成资料，不是真实维修验收。
- 未实施分片上传、OCR、超限整书、真实资料完整审核平台。
- 诊断联调、SSE、观察提交、区域切换和报告交互属于 WP-15 或后续包。本包不改写已接受的预览和诊断切片范围。
- 未运行约 41 分钟全后端入口；本包只增加一个读配置薄接口和前端，已运行直接合同/预览兼容回归。
- 没有付费模型请求，没有部署或操作 5180/5196，没有提交/推送。

## 停止点

WP-14 为 `IMPLEMENTED_NOT_ACCEPTED`，等待一次集中审核。WP-15—17 保持 `NOT_STARTED`。
