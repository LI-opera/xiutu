# WP-15 定点复核 r2

日期：2026-09-21  
范围：仅复核 `wp-15-review-r1.md` 的 ISSUE-001—006  
结论：`REVIEW_PASS`（限定正式诊断工作台及合成技术范围）

## 1. 审核声明与固定基准

本轮没有修改业务实现、正式测试、`STATUS.md`、接受记录或历史报告，没有进入 WP-16，没有调用付费模型，也没有操作 5180/5196。新增内容仅为本报告及 `evidence/wp-15-review-r2/` 下的审核夹具、日志和截图。本任务链参与过此前实施、整改与审核，因此不声称任务或组织上的独立审核。

整改封存的 46 个文件逐一重新计算 SHA-256，全部与 `evidence/wp-15-remediation-r1/delivery-hashes.json` 匹配。r1 审核证据目录中 31 个原始文件与其 `evidence-hashes.json` 全部匹配，r1 报告和失败反例没有被覆盖。整改范围外未发现未解释的生产变化。

Git 保护采用稳定内容输出，不采用 `.git/index` 原始文件哈希。审核前后 `GIT_OPTIONAL_LOCKS=0 git ls-files --stage` 的规范化 SHA-256 均为 `e146135dd7084735f6b331b6ed1a3ac32938bf971f8705cf9e75e1dccb49a4ea`，`git diff --cached --binary` 均为 `dcbc0d1d7c2c1dd026a8106372d8beb6a9f5f38ac7dc10342ee3a4328389ad2b`，与整改前基准一致。见 `baseline-verification.json`、`final-protection.json` 及前后 Git 文本输出。

r1 原前端反例保持原内容运行，exit 1、5 项旧断言全部失败。这是预期的闭环证据：已完成区域现在有选择按钮、composite 请求带顶层工况、报告歧义重试复用原键、更正 revision 变化生成新键、SSE snapshot 暂时失败不再令 consumer reject。r1 后端“不同新键创建两份报告”的反例仍 exit 0，证明服务端继续把不同键视为不同用户动作；当前同键重放另由 WP-13 真实 HTTP/PostgreSQL 用例证明只保留一份报告和一个 run。

## 2. ISSUE-001：区域选择与激活保护 — CLOSED

修复位于 `WorkbenchPage.tsx` 的区域选择、case/epoch 代次和 activate 稳定键，以及 `WorkbenchParts.tsx` 的可聚焦区域按钮和 `canActivate` 门禁。

r2 结果：

- 正式组件测试覆盖 completed A/B 选择、当前步骤区域优先、case/epoch 清理、安全回退、queued/running/cancel_requested 与待答步骤门禁、409/超时/迟到成功和错误、ABA 及同内容重试键。
- 审核补充夹具确认两个 completed 区域均可选择，选择 B 后显示 B 卡；activate 歧义重试键保持一致。
- 隔离浏览器实际显示两个 `.area-select` 控件，点击第二项后读到其 `AUDIT-B-CONCLUSION` 卡；操作前后数据库 run 数均为 4，证明只读选择没有创建任务或改变业务流程。页面刷新仍恢复同一病例。

结论：r1 的不可选择及活跃任务误激活问题关闭。

## 3. ISSUE-002：composite 工况 — CLOSED

修复位于 `ObservationForm` 的请求组装和有限十进制校验。生产请求在 `kind=composite` 时同时保留 `choice_index`、顶层 `conditions` 以及各 measurement 的 `spec_id/unit/conditions`。

全新隔离 PostgreSQL 上的真实 HTTP 反例确认：缺顶层工况、篡改工况、空值、NaN、Infinity、非法十进制、错单位以及携带额外 choice/measurements 的 unavailable 均为 422，且没有写入观察；合法 composite 返回 202，数据库只新增一条观察，顶层及子项工况、单位和规格均保持。原 ProposalService、批准规格和工况门禁没有放宽。

