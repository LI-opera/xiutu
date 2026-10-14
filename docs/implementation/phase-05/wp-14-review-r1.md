# WP-14 集中限定审核 r1

时间：2026-09-21（Asia/Shanghai）  
结论：**CHANGES_REQUIRED**  
审核范围：正式前端外壳、资料中心、病例入口、历史主动选择及预览兼容；不含 WP-15 诊断联调，不代表真实资料门槛或真实维修效果通过。

## 1. 基准与流程披露

审核读取了 [STATUS](../STATUS.md)、[契约](wp-14-contract.md)、[实施结果](wp-14-result.md)、[执行者验证摘要](evidence/wp-14/verification-summary.md)、[前端运行说明](../../runbooks/frontend.md)、[API说明](../../api/wp-14-frontend.md)，并核对 WP-13、资料预览、资料接入、DKVB 专题和诊断切片的限定接受记录。

- `delivery-hashes.json` 所列 **37/37** 个交付文件 SHA-256 与当前文件一致。
- `seal.json` 所列 **12/12** 个历史证据文件 SHA-256 一致，没有覆盖执行者日志。
- 本轮没有执行 `git add/reset/commit`，没有改变暂存条目的业务内容，也没有把审核证据加入 index。但审核开始后的 `git status --short` 刷新了 Git index 的 stat-cache，导致 `.git/index` 原始文件 SHA-256 从封存的 `c451d6e7…` 变为 `3984f041…`。这是本审核造成且已解释的索引元数据字节变化；37个交付文件仍完全匹配封存版本，审核没有把变化后的业务实现纳入结论。见 [protection-final.json](evidence/wp-14-review-r1/protection-final.json)。这项流程偏差不应被表述为“Git index 原始字节未变”。
- 本审核任务属于同一任务链，参与过此前实施、整改和复核，**不声称不同任务独立审核**。

## 2. 总体判断

正式路由、生成类型、统一 API client、资料单页流程、病例创建/刷新、主动历史搜索、响应式布局和旧预览入口均有当前版本证据。两个新增反例揭示必须整改的问题：服务端提供的分页游标没有被正式页面消费；资料切换后，旧资料的迟到检索成功仍可写入当前页面。前者使资料、切块和历史病例在超过首个 limit 后不可达，后者可能把 A 资料的命中展示在 B 资料上下文。

因此 WP-14 当前不满足限定 `REVIEW_PASS`。整改只需集中在正式页面的分页和检索上下文保护，不需要修改后端分页协议、资料资格算法或开始 WP-15。

## 3. 必须整改项

### ISSUE-001（P1）正式页面忽略分页游标，静默隐藏后续资料、切块和病例

**触发与实际结果**

1. `/documents?limit=50` 返回 50 项且 `next_cursor` 非空时，页面只渲染首 50 项，没有加载下一页入口。
2. 版本切块接口返回 100 项且 `next_cursor` 非空时，页面只渲染首 100 项。
3. `/cases?limit=50` 首页面不含搜索目标、`next_cursor` 非空且目标在第二页时，历史页直接显示“没有匹配病例，可调整关键词”，没有读取或提供后续页。

本轮四项业务反例中的前三项均按上述方式失败，见 [audit-counterexamples-business.txt](evidence/wp-14-review-r1/audit-counterexamples-business.txt)。服务端已实现 owner 绑定的游标：`documents.py:70-93`、`cases.py:113-116`、`document_service.py:202-237,308-330`、`case_service.py:148-155`；缺口在正式前端：

- `frontend/src/formal/pages/DocumentsPage.tsx:27` 固定请求首 50 项，`:100` 仅渲染该页；
- `frontend/src/formal/pages/DocumentsPage.tsx:37-40` 固定请求首 100 个切块，`:124` 仅渲染该页；
- `frontend/src/formal/pages/HistoryPage.tsx:15` 固定请求首 50 个病例，`:19` 只在该页过滤，`:26` 在仍有下一页时给出错误的无匹配结论。

**影响**

正式资料中心和历史恢复无法保证数据完整可达；病例仍存在时可能被错误描述为不存在。搜索关键词不能替代游标读取，因为当前病例接口不接受服务端全文搜索条件。

**最小整改要求**

使用 `useInfiniteQuery` 或显式游标状态消费 `next_cursor`，按稳定 key 去重追加；资料、切块和历史均提供明确的继续加载行为。历史搜索在尚未遍历的页可能含目标时，不得声称“没有匹配病例”。加入大于 50 个资料/病例和大于 100 个切块的组件反例；无需新增服务端全文搜索。

### ISSUE-002（P1）切换资料后，旧检索迟到成功可污染当前资料上下文

**触发与实际结果**

在资料 A 上启动 `/evidence/search`，请求挂起；切换到资料 B 后释放 A 的成功响应。页面重新出现 `A-ONLY-LATE-RESULT`。对应反例见 [test_audit_wp14.test.tsx](evidence/wp-14-review-r1/test_audit_wp14.test.tsx) 和 [audit-counterexamples-business.txt](evidence/wp-14-review-r1/audit-counterexamples-business.txt)。

代码中 `frontend/src/formal/pages/DocumentsPage.tsx:70-76` 使用不带上下文身份的 mutation，并在 `onSuccess` 无条件调用 `setSearchResult`；`:91-94` 切换时只清除当前值，不能阻止已经在途的 A 请求后来重新写入。

**影响**

用户可能在 B 资料的版本、切块和审核状态旁看到 A 资料检索命中，破坏证据与资料版本的对应关系。该问题不构成后端 owner 越权，但属于正式证据页面的上下文错误。

