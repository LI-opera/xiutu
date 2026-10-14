# 修途新工作台接手文档（截至 2026-09-25）

> **同日后续更新：** 用户另授一次“新增气路详细参考”真实调用已完成。当前目标病例最新分析为 `43e16b6f-e643-4a80-8126-e31caaee1434`；本文原 `b2cb1c80-f94e-4c43-bc0d-1f0acbc98052` 保留为旧结果。病例仍revision60/59条有效观察且无处理/复检。新参考范围/性质及1—11、14、16节已冻结，输出8192上限，实际22,834/3,622 tokens；付费窗口已关闭。先读 [C19记录最后一节](WORKBENCH-ADAPT-C19.md)，再按本文阅读顺序接手；仍未获用户验收，不自行再调用。

> 给新窗口的定位：这是**接手地图，不是新的实施授权**。开始任何修改前，重新核对代码、服务、病例和用户最新指令。本文把已观察到的事实、历史实施记录、尚待用户验收的体验明确分开。当前工作仓库是 `E:\Work\xiutu-v5`；`E:\Work\v4-double` 是旧项目及规划资料所在目录，不是同一工作树。

## 1. 一分钟读懂当前停止点

- 当前成果：正式 5215 工作台上，独立合成 DEMO 病例已经通过 C19 新链路获得**一次** DeepSeek `deepseek-flash` 真实生成的结构化维修建议，已保存，页面及刷新可读。体验入口：[C19 真实指导病例](http://localhost:5215/workbench/17c8ddf4-fd43-44cc-8f2c-f922d922b8af)。病例 ID `17c8ddf4-fd43-44cc-8f2c-f922d922b8af`，输入 revision 60，分析 ID `b2cb1c80-f94e-4c43-bc0d-1f0acbc98052`。
- 这次输出对应契约 `case-advice-open-c19-v1`、提示词版本 `dkvb-c19-v1`，输出上限 8192 tokens。一次真实生成返回 `finish_reason=stop`，提供方报告输入 14,930、输出 5,992、合计 20,922 tokens；实际费用未知。该次授权**已使用并关闭**，不能据此进行新的付费调用。
- 病例有 59 条明确标为模拟、非用户实测的维修前有效观察；没有把模型建议写成维修、复检或最终报告事实。专题资料只选了与该病例有关的 4 段摘录进入本次模型输入；图像是页面查看引用，**模型没有读取图像**。
- 当前页面的真实结果已实际查看和刷新：判断、步骤、处理后验证、资料/观察入口仍在；点击 AIR-07 引用未写观察。病例仍是 revision 60、59 条有效观察、0 条处理/复检记录。浏览器应停在上述结果开头；新窗口仍须自己复核当时状态。
- 运行实例在真实调用后恢复为 `stub / paid=false`，本地回环自动登录。`scripts/wp15_workbench.py status` 本文写作时显示本项目登记的 API、Web、worker 全部 `alive=true`；这个运行状态会变化，不能从文档推定以后一直在线。
- 状态是 **`IMPLEMENTED_NOT_ACCEPTED`**：程序链路与页面可用，不代表用户已接受这份建议，更不代表真实车辆诊断或维修技术结论经过系统审核、实车验证或最终报告获准。下一步是**等用户体验和明确指令**，不是自动再调用模型、扩充资料或进入阶段 D。

## 2. 仓库、资料与状态的不同层次

| 层次 | 去哪里看 | 如何理解 |
| --- | --- | --- |
| 正式实现 | `E:\Work\xiutu-v5` | 当前 API、worker、前端、数据库迁移、测试、实施记录都在这里；实际行为以运行代码与当前服务为准。 |
| 正式 WP 状态 | `docs/implementation/STATUS.md` | 记录 WP-00—15 各自有限接受、WP-16/17 未开始及真实资料门禁等正式阶段状态；**不是**最新 C19 产品恢复进度的逐项汇总。不要用较旧的 WP 状态否认 C19 已发生的真实调用，也不要用 C19 演示结果改写 WP 的正式验收。 |
| 产品恢复时间线 | `docs/implementation/product-recovery/README.md` | R0、B01/B02、UX、C01—C19 的实施索引及历史记录。每节描述的是**当时**状态，尤其早期“尚未真实验证”等语句可能已被后续阶段超越。 |
| 当前产品边界 | `docs/implementation/product-recovery/WORKBENCH-ADAPT-C19.md` | 目前新分析的契约、保留功能、截断留存/预算修复，以及最新 8192-token 真实结果。 |
| 本地开发身份 | `docs/implementation/product-recovery/WORKBENCH-LOCAL-AUTO-LOGIN.md`、`docs/runbooks/frontend-diagnosis.md` | 仅本机回环实例免重复输入令牌；病例归属、CSRF 和付费授权仍独立。 |
| 专题设计及来源 | `E:\Work\v4-double\docs\参考\专题资料包\探岳维修资料1` | 合成 DKVB/P0299 专题的题库、演示流程、来源登记与图示。此目录不是可以全部无差别发送给模型的厂家手册。 |

工作树长期含有大量已存在的未暂存/未跟踪修改；本次检查中，`docs/implementation/product-recovery/` 等路径显示为未跟踪。**现有修改属于用户和此前任务**。任何新窗口开始前先核对 Git 状态，不要 `git add -A`、提交、重置、清理、stash 或删除临时树。若根路径默认落在 `E:\Work\v4-double`，先切到正式实现仓库，不能在旧项目误改。

## 3. 已完成的工作按能力看，而不是按任务编号堆叠

### 3.1 正式工作台与病例记录

- 五区域和现有模块构成正式工作台；普通观察可跨区域独立记录，不能因浏览/展开把整区自动纳入必查。初始必查与规则派生由服务端决定；未检查不等于正常，无法完成不等于已排除。
- 纯选项题点击即提交；文字、数值、多字段和无法完成原因等输入题由用户点击“保存”才提交。已保存值可直接修改再保存，后台保留可追溯修订；同一次观察的更正不得伪造新复检轮次。多选题保留连续选择。
- 成功保存可自动展开下一项，但**不自动滚动，也不自动收起刚完成问题**；失败或用户已切换位置不能抢回界面。页面不恢复“未保存”文案和“纳入本轮排查计划”面板。综合分析四栏可独立折叠。上述交互是过去 UX 工作包的既定成果，除非用户明确要求，不应在处理 AI 时回退。
- B02 阶段对条件操作、无法检查、派生判断、完成度、处理与维修后复检轮次做了服务端语义修复。用户曾接受的是**B02 合成专题工作台体验与执行流程**，不是实车诊断能力验收。处理建议/导航不自动记录已维修或复检通过；最终报告仍有独立门禁。

### 3.2 AI 链路经过的关键转向

1. C01—C13 建起病例分析 API、服务端事实/资料快照、任务与持久化、一次请求/幂等/过期、受限诊断，以及历史受控操作与分层发布机制；多个真实回复被当时的内容门禁拒绝。历史失败仍是历史事实，不可自动改为成功。
2. C14—C18 收敛旧约束、补充气路接头场景资料、改进维修人员可读的判断→确认→处理→验证展示；C15/C18 的真实调用都没有形成可交付的已发布指导，不能把其离线预览或替身当成成功的真实结果。
3. C19 是明确的**产品边界变更**。新请求使用 `case-advice-open-c19-v1`：模型可直接撰写技术方向、检查/维修建议；服务端不再以关键词、数值措辞、方向类型、`action_id` 白名单、资料适用性审批或自由文本依赖推断来审批 AI 技术结论。服务端仍负责 JSON 类型/大小、身份与病例归属、就绪/安全停止、冻结快照、版本/并发/幂等、一次付费授权、诊断留存和结果持久化。旧版本的审核代码仅供历史快照/任务兼容，不应叠加到新请求。
4. C19 首次 4096-token 真实尝试因 `MODEL_TRUNCATED` 失败，当时原响应与 usage 没有保存；**不能恢复或猜测那次的部分正文或用量**。随后修复 SDK 长度异常的部分响应留存，以及统一 `CASE_ANALYSIS_MAX_OUTPUT_TOKENS` 配置。用户另行授权的 8192-token 调用才得到本节所述完整结果。历史失败分析 `3ac3c93c-918d-4304-97dd-2b5f0f0dda5b` 原状保留。

### 3.3 最新真实病例的内容与评价边界

新病例是从原完整模拟病例 `a506d2ac-fcfd-4d37-b411-64ab38f62efb` 通过正式病例/观察接口复制同一 59 条维修前剧本而建。另建病例的原因是服务端已有一次真实调用保护，不允许在原病例事实版本再次创建付费任务；没有清旧账本、重设幂等或改答案。

真实建议优先考虑增压软管接头座合不良或泄漏，结合 AIR-07/08/09/15/16、接头检漏响应及可比工况约 370 hPa 压差，提出复核接头、按提供资料重新座合/紧固、处理后检漏及同工况压力帧复测；若未解决，再审视压力信号、执行器和涡轮方向。其“当前判断”较长，包含许多内部观察 ID；部分“必要确认”基于继承的接诊字段，是否确为现场必要仍需用户判断。**结构解析和显示成功只是功能性结论，不是技术正确性背书**。新 C19 路径本身不提供系统对 AI 技术结论的内容审核保证。

## 4. 新请求从页面到结果的实际职责

```text
正式工作台 /workbench/{case_id}
  ├─ 用户观察：原问题接口保存/更正 → 病例 revision 增加 → 旧分析标记过期
  └─ 用户主动请求 AI 分析
      → 鉴权、归属、就绪/安全停止、版本和幂等检查
      → 服务端冻结当前有效观察、派生状态、缺项、选定资料、契约、预算
      → 任务/worker → 网关最多一次生成（真实模式另需明确付费授权）
      → 受限响应留存 → C19 JSON/资源结构处理 → 结果持久化
      → 工作台显示建议、来源方式、输入版本、过期状态和可匹配引用
```

浏览器**不上传自称完整的事实清单**供模型直接信任。观察/缺项/资料引用只在冻结快照或当前题目录中匹配时提供查看/导航；错误 ID 只能显示局部“未匹配/无法定位”，不能猜另一个问题，也不因一个坏链接拒绝整份建议。模型文字作为不可信文本节点渲染，不执行其 HTML、脚本、工具调用或 URL。分析建议不自动成为病例观察、已处理事实、维修后复检事实或最终维修报告。

按故障排查顺序阅读代码（均相对 `E:\Work\xiutu-v5`）：

| 责任 | 主要文件 |
| --- | --- |
| 正式页面与 AI 区 | `frontend/src/formal/design/workbench-v2/FormalWorkbenchB01Page.tsx`、`FormalCaseAnalysis.tsx`、`formal-workbench-v2.css`；正式入口另见 `FormalWorkbenchV2Page.tsx`。 |
| 病例分析 HTTP 与权限入口 | `backend/app/api/case_analyses.py`。 |
| 请求门禁、冻结、列表/读取、当前/过期状态 | `backend/app/services/case_analysis_service.py`。 |
| 专题资料选择 | `backend/app/services/case_analysis_context.py`、`backend/app/topics/tanyue_dkvb_p0299_c15_context.json`；不要把来源登记当作已经进入模型输入的正文。 |
| 当前 C19 schema、提示词、任务执行/发布路由 | `backend/app/domain/case_analysis.py` 中 `CaseAdviceOpenV1`，`backend/app/services/case_analysis_runtime.py`，`backend/app/services/case_analysis_c19.py`。旧 C09/C14 分支是历史兼容，核对版本路由再判断是否仍在新路径执行。 |
| 模型与预算、截断诊断 | `backend/app/infrastructure/model_gateway.py`、`model_budget.py`、`backend/app/services/case_analysis_diagnostics.py`、`backend/app/config.py`。 |
| 专题规则与历史操作清单 | `backend/app/topics/tanyue_dkvb_p0299_b01.json`、`..._b02_rules.json`、`..._c15_actions.json`。C19 新模型输入不再以历史 `action_catalog` 审批步骤。 |
| 本地启动/运行 | `scripts/wp15_workbench.py`；启动说明 `docs/runbooks/frontend-diagnosis.md`。 |
| 定点检查 | `tests/unit/test_case_analysis_c19.py`、`test_case_analysis_output_budget.py`、`test_auth.py`、`test_workbench_b02.py`；前端 `frontend/tests/formal-workbench-ux.test.ts`、`frontend/tests/wp15-workbench.test.tsx`。只运行与新任务风险对应的检查。 |

## 5. 本地运行、登录和费用边界

- 现有本机入口是 `http://localhost:5215/`（正式工作台）和 `/workbench/{case_id}`；API 为回环 `127.0.0.1:8215`。不要开新演示端口。脚本 `python -B -m scripts.wp15_workbench status` 可只读查看其登记的 API/Web/worker；启动或停止服务前还须检查进程归属和新任务权限。不要因文档中记有 URL 就假设服务一定还在。
- 本地自动登录仅在显式开发模式、非生产、实际客户端和监听端均为回环时建立稳定开发身份会话。Chrome 与 Codex 内置浏览器独立获取会话；重启不需用户反复输入令牌。病例归属、写入 Origin/CSRF 和权限仍存在。`start --manual-login` 关闭此模式，普通非本地/生产环境保留正常鉴权；**免登录不等于任意人可见所有病例**。
- 本机通常以 `stub / paid=false` 运行。文档中的真实建议是**历史结果的生成方式**，与当前后续请求模式不是一回事。不要因为页面有“真实模型生成”就推断普通按钮现在会或应该付费。
- `CASE_ANALYSIS_MAX_OUTPUT_TOKENS` 是当前统一预算配置；严格正整数范围 256–16384，创建时冻结，预检、网关及账本使用同一值。普通替身启动为 1536；8192 是已经消耗的那次独立授权，不是新窗口可自行继续使用的额度。总输入字符上限为 48,000；模型上下文、实际提供方与密钥仍须在**每次经用户明确授权的真实请求之前**重新核对。
- SDK `LengthFinishReasonError` 或正常 `finish_reason=length` 的部分正文/模型/finish_reason/usage，只在提供方实际提供时进入既有受限诊断；本地留存上限 32 KiB、30 天，供应商长度终止与本地裁剪分别标识。截断内容不修补为完整 JSON、不发布、也不自动重试。受限诊断需有权限，不能向普通页面或日志泄漏原文/密钥。
- 不得把项目 `.env`、API 密钥、访问令牌、cookie、数据库连接串、诊断原文或整份原始手册复制进新窗口聊天、文档、截图、日志。**本接手任务没有读取密钥或发起模型调用**。未来若用户另授一次真实请求，要将范围限定到目标病例、revision、幂等键和单次请求；请求是否送达不确定就停止，不能重复购买。

## 6. 专题资料：读什么、信到什么程度

首先读本地资料包的 `README.md`、`00-专题知识包总规范-v2.md`、`07-完整问题块与选项库-v2.md`、`08-结果组合与路由-v2.md`、`sources-register.md`。这是 DKVB/P0299 五区问题/演示规则的设计原稿，不是“全是厂家证据”的资料库。资料包显式区分 `FACT_LOCAL_MANUAL`（本地手册支持）、`GENERAL_VAG_REFERENCE`（通用参考）、`EDITORIAL_DEMO`（编辑性演示规则）、`SAFETY_BOUNDARY`（安全/结论边界）；模拟测量值只属于病例剧本。旧 01—06 文档保留演变背景，导入协议应以带 `v2` 的文件及 `structured/protocol-dkvb-p0299-demo-v2.json` 为准。

C15 为接头场景接入的正式内容应读 `WORKBENCH-ADAPT-C15.md` 及 `backend/app/topics/tanyue_dkvb_p0299_c15_context.json`；来源可回溯到资料包 `sources-register.md` 和必要时原始手册目录 `E:\BaiduNetdiskDownload\M164\06大众车系\大众车系\28探岳\2019一汽大众探岳（探岳GTE）`。只有实际被选进**该次冻结快照**的摘录正文才能说“提供给模型”；图片/线路图如只是 URL 引用，不能说模型读图。任何厂家限值、拆装方法、扭矩、工具条件应按具体来源和适用范围核对，不能把演示阈值当实车维修标准。C19 取消的是**系统对 AI 内容的发布审批**，不是把模型文字变成受认证的厂家技术资料。

## 7. 新窗口建议先读的文件（按顺序，不必一次读完整历史）

### A. 15 分钟建立正确的当前状态

1. 当前请求和本文；再检查仓库根及目标目录祖先的适用 `AGENTS.md`。本文撰写时对仓库根、`docs/`、`docs/implementation/`、`product-recovery/` 的显式检查未发现适用文件；后续新增时必须遵守。
2. `E:\Work\xiutu-v5\docs\implementation\product-recovery\WORKBENCH-ADAPT-C19.md`：先读最后两节，再读开头的新旧职责对照，防止把历史门禁当现行要求。
3. `E:\Work\xiutu-v5\docs\implementation\product-recovery\README.md`：按时间线检索相关任务，不要只读文件开头的 R0 状态就判断当前进度。
4. `E:\Work\xiutu-v5\docs\implementation\STATUS.md`：核对正式 WP 边界和验收范围；与 C19 产品恢复记录并列阅读。
5. `E:\Work\xiutu-v5\docs\implementation\product-recovery\WORKBENCH-LOCAL-AUTO-LOGIN.md` 与 `E:\Work\xiutu-v5\docs\runbooks\frontend-diagnosis.md`：了解 5215/8215、稳定开发身份、默认 stub 及预算配置。

### B. 要改 AI 请求、建议正文或页面时

1. `backend/app/api/case_analyses.py` → `backend/app/services/case_analysis_service.py` → `backend/app/services/case_analysis_runtime.py`：跟一次新请求的真实版本分流，不凭旧文件名猜执行链。
2. `backend/app/domain/case_analysis.py` 的 `CaseAdviceOpenV1`、`backend/app/services/case_analysis_c19.py`、`backend/app/services/case_analysis_context.py`、`backend/app/topics/tanyue_dkvb_p0299_c15_context.json`：核对当前结构、资料是否真进入输入，以及哪些只是历史兼容。
3. `backend/app/infrastructure/model_gateway.py`、`backend/app/infrastructure/model_budget.py`、`backend/app/services/case_analysis_diagnostics.py`：预算、唯一请求、截断与受限留存。若没有付费授权，只做只读/离线检查。
4. `frontend/src/formal/design/workbench-v2/FormalCaseAnalysis.tsx`、`FormalWorkbenchB01Page.tsx`、`formal-workbench-v2.css`：实际展示、问题导航和已接受的表单体验。确认是**正式**工作台组件，不要在 prototype 页面修了却声称线上已改。
5. `WORKBENCH-ADAPT-C17.md`、`WORKBENCH-ADAPT-C15.md`：了解页面表达目标、场景资料和旧受控操作的历史边界；它们不是 C19 新请求的技术审核规则。

### C. 要深挖产品与专题来源时

1. `E:\Work\v4-double\docs\参考\修途项目-新工作台执行架构适配分析与迁移方案-2026-09-23.md`：阶段 B/C、快照及建议边界的规划来源；与当前 C19 代码相比，冲突时以用户最新决策与现行实现为准。
2. `E:\Work\v4-double\docs\参考\专题资料包\探岳维修资料1\README.md`，再按其推荐顺序读 `00`、`07`、`08`、`09`、`10` 与 `sources-register.md`；需要解释某个问题或演示阈值时回到具体条目。
3. `E:\Work\xiutu-v5\docs\implementation\product-recovery\WORKBENCH-ADAPT-B01.md` 和 `backend/app/topics/tanyue_dkvb_p0299_b01.json`、`..._b02_rules.json`：已发布问题、条件操作、必查与派生状态。不要把专题设计稿直接当现行服务端规则。
4. 若任务要求核对具体维修操作，再打开上述原始手册的**相关章节**，按 C15 记录追溯；不要扫整个手册目录、把全部 PDF/图片塞入提示词，或把图纸查看链接说成已被模型解析。

## 8. 新窗口的安全开工顺序

1. 先确认用户新任务究竟是“审阅/解释”还是“修改/生成”。本接手文档**不授权**新的付费生成、病例写入、服务重启、Docker/WSL 操作、资料扩充、Git 操作或阶段 D。
2. 核对 `E:\Work\xiutu-v5`、适用指引、`git -c safe.directory=E:/Work/xiutu-v5 status --short`、最新 C19/README/STATUS；先记录已有改动，避免覆盖。
3. 如果涉及运行态，先用只读 `python -B -m scripts.wp15_workbench status` 和正式 API/浏览器核对病例、revision、分析 ID、当前请求模式；`status` 只表示登记进程存活，不代替 API/页面检查。保持原 5215/8215 入口和现有数据库。
4. 如果涉及病例修改，优先创建**另一个明确标记的独立 DEMO 病例**并使用正式病例/观察接口；不要直接写库、重绑或更改用户正在看的 `17c8...` 病例。每条数据区分“模拟观察”“来源资料”“模型建议”“实际处理/复检”。
5. 如果涉及模型，先重读当前预算和历史调用账本；没有用户**针对本次**模型、额度、病例和次数的授权就停在预检。不得复用已花费的 8192 授权，或对状态不确定的请求重试。
6. 修改只在授权范围内；做定点测试和实际正式浏览器路径，区分 API/组件测试与浏览器实际体验。更新现有产品恢复记录，报告完成、未完成、状态和限制。最后等用户体验，不自行宣布接受或进入下一阶段。

## 9. 当前未解决、但不能擅自扩展的事项

- 用户尚未评价最新 C19 真实指导的可读性和技术有用性。初步已见总结含许多 UUID、部分继承信息重复要求确认；是否调整表达应等用户反馈，不能为了改善体验擅自重做契约或再次付费。
- C19 结构化生成没有技术内容审核保证。建议能显示不表示维修参数、操作适用性或实车故障方向已由系统批准；正式报告门禁独立。合成专题的验证不能推广到所有车型或真实车辆。
- 本次只验证一个完整模拟气路接头病例及 4 段相关摘录。其他五区场景、真实资料覆盖、图片理解、诊断质量和维修后闭环未随此次真实调用全面验收。
- `STATUS.md` 中的正式 WP/真实资料门禁仍须单独对照，不得由 C19 单病例结果静默改写。

## 10. 可直接给新窗口的开场说明

> 接手 `E:\Work\xiutu-v5` 修途正式工作台。先读 `docs/implementation/product-recovery/CURRENT-HANDOFF-2026-09-25.md`、最新 `WORKBENCH-ADAPT-C19.md`、`README.md`、`docs/implementation/STATUS.md` 和适用 AGENTS.md。当前 5215 有独立合成病例 `17c8ddf4-fd43-44cc-8f2c-f922d922b8af` 的一次真实 DeepSeek 建议，分析 `b2cb1c80-f94e-4c43-bc0d-1f0acbc98052`，尚待我体验接受；其 8192-token 一次性授权已经用完。当前本地服务恢复 `stub / paid=false` 与回环自动登录。不要复制历史命令发起付费请求，不修改病例或 Git 状态；先复核当前状态，然后只执行我接下来明确交办的任务。合成/DEMO 不等于实车维修结论，C19 新路径也不提供 AI 技术内容审核保证。
