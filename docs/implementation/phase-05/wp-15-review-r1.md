# WP-15 集中审核 r1

日期：2026-09-21  
审核范围：正式诊断工作台及合成技术范围  
结论：`CHANGES_REQUIRED`

## 1. 审核声明与基准

本轮只审核 WP-15，没有修改业务实现、正式测试、`STATUS.md`、接受记录或历史证据，没有启动 WP-16，也没有操作 5180/5196 或发起付费模型调用。审核夹具及输出只写入 `evidence/wp-15-review-r1/`。本任务链此前参与过实施和整改，因此本报告不声称组织上或任务上的独立审核。

当前交付与执行者封存基准一致：`delivery-hashes.json` 的 25 个交付文件逐一匹配，delivery 清单 SHA-256 与 `seal.json` 相同；`GIT_OPTIONAL_LOCKS=0 git ls-files --stage` 与 `git diff --cached --binary` 的规范化 SHA-256 分别为 `e146135d...a4ea`、`dcbc0d1d...ad2b`，与实施前稳定基准一致。未发现封存交付文件或暂存业务内容的未解释变化。详见 `baseline-verification.json`。本轮新增审核报告、审核证据、独立构建目录和隔离测试目录属于已解释审核产物，不纳入原交付结论。

执行者历史证据与本轮证据严格区分：执行者的真实链路、三视口和 33 项前端结果来自 `evidence/wp-15/`；本轮亲自运行正式前端、兼容测试、后端定点、报告路径以及 6 个高风险反例。未重跑约 40 分钟后端完整入口。

## 2. 架构与边界

正式工作台复用了 WP-11—13 的病例、图、观察、区域、任务、证据与报告 API；没有发现第二套诊断后端、前端硬编码下一检查或本地推断结论。WP-15 的后端生产改动限于响应模型/OpenAPI和观察历史只读字段，未发现放宽 ProposalService、规格、资料资格、结论或 ReportPolicy 的差异。正式类型来自 `frontend/src/generated/api-schema.ts`，正式页面没有导入预览手写 `api-schema.ts`。`api:check` exit 0。

`unknown` 在区域卡中明确显示为待补，真实链路也只证明“首项检查 → 保存观察 → 保守 unknown 区域卡 → 刷新读回”；没有把续轮写成第二项当前检查、确诊、排除或最终报告完成。该边界通过代码、`live-sanitized.json` 和执行者截图保持成立。

## 3. 必须整改项

### ISSUE-001（P1）：已完成区域不可选择，活跃任务期间仍可能显示区域激活按钮

**触发**：病例有两个 completed 区域，且当前没有待答步骤。点击第二个区域标题。实际页面没有可点击或可聚焦的 completed 区域控件，也没有保存用户区域选择；中栏固定取 `currentArea`，否则取 `areaItems.find(status === completed)`，因此只能显示第一个 completed 卡。另在 `activeRunId` 存在但 `currentAreaId` 为空时，pending 区域仍显示“生成本区域检查”。

**位置**：`frontend/src/formal/diagnosis/WorkbenchParts.tsx:13-23`；`frontend/src/formal/pages/WorkbenchPage.tsx:49-58`。

**证据**：审核夹具 `completed areas expose no selection control` 通过，证明两个 completed treeitem 均无按钮、键盘焦点或选择回调。源码中没有 `selectedAreaId`。这违反 WP-15 契约的本地“展示选择”边界和 U508 的多区域摘要浏览要求。

**影响**：用户无法查看指定已完成区域的卡；页面可能把第一个完成区域误呈现为当前选择；活跃任务期间显示可激活动作，点击后只会依赖服务端拒绝，且超时后没有可靠恢复路径。

**最小整改**：增加按 `caseId + graph_epoch` 绑定的只读区域选择；completed/current 区域须可点击和键盘操作，切换只更新展示状态、不创建 run；pending 激活按钮同时受当前步骤和活跃任务约束；激活响应按 case/epoch/area/请求代次守卫。定点复核 completed A/B 切换、active run、409、超时及 ABA 迟到响应。

### ISSUE-002（P1）：composite 观察确认了必需工况，但请求体丢失顶层 `conditions`

