# WP-15 实施契约：完整诊断工作台联调与交互恢复

- 状态：IMPLEMENTING
- 日期：2026-09-21
- 工作目录：`E:\Work\xiutu-v5`
- 前置：WP-14 限定范围已接受；WP-11/12/13 仅按各自已接受的限定技术范围复用。

## 范围与停止点

本包把现有正式 `/workbench/:caseId` 外壳接到已接受的病例、诊断、区域、观察、任务事件、依据和报告 API。主路径是：读取病例快照，用户显式启动或恢复诊断，查看区域与当前检查及依据，按服务端输入定义提交观察，由任务事件触发重新读取，查看保守区域卡，并由用户显式请求进度或最终报告。观察更正导致 revision/epoch 变化后，页面只读取服务端给出的 stale 状态。

本包不改变 WP-10 校验、WP-11 图、WP-12 观察事务或 WP-13 ReportPolicy 语义；不实现新的结论规则、自动确诊、资料资格放宽、付费重试策略、生产部署或 WP-16。`unknown` 始终显示为待补，不能显示成确诊、排除或最终报告就绪。真实资料门槛保持 `NOT_MET`。

## 实际改动面

### 后端薄适配

- `backend/app/domain/schemas.py`：只增加现有服务返回值的严格响应模型。
- `backend/app/api/cases.py`、`backend/app/api/reports.py`：为既有读取和动作接口声明 `response_model`，不改变服务调用、事务、权限或错误码。
- `docs/api/openapi.wp14.json` 与 `frontend/src/generated/api-schema.ts`：由现有脚本重新生成并校验漂移。

### 正式前端

- `frontend/src/formal/pages/WorkbenchPage.tsx`：病例入口与工作台编排；所有服务端事实由 TanStack Query 管理。
- `frontend/src/formal/diagnosis/*`：AreaTree、CurrentStep、ObservationForm、AreaConclusion、EvidenceDrawer、FinalAdvice、RunStatus、SSE 客户端及由生成类型派生的类型。
- `frontend/src/formal/api-client.ts`：在既有 cookie/CSRF/错误映射基础上提供 SSE 所需的同源认证读取能力，不把 token 放入 URL。
- `frontend/src/formal.css`、`frontend/src/formal/components/AppShell.tsx`：只增加正式诊断工作台状态和响应式样式。
- `frontend/tests/*`：覆盖状态恢复、观察表单、幂等键、revision 冲突、SSE 游标/去重/终态和迟到响应。

## 服务端接口与调用顺序

1. `GET /cases/{caseId}`：可信 `revision`、`graph_epoch`、`active_run`、`current_check` 与报告门禁。
2. `GET /cases/{caseId}/diagnosis`、`/diagnosis/areas`、`/observations`、`/reports`：读取当前图、区域、不可变观察及报告历史。
3. `POST /cases/{caseId}/diagnosis/runs`：仅在服务端快照允许且用户点击时，提交 `expected_revision`；幂等键由未变化动作草稿持有。
4. `GET /runs/{runId}/events`：同源 cookie 请求，使用 `Last-Event-ID`；每个新事件仅使相关 Query 失效并重新读取服务端事实。
5. `POST /cases/{caseId}/observations`：提交服务端当前步骤公布的 `step_id`、`graph_epoch`、输入种类、选项/测量/工况或无法测量原因。模型和前端不能提供身份或可信状态。
6. `POST /cases/{caseId}/diagnosis/areas/{areaId}/activate`：只对服务端返回的合格 pending 区域提供动作。
7. `POST /cases/{caseId}/observations/{observationId}/correct`：只对有效历史观察提供更正；原因必填；成功后重新读取 revision/epoch 与 stale 状态。
8. `POST /cases/{caseId}/reports`：用户显式请求。进度报告可在未收敛病例请求；最终报告仅在 `ReportGate.allowed=true` 时提供按钮，服务端仍再次门禁。
9. `GET /reports/{reportId}` 与依据 `source_content_url`：显示服务端当前有效性、历史状态和真实来源；失效、撤销、缺页或缺映射显示明确状态，不制造替代来源。