**最小整改要求**

检索发起时绑定 `{documentId, versionId}` 及上下文代次，或使用可取消并按 query key 隔离的请求；成功和错误回调均须核对请求发起时的上下文及组件生命周期。覆盖 A→B、A→B→A、迟到成功/错误和同上下文正常完成；不得通过清空用户输入或统一吞掉当前错误规避。

## 4. 分项审核结论

| 项目 | 结论 | 当前证据与边界 |
| --- | --- | --- |
| 正式路由与状态所有权 | **PASS（受 ISSUE-002 限制）** | `/documents`、`/history`、无 id `/workbench` 可直达和刷新；`/workbench/:caseId` 实际刷新读回同一 case。无 id 不恢复最近病例。病例事实来自 TanStack Query，未发现 localStorage 业务副本。检索 mutation 的上下文保护失败。 |
| OpenAPI 与类型 | **PASS** | `formal/types.ts:1` 仅从 `generated/api-schema.ts` 派生；正式目录未导入旧预览 `api-schema.ts`。`api:check` exit 0，生成文件前后 hash 一致。临时副本的 OpenAPI 和生成类型各自注入漂移后均 exit 1，证明差异检查会失败。真实 case 快照字段见 [real-case-snapshot-sanitized.json](evidence/wp-14-review-r1/real-case-snapshot-sanitized.json)。 |
| 统一 API client | **PASS** | 源码及15项正式前端测试覆盖 cookie、内存 CSRF、幂等键、AbortSignal、15秒默认超时、401会话失效、409/413/422和非 JSON 错误。浏览器实际 422 显示中文错误、trace_id 和复制入口，原资料与检索结果保留。 |
| 资料中心真实边界 | **PASS（受 ISSUE-001/002 限制）** | 独立浏览器真实完成 Markdown 上传、解析、人审、索引、原文/3个切块和 E5 试搜；持续显示 synthetic、formal_usable=false 与适配 unknown。服务端上限显示为25.00 MiB，错误输入未替换原资料。单页流程成立，跨页完整性与检索切换不成立。 |
| 分页完整性 | **FAIL** | 资料、切块、病例三类 `next_cursor` 均未消费，三个定点反例失败。 |
| 工作台边界 | **PASS** | 真实 API 保存 model/year/engine_family/engine_code/fault code；刷新读回同一快照。`current_check=null`、`active_run=null`、`report_gate=FINAL_NOT_READY/NO_EFFECTIVE_AREA` 与页面一致；没有诊断启动、观察、切区或报告按钮，unknown 未提升。 |
| 兼容与浏览器 | **PASS（限定当前单页数据量）** | 24项预览状态测试通过。1440×900、1024×768、390×844 实测无横向溢出或关键遮挡；移动端导航和键盘焦点可见；控制台无 error/warning。截图在本轮浏览器轨迹，摘要见 [browser-summary.md](evidence/wp-14-review-r1/browser-summary.md)。未重审预览历史业务能力。 |

## 5. 验证记录

| 命令/检查 | 结果 |
| --- | --- |
| `npm.cmd run test:wp14` | exit 0，4 files / **15 passed** |
| `node --test scripts/check-node.test.mjs scripts/material-intake.test.mjs scripts/preview-context.test.mjs` | exit 0，**24 passed** |
| `npm.cmd run typecheck` | exit 0 |
| `npm.cmd run api:check` | exit 0；OpenAPI 与生成类型当前一致 |
| OpenAPI exporter 临时副本 current/drift | current 0，注入漂移 1 |
| openapi-typescript 临时副本 generate/drift | generate 0，注入漂移非零 |
| `npm.cmd run build:wp14 -- --outDir E:\Work\xiutu-v5\.local-data\wp14-review-r1-build` | exit 0，102 modules；未覆盖 `frontend/dist` |
| 审核反例最终版 | exit 1，**4 failed / 4**，均为上述真实功能缺口 |
| 独立浏览器 | 真实 API/worker/Vite，端口5224/8224；三个视口及真实上传、索引、检索、病例刷新均完成；审核实例已停止 |

反例夹具的前两次准备分别因审核配置解析路径和测试缺少 React 导入而失败，没有进入最终业务结论；原日志 [audit-counterexamples.txt](evidence/wp-14-review-r1/audit-counterexamples.txt) 与 [audit-counterexamples-final.txt](evidence/wp-14-review-r1/audit-counterexamples-final.txt) 保留。第三次固定夹具后四个业务反例稳定失败，没有修改产品断言或实现。

## 6. 非阻断保留项与未验证范围

- 真实资料仍 `NOT_MET`；本轮上传是明确合成 Markdown，不能证明真实维修资料或实际维修效果。
- 分片上传、OCR、超限整书和正式真实资料审核平台不在 WP-14。
- WP-15 的诊断启动、SSE、观察提交、区域切换及报告交互未实施；本审核没有要求假按钮。
- 没有运行约41分钟全后端入口，没有调用付费模型，没有操作或部署到5180/5196。
- 本轮没有第二环境和真实用户大数据量浏览器验证；分页缺陷已用服务器真实响应形状的免费组件反例证明，不需要以大量数据库造数重复触发。

## 7. 建议接受范围

当前结论为 **CHANGES_REQUIRED**，不建议记录接受。完成 ISSUE-001 和 ISSUE-002 的定点整改后，可仅复核：三类游标、历史无匹配文案、A→B/ABA迟到成功与错误、同上下文正常检索，并复跑15项正式前端测试、typecheck、api:check和独立构建。无需重开 WP-00—13、重跑全后端或进入 WP-15。