**触发**：当前步骤 `input.kind=composite`，同时包含 choice、measurement 和服务端 `required_conditions={engine: off}`。用户完成选择、数值并勾选工况后提交。

**位置**：`frontend/src/formal/diagnosis/WorkbenchParts.tsx:59-70`。第 63 行要求确认工况，但第 68 行只为 `choice` 写入顶层 `conditions`。后端 `backend/app/services/observation_service.py:229-232` 对 bounded choice 的工况执行硬校验。

**证据**：审核夹具 `composite observation drops confirmed required conditions from the actual request body` 直接检查 `apiClient.request` 的生产组件请求体，实际 `kind=composite` 且 `conditions` 为 `undefined`。

**影响**：合法 composite 步骤在服务端返回 `CONDITIONS_MISMATCH`，四类观察输入并未全部联通，U510 核心路径失败。

**最小整改**：choice 与 composite 在存在服务端 `required_conditions` 且用户确认后都提交同一顶层工况；measurement 子项继续使用各自已发布条件。补真实 HTTP 正例以及缺确认、篡改工况、错单位、空值、NaN/Infinity 反例。

### ISSUE-003（P1）：部分写操作没有在歧义失败后复用同一幂等键，报告可重复创建

**触发与结果**：

- 进度报告首个请求已提交且 worker 已完成，客户端响应丢失；用户重试。`FinalAdvice` 每次 mutation 现场生成新键。真实 HTTP/PostgreSQL/worker 反例得到两个不同 `report_id`、两个不同 report run、数据库两条报告记录。
- activate、cancel 同样每次调用现场生成新键。服务端状态门禁能减少部分重复副作用，但无法向歧义重试返回原响应；不能用 `isPending` 证明网络超时重试安全。
- 更正键只绑定 `{correctionReason, choice, unavailableReason, values}`。409 后 revision 更新而草稿未变时，请求体变化但旧键复用，服务端会返回 `IDEMPOTENCY_CONFLICT`，用户必须无意义修改字段才能继续。

**位置**：`frontend/src/formal/pages/WorkbenchPage.tsx:38-39`；`frontend/src/formal/diagnosis/WorkbenchParts.tsx:121-133,162,166-170`；服务端报告创建在 `backend/app/services/report_service.py:56-86`。

**证据**：前端审核夹具确认 report 重试键不同、correction 跨 revision 请求体变化但键相同；后端审核反例 `test_progress_report_ambiguous_retry_with_new_key_duplicates` 在隔离库证明真实重复报告。开始诊断与普通观察的稳定键路径通过，问题不扩展到这两项。

**影响**：可产生重复报告和重复任务；更正可能在合法刷新后永久冲突；activate/cancel 的歧义结果不能可靠恢复。违反本包“所有写操作”的幂等重试要求。

**最小整改**：为 activate、cancel、progress/final report 建立按规范化请求内容持有的稳定键，成功或明确终态后才清除；correction 指纹必须包含 case、observation、step、revision、epoch 以及规范化 body。409 刷新后不得自动发送旧草稿到新上下文。复核每个写操作的提交后超时、同内容重试、改内容新键和数据库行数。

### ISSUE-004（P1）：SSE 断线后的 snapshot 读取失败会终止恢复链

**触发**：SSE 流关闭或失败，随后 `onDisconnect()` 的 run/case snapshot GET 也暂时失败。

**位置**：`frontend/src/formal/diagnosis/run-events.ts:38-91`，尤其第 82 行的 `await options.onDisconnect()` 位于捕获区外；`WorkbenchParts.tsx:156-159` 以 `void consumeRunEvents(...)` 启动且没有捕获拒绝或显示恢复错误。

**证据**：审核夹具 `an SSE snapshot recovery failure terminates the consumer instead of continuing recovery` 得到 promise rejection，fetch 只调用一次。正式测试覆盖了“snapshot 成功”的重连、去重、reset 和终态，没有覆盖该分支。

**影响**：短暂同时失去 SSE 与 snapshot 时，页面停止恢复且没有可见错误；之后服务端进入 waiting_input/succeeded/failed 也不会自动回到数据库事实。U509 失败。