## 状态所有权与竞态

- Query 缓存保存病例、诊断、区域、观察、run 和报告事实；组件 state 只保存未提交表单、抽屉选择和展示选择。
- 工作台上下文代次绑定 `caseId + graph_epoch + runId`；区域展示选择额外绑定 `caseId + graph_epoch + areaId`，当前步骤所属区域优先，completed 区域只读切换不创建任务。路由、epoch 或 run 改变即中止旧 SSE/读取；旧回调必须同时通过代次和生命周期检查。
- SSE 按事件 id 去重；断线后先 GET run/病例快照，再携带最后事件 id 重连；snapshot 临时失败显示有限错误并按 0.5、1、2 秒直至最高 5 秒退避；恢复成功清除错误。`reset_required` 清空本地游标并全量重新读取；终态关闭连接。事件正文不直接写业务事实。
- 所有工作台写动作的幂等键绑定接口、case/run、目标 ID、revision、epoch 与规范化 body；超时/网络失败重试复用，同一可信上下文或表单内容变化生成新键，成功或明确 409 后清空。
- 409/旧 revision 先重新读取快照并保留未提交草稿，不自动把旧答案提交到新步骤。取消按钮只有服务端成功响应后才显示终态。

## 输入与输出

- choice：必须选择服务端 choices 中的索引，并提交所需工况。
- measurement：逐项提交服务端 measurements 中的 `spec_id`、数值、单位和工况；前端不自行判范围。
- composite：同时满足 choice、顶层 required conditions 和全部 measurement；数值必须是有限且受支持精度的十进制文本。
- unavailable：只提交非空原因；显示为未完成/待补。
- 当前检查显示标题、位置、前置工况、动作、输入和 interpretation；依据按引用打开 EvidenceView，显示版本、locator、hash/current_validity 与结构化 `source_access`。PDF 地址只由服务端按不可变版本和可信物理页生成；无页、映射缺失、needs_ocr 或无独立页图均显式显示。
- 区域卡与报告仅显示服务端 assessment/status；`unknown`、`stale`、`needs_review`、`draft` 保持原义。

## 错误与安全

统一客户端保留 401、409、413、422、结构化 `details` 和可复制 `trace_id`。SSE 与普通请求只使用同源 cookie；CSRF 仅内存持有；写请求必须带 Idempotency-Key。所有 owner、revision、epoch、权限、资料资格和 ReportPolicy 仍由服务端判定。页面不读取私有模型配置、费用账本或本地路径。

## 验证顺序

1. 生成 OpenAPI 并证明差异检查能覆盖新增响应模型。
2. 免费组件/状态测试：恢复路由、输入四类、幂等键、409、取消、SSE 去重/重连/reset/终态、报告门禁与 stale、跨 case/run/epoch 迟到保护。
3. 后端只运行新增响应契约与直接受影响接口测试；不机械重跑约 41 分钟全后端入口。
4. `typecheck`、`api:check`、独立 production build；复跑 WP-14 正式前端及预览兼容测试。
5. 新隔离数据库、storage、cookie、API 和 worker 执行确定性 E2E：启动、发布检查、观察提交、下一任务、刷新恢复、进度报告、最终报告拒绝、更正 stale。
6. 仅在免费 E2E 全部通过后，才允许一个有界真实 DeepSeek 业务链；沿用 v2 账本持续计量和每 turn 门禁，不以失败循环重试。

## 完成标准

U508—U514 逐项有命令、退出码、版本和证据；正式页面不出现未来能力假按钮；5180/5196 未操作；暂存业务内容稳定；STATUS 仅将 WP-15 记为 `IMPLEMENTED_NOT_ACCEPTED`，或在关键链路未完成时明确 `BLOCKED`。完成后停止，等待集中审核。
