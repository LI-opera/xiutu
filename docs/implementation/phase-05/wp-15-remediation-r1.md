# WP-15 r1 六项问题整改记录

日期：2026-09-21  
状态：`IMPLEMENTED_NOT_ACCEPTED`  
范围：只整改 `wp-15-review-r1.md` 的 ISSUE-001—006；未进入 WP-16，未付费调用，未操作 5180/5196。

## 基准与保护

整改前读取并固定 WP-15 契约、结果、r1 审核、审核反例、STATUS、正式工作台、Evidence/Observation/Report 服务以及生成 OpenAPI。r1 报告与 `evidence/wp-15-review-r1` 未修改。稳定暂存内容指纹在整改前后均为：

- `git ls-files --stage` 规范化 SHA-256：`e146135dd7084735f6b331b6ed1a3ac32938bf971f8705cf9e75e1dccb49a4ea`
- `git diff --cached --binary` 规范化 SHA-256：`dcbc0d1d7c2c1dd026a8106372d8beb6a9f5f38ac7dc10342ee3a4328389ad2b`

见 `evidence/wp-15-remediation-r1/git-content-fingerprint.json`。未执行 git add/reset/checkout/commit/stash/push。5180/5196 未启动、停止或更新；本轮 5225/8225 隔离进程均已停止，最终监听数为 0。

## ISSUE-001：区域选择与激活状态

`WorkbenchPage` 新增绑定 `caseId + graph_epoch + areaId` 的展示选择。case/epoch 变化清空旧选择；当前步骤区域优先；没有当前步骤时保留仍存在的 completed/current 选择并提供合理回退。`AreaTree` 的 completed/current 项改为可点击、可键盘聚焦并带 `aria-selected/aria-pressed` 的只读展示控件，切换不会创建 run。

pending 激活按钮同时要求无当前步骤和无 queued/running/cancel_requested 任务。激活动作指纹包含接口、case、area、revision、epoch 和 body；歧义失败保留键，成功或明确 409 清理。回调还核对请求代次与当前 case/epoch，旧 A→B→A 响应不能改变新选择。

正式测试覆盖 completed 选择和活跃状态门禁。服务端可激活性、revision/epoch 和单活跃任务仍由原 API 最终判定，未复制区域算法。

## ISSUE-002：composite 工况与数值

`ObservationForm` 对 choice 与 composite 都在用户确认后提交服务端原样发布的顶层 `required_conditions`；composite 同时保留 `choice_index` 和每一项 measurement 的 `spec_id/unit/conditions`。前端只接受有限、受支持精度的十进制文本，空值、NaN、Infinity 和非法文本不能提交；更正表单使用相同数值门禁。unavailable 仍是独立请求体。

全新 PostgreSQL 中的真实 HTTP 反例证明：缺顶层工况返回 422；合法 composite 返回 202；数据库只保存一条合法观察，并同时保存顶层及 measurement 工况。测试候选通过原 WP-10 ProposalService 和已批准规格，没有绕开规格或证据门禁。前端反例覆盖 NaN 禁用和合法 `4.2` 请求体。

## ISSUE-003：稳定幂等键

开始诊断、区域激活、观察提交、更正、取消任务、进度报告和最终报告现在都按实际请求上下文持有稳定键：接口与动作类型、case/run、area/observation/step、revision、epoch 和规范化 body。未知结果保留键；成功或明确 409 后清理；上下文或 body 变化生成新键。组件卸载后 ref 生命周期结束，不会把旧 case 的键带到新实例。

r1 的“不同新键可创建两条报告”数据库反例保持原样，说明服务端把不同键视为不同用户动作。整改后的前端歧义重试复用同键；原 WP-13 同键 HTTP/PostgreSQL 回归确认只产生一个 report/run，并在 worker 完成后仍为同一报告。revision 变化会进入 correction 新指纹，旧草稿不会自动提交。

## ISSUE-004：SSE snapshot 恢复

`consumeRunEvents` 将 `onDisconnect` 的失败纳入循环：首次失败通过 `onRecoveryError` 显示，保留现有 cursor 和业务状态；按 0.5 秒起步的指数退避、最高 5 秒继续；snapshot 成功后清除错误；terminal snapshot 停止。AbortSignal、上下文变化和卸载立即结束。`RunStatus` 顶层捕获最终异常，并在 case/epoch/run 变化时清理旧恢复错误和取消键。

正式测试覆盖首次 snapshot 失败、第二次恢复并继续到 `waiting_input`；既有事件去重、Last-Event-ID、reset_required、终态和旧上下文停止测试继续通过。没有增加遥测平台。