**最小整改**：将 snapshot 恢复错误纳入同一受控循环和页面状态，采用有界退避，保证 case/run/epoch 或生命周期变化立即终止；当前上下文错误需可见且可重试。复核 snapshot 首次失败后恢复、持续失败的有界频率、终态、reset、ABA 和卸载。

### ISSUE-005（P2）：正式证据接口没有把 PDF 物理页绑定到实际打开地址

**触发**：证据 locator 指向旧 PDF 的物理第 7 页。正式 Drawer 使用后端 `source_content_url` 打开来源。

**位置**：`backend/app/services/evidence_service.py:103-110` 始终生成不带 `page` 的版本内容 URL；`backend/app/api/documents.py:129-137` 支持 `page` 查询；`frontend/src/formal/diagnosis/WorkbenchParts.tsx:94-100` 直接使用该 URL。正式前端测试 `frontend/tests/wp15-workbench.test.tsx:61` 手工模拟了 `?page=7`，但该值并非当前 EvidenceService 实际输出。

**证据**：源码和 OpenAPI 路径核对；当前真实 Markdown 内容读取通过，历史 DKVB 专题封存证明后端另有正确 PDF 页/页图映射能力，但 WP-15 正式 EvidenceView 没有接到该页映射。执行者本轮浏览器也只打开合成 Markdown 当前版本。

**影响**：用户点击 PDF 引用只能得到整份附件，不能保证打开正确物理页或完整页图；needs_ocr、缺页图或映射缺失也无法在 Drawer 中按正式接口准确区分。U512 不能通过。

**最小整改**：由服务端根据已保存 evidence 的不可变 locator/version 生成明确的 PDF 页或页图授权 URL，或返回结构化缺项；不得由前端猜页、回退 latest 或第一页。补旧版本、撤销版、正确页、无页图、needs_ocr、映射缺失和引用切换迟到反例，并至少一次真实 HTTP/浏览器定位。

### ISSUE-006（P2）：报告请求的 run 状态没有进入工作台恢复链

**触发**：点击生成进度报告，服务端返回 `run_id/report_id` 后 worker 异步执行。

**位置**：`frontend/src/formal/diagnosis/WorkbenchParts.tsx:166-174`。成功回调只立即 invalidate 一次报告列表，返回的 `run_id` 被丢弃；组件没有 RunStatus、SSE、轮询或完成后再次读取。

**证据**：代码审查与正式报告组件测试。后端定点证明报告 worker、最终门禁、更正后 stale 正常；缺口位于正式页面的异步状态接线。

**影响**：首次 invalidate 发生在报告仍为 draft 时，任务随后完成不会触发列表刷新；用户可能一直看到 draft 或看不到完成内容，直到手工刷新整页。报告错误和终态也没有任务级反馈。

**最小整改**：保留返回的 report run，并复用 RunStatus/SSE 或有界 snapshot 重新读取；终态后刷新 report list 和 gate，失败显示结构化错误。配合 ISSUE-003 使用稳定幂等键；复核 progress 成功/失败、final 409、完成内容、stale 历史和刷新恢复。

## 4. U508—U514

| 项 | 结论 | 审核依据 |
| --- | --- | --- |
| U508 即时区域摘要 | **FAIL** | 服务端卡可即时读取且 unknown 语义正确，但用户不能选择不同 completed 区域；见 ISSUE-001。 |
| U509 SSE 恢复 | **FAIL** | 去重、Last-Event-ID、reset、终态和旧上下文测试通过；snapshot 恢复失败会终止消费器；见 ISSUE-004。 |
| U510 数值及双击 | **FAIL** | choice、measurement、unavailable 及普通观察稳定键已有覆盖；composite 丢工况，且部分写操作歧义重试不安全；见 ISSUE-002/003。 |
| U511 固定观察/报告布局 | **PASS（布局限定）** | 观察、区域与报告均在正式三栏，无临时弹窗；报告异步任务反馈仍须按 ISSUE-006 整改。 |
| U512 证据定位 | **FAIL** | Markdown 当前/旧版及撤销有效性路径有证据；正式 EvidenceView 未动态绑定 PDF 物理页/页图；见 ISSUE-005。 |
| U513 响应式 | **PASS（执行者封存证据限定）** | 1440×900、1024×768、390×844 无关键横向溢出；截图与 `browser-verification.json` 已核对。本轮未重启浏览器实例重复三视口。 |
| U514 真实链路 | **PASS（已发生结果限定）** | 脱敏证据证明浏览器→API→PostgreSQL→worker→只读 MCP→DeepSeek→服务端校验；只接受首项检查、保存观察、unknown 卡和刷新读回。续轮未发布第二项检查。 |