结论：r1 的合法 composite 必然失败问题关闭。

## 4. ISSUE-003：稳定幂等键 — CLOSED

开始诊断、区域激活、观察提交、更正、取消、进度报告和最终报告均按目标、case/run/area/step/observation、revision、epoch 及规范化 body 持有动作键。成功或明确终态清除；未知结果保留；请求上下文或 body 变化生成新键。

r2 逐项验证：

- 同一规范化请求的歧义重试使用相同 key；body、revision、epoch 或目标变化使用新 key；旧 case 的键不会跨实例复用。
- activate、cancel、progress/final report 的歧义重试稳定；correction 的 revision 与完整上下文进入指纹。
- 同键报告真实 HTTP/PostgreSQL/worker 路径返回同一 `report_id/run_id`，数据库保持一条 report 和一条对应 run；更正后旧报告仍为 stale 且可读。
- r1 的不同键反例仍可产生两份报告，符合服务端“不同键是不同动作”的既有契约，没有通过改变服务端含义掩盖前端缺陷。

结论：r1 的报告重复创建和更正键错配问题关闭。

## 5. ISSUE-004：SSE snapshot 恢复 — CLOSED

`consumeRunEvents` 现在将 `onDisconnect` 失败纳入受控循环，保留 cursor，以 500ms 起步、最高 5s 的有界退避重试，通过 `onRecoveryError` 暴露当前上下文错误；snapshot 恢复后清除错误。AbortSignal、卸载、case/run/epoch 变化、terminal snapshot 和 reset_required 均有明确停止或重置路径。

r1 旧反例不再观察到 rejection。正式与审核补充测试确认：首次 snapshot 失败时 consumer 继续运行且错误可见，第二次成功后恢复；持续失败没有忙循环；终态停止；reset 清游标；ABA、卸载和上下文变化不会污染新页面。当前有效错误仍显示，没有被防迟到逻辑吞掉。

结论：r1 的 snapshot 临时失败终止恢复链问题关闭。

## 6. ISSUE-005：PDF 不可变物理页定位 — CLOSED（插件限定）

EvidenceService 的 `source_access` 只根据已保存 evidence 的 `document_version_id`、document 关系及不可变 locator 生成。OpenAPI 明确区分 `available`、`needs_ocr`、`page_missing`、`mapping_missing`，并单列 `page_image_status`；前端不猜页码、不回退 latest 或第一页。

在全新隔离 PostgreSQL/storage 中，r2 创建两页内容明显不同的合成 PDF，将 evidence 绑定到 v1 第 2 物理页，然后为同一 document 增加 v2。旧 evidence 仍返回 v1、page=2、旧 hash 与旧 locator；实际 `content_url` 返回 200、`application/pdf`，PDF 解析器确认第 2 页文本只存在于物理第 2 页。撤销只使 current validity 失效，没有改变历史版本或页；缺页、映射缺失、needs_ocr 与无独立页图状态分别保持。owner/版本访问仍由服务端授权。

页面入口使用服务端给出的 v1/page=2 地址，引用切换的 A→B→A 迟到响应由组件测试阻断。隔离 Chrome 能显示正式证据入口状态，但本机自动化环境没有完成内置 PDF 插件对第 2 页的视觉渲染；本报告不将其写成插件通过。独立 page image 当前明确为 `unavailable`，页面如实说明。

结论：服务端不可变版本/物理页绑定及页面入口缺陷关闭；浏览器内置 PDF 插件渲染仍是限定范围外的未验证项。

## 7. ISSUE-006：报告 run 状态恢复 — CLOSED

报告 POST 返回的 `run_id` 由页面保存并交给独立 `RunStatus`。queued/running 状态可见；SSE 或 snapshot 终态会刷新 report list、detail、gate 和 case snapshot；刷新页面可从 draft 报告恢复 run。诊断 run 与报告 run 分开渲染。