## ISSUE-005：PDF 物理页及页图状态

EvidenceView 新增严格 `source_access`：`kind/status/page/page_count/needs_ocr/content_url/page_image_url/page_image_status`。EvidenceService 只从不可变 evidence 的 `document_version_id`、`locator.document_id` 和保存的 source locator 生成地址：

- Markdown/text 返回绑定版本原文；
- PDF 有可信页时返回绑定版本 `?page=N#page=N`；
- 页缺失、页越界/映射缺失、needs_ocr 分开标识；
- 通用正式接口没有独立页图时明确 `page_image_status=unavailable`，不伪造成功；
- 不回退 latest 或默认第一页，撤销仅改变 current_validity，不删历史定位。

OpenAPI 和生成类型已同步。Drawer 依结构化状态显示正确入口或缺项，不从文本猜页码。真实 HTTP/PostgreSQL 测试上传两页合成 PDF、解析/审核/索引/检索并绑定第 2 物理页，再为同 document 上传 v2；历史 evidence 仍返回 v1、第 2 页和原 hash/locator 关系。浏览器隔离会话成功登录并恢复病例，但 Chrome 自动化客户端对 PDF response 返回 `ERR_BLOCKED_BY_CLIENT`；该项没有写成浏览器打开成功。实际授权 PDF bytes 与页映射由真实 HTTP 测试证明，浏览器 PDF 插件行为留待 r2 环境复核。

## ISSUE-006：报告 run 恢复

报告 POST 的 `run_id` 被保存并交给独立 `RunStatus`；进度与最终报告共用稳定键策略。SSE/快照事件会重新读取 report list、report gate 和 case snapshot，终态后显示服务端报告内容；run snapshot 的结构化失败由统一 ErrorState 显示。刷新时，从报告列表中恢复仍为 draft 且带 `run_id` 的任务。诊断 run 和报告 run 分别渲染，不相互覆盖。

final gate=false 时按钮禁用；服务端 409 仍是最终门禁并清理该明确失败动作键。观察更正后的 stale 报告继续可读。`unknown` 不启用最终报告。

## 验证结果

| 验证 | 结果 | 证据 |
| --- | --- | --- |
| 正式前端最终测试 | exit 0，6 files / 37 passed | `frontend-tests-final.log` |
| 预览兼容业务状态 | exit 0，22 passed | `preview-compat.log` |
| Node 运行时兼容 | exit 0，2 passed；合计完整兼容入口 24 项 | `preview-runtime.log` |
| typecheck | exit 0 | `typecheck-final.log` |
| OpenAPI 漂移检查 | exit 0 | `api-check-final.log` |
| 独立 production build | exit 0，105 modules | `build-final.log` |
| 最终后端定点 | exit 0，8 passed | `backend-targeted-final.log`、`backend-run-final.json` |
| Python Ruff | exit 0 | `ruff.log` |
| 浏览器隔离实例 | 登录及工作台恢复成功；PDF 导航被自动化客户端阻止 | `browser-verification.json`、`browser-ports-final.json` |

后端 8 项包括 OpenAPI 严格响应、WP-15 确定性工作台、PDF 旧版本物理页、composite HTTP 正反例，以及报告同键重放/worker/stale。全部使用新隔离 PostgreSQL、storage 和测试身份。失败历史未删除，见 `failure-history.json`；其中多次 composite 首轮失败来自测试候选没有满足原 WP-10 结构/语义/来源门禁，最终通过调整合成夹具而非放宽生产门禁。

没有重跑约 40 分钟后端完整入口。U514 继续引用 r1 已核实的真实 DeepSeek 链路，没有新付费调用。

## 当前限制与停止点

- 浏览器自动化环境未能由 PDF 插件实际渲染第 2 页；产品服务端地址、授权响应和不可变版本/页关系已经真实 HTTP 验证，r2 可在支持 PDF 插件的独立浏览器复核。
- 通用正式 Evidence API 当前不提供独立 PDF 页图，明确返回 unavailable；没有实施 OCR。
- 真实资料仍 `NOT_MET`；真实续轮仍没有第二项当前检查；unknown 不是确诊、排除或最终报告就绪。
- 未验证真实最终报告语义、生产部署、生产恢复或真实维修效果。

WP-15 保持 `IMPLEMENTED_NOT_ACCEPTED`。本记录是执行者整改与自测，不是审核关闭、`REVIEW_PASS` 或用户接受。下一步只等待 ISSUE-001—006 定点 r2 复核。