## 5. 本轮命令与结果

| 命令/检查 | 结果 | 证据 |
| --- | --- | --- |
| seal、25 个 delivery hash、稳定 Git 暂存内容核对 | exit 0，全部匹配 | `baseline-verification.json`、`git-ls-files.txt`、`git-diff-cached.patch` |
| `npm run test:wp14` | exit 0，6 files / 33 tests passed | `frontend-wp15-wp14-tests.log` |
| 三个 preview Node 入口 | exit 0，2 + 12 + 10 = 24 passed | `preview-check-node.log`、`preview-material-intake.log`、`preview-context.log`；其中业务状态 22 项，完整兼容入口另含运行时 2 项 |
| `npm run typecheck` | exit 0 | `typecheck.log` |
| `npm run api:check` | exit 0 | `api-check.log` |
| 独立 Vite production build | exit 0，105 modules | `build-wp14-audit.log` |
| WP-15 后端定点 | exit 0，4 passed | `backend-targeted.log`；当前 pytest 收集数为 4，执行者历史报告中的 3 是其当时统计，不混写 |
| 进度报告→worker→更正→stale 定点 | exit 0，1 passed | `report-correction-stale-targeted.log` |
| 相关 Python Ruff | 首次因审核命令写错不存在的文件名 exit 1；纠正为现有 `evidence_service.py` 后 exit 0 | `ruff.log`、`ruff-final.log` |
| 审核前端反例 | 最终 exit 0，5 项均复现预期缺陷 | `test_audit_wp15.test.tsx`；此前 include/config/React 导入三次夹具错误已保留，不算业务失败 |
| 报告不同键重试真实反例 | 两次夹具依赖错误、一次“首任务仍活跃时服务端 409”后，最终在首任务完成场景 exit 0，证明两条报告/两条 run | `audit-backend-counterexample-final3.log`，先前失败日志均保留 |

隔离后端使用全新数据库 `xiutu_test_wp15r1_a7bb2cd1`、独立 storage 和临时目录。数据库创建首次错误使用了不符合项目策略的 `postgres` 管理目标，随后按既有 `xiutu_dev` 策略创建；Alembic 首次误指不存在配置，纠正到根目录配置后继续。所有原始失败均保留，没有删除或改写为成功。未启动 5180/5196 或任何用户实例。

## 6. 非阻断建议与未验证范围

- SSE 目前固定约 500ms 重连；在修复 ISSUE-004 时可加入上限和退避，避免持续故障下的高频请求，但无需扩建遥测平台。
- unavailable 更正的空白原因目前主要依赖服务端 422；可以前端提前禁用以改善体验，但服务端门禁仍在，本项不单独阻断。
- 本轮没有验证生产部署、真实资料、真实维修效果、负载、备份恢复或真实最终报告语义；真实资料仍 `NOT_MET`。
- 真实续轮没有第二项当前检查；unknown 不是确诊、排除或最终报告就绪。
- 正式前端尚未部署到 5180/5196；WP-16/17 未开始。

## 7. 结论与建议接受范围

结论：**CHANGES_REQUIRED**。

WP-15 的基础路由、三栏布局、OpenAPI 类型、病例/诊断/观察读取、服务端门禁、确定性后端路径和限定真实链路均有有效证据；但 U508、U509、U510、U512 存在可复现核心缺陷，报告请求还缺少稳定重试与任务终态接线。当前不建议记录 WP-15 接受。

建议只整改 ISSUE-001—006 并进行定点复核：区域选择/激活状态、composite 工况、所有写操作的稳定幂等上下文、SSE snapshot 失败恢复、PDF 物理页/页图定位、报告 run 状态。无需重开 WP-14、重做模型评测、重复付费调用或启动 WP-16。