真实 HTTP/PostgreSQL/worker 定点完成 progress 创建、run 执行、终态报告读取、刷新恢复、观察更正及旧报告 stale。审核补充组件反例确认 draft run 恢复后显示 completed 报告内容；失败/取消状态沿统一结构化错误路径展示。final gate=false 时按钮禁用，服务端既有 409 用例证明过时按钮状态也不会创建任务；unknown 仍不能启用最终报告。

结论：r1 的报告异步任务终态不进入工作台问题关闭。

## 8. 本轮验证与证据版本

| 检查 | 本轮结果 | 证据 |
| --- | --- | --- |
| 46 项整改交付、31 项 r1 原证据、Git 暂存内容 | 全部匹配 | `baseline-verification.json`、`final-protection.json` |
| r1 原前端反例 | exit 1，5/5 旧缺陷断言不再成立 | `r1-counterexamples.log` |
| r1 不同键报告后端反例 | exit 0，1 passed | `r1-backend-counterexample.log` |
| 当前正式前端 | exit 0，6 files / 37 passed | `frontend-tests.log` |
| r2 补充前端边界 | 首轮 7 passed/1 夹具错误；补正后 exit 0，8 passed | `frontend-extra-attempt-1.log`、`frontend-extra.log` |
| 后端整改定点 | 最终 exit 0，8 passed | `backend-targeted.log` |
| r2 真实 HTTP/数据库补充反例 | 两次夹具收集错误后，最终 exit 0，2 passed | `backend-extra-attempt-1.log`、`backend-extra-attempt-2.log`、`backend-extra.log` |
| typecheck / api:check / 独立 build / Ruff | 均 exit 0；build 105 modules | 对应 `.log` |
| 隔离浏览器 | 登录、病例刷新、两个完成区域切换、报告状态及 unknown 边界通过；切换未增加 run | `browser-verification.json`、`browser-area-after.json`、`browser-workbench.png` |

后端最终使用全新数据库 `xiutu_test_wp15r2_5b8009f51d` 和独立 storage。首次迁移因审核 token 夹具长度错误、第二次 pytest 因 Windows 全局临时目录权限失败，均保留原日志；换用合法测试 token 和项目内独立临时目录后执行成功。这些是审核环境/夹具错误，不是业务断言失败。浏览器首次重跑时审核实例已停止，重新启动本轮专属 5235/8235 后完成；实例已停止，5180/5196 未操作。

预览共享文件及其封存哈希未变，预览兼容 22 项与 Node 运行时 2 项引用整改自测证据，本轮未重复运行。没有重跑约 40 分钟后端完整入口，没有重跑真实 DeepSeek、U511、U513、U514、性能、部署或模型评测。

## 9. 保留限制

- 浏览器内置 PDF 插件的第 2 页视觉渲染未验证；授权 HTTP 响应、PDF 字节和物理页内容已经验证。
- 正式 Evidence API 当前没有独立页图，页面明确显示 `unavailable`；本轮没有实施 OCR。
- 真实资料仍为 `NOT_MET`；当前证据来自明确合成资料，不代表真实车型或维修效果。
- 真实续轮没有发布第二项当前检查；`unknown` 不是确诊、排除或最终报告。
- 真实最终报告语义、生产恢复、负载、部署和真实维修效果未验证。
- 正式前端未部署至 5180/5196；WP-16/17 未开始。

## 10. 结论

ISSUE-001、ISSUE-002、ISSUE-003、ISSUE-004、ISSUE-005、ISSUE-006：**全部 CLOSED**。

**结合 r1 与本轮定点复核，WP-15 限定正式诊断工作台及合成技术范围 `REVIEW_PASS`。**

该结论只建议接受本报告明确列出的限定范围，不代表用户已经接受 WP-15，也不代表生产部署、真实资料、第二项真实检查、真实最终报告或整个 P5 已完成。
