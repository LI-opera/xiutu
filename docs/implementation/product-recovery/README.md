# 修途产品恢复总记录

## 2026-09-26：仅区域综合分析解除 100 KB 本地输入门槛

按用户新增授权，匹配区域综合 AI 分析可发送完整参与区域资料，不再受原服务端字符上限和计费模块 100 KB 字节门槛拦截；其他模型通路保持原限制，费用仍按完整输入预留，提供方上限仍适用。旧失败记录保留且可手动重试。本轮真实生成 0 次，验证与边界见 [WORKBENCH-MATCHED-AREAS-ANALYSIS-01](WORKBENCH-MATCHED-AREAS-ANALYSIS-01.md)。

## 2026-09-26：分析失败后可手动重试

失败分析不再锁死同一输入的按钮；手动重试另存新尝试，旧失败可回看。数据库迁移与回滚探针通过，真实模型调用 0 次。共享计费模块的 100 KB 输入门槛仍在：移除它的改动因涉及所有付费模型请求的成本边界被执行环境拒绝，本轮未绕过；相同超限输入重试仍可能失败。详见 [WORKBENCH-MATCHED-AREAS-ANALYSIS-01](WORKBENCH-MATCHED-AREAS-ANALYSIS-01.md)。

## 2026-09-26：综合分析只发送有记录区域

修正“匹配五区”被误当作“本次分析五区”：只有当前有有效、已保存检查观察的区域及其对应资料进入输入。病例 `18a144fe-dfa2-4d44-8824-11388d26fa9a` 的范围为两区、两份资料、11 条记录；其余三区不发送，单次点击仍只生成一份综合建议。离线回滚探针通过，真实模型调用 0 次。详见 [WORKBENCH-MATCHED-AREAS-ANALYSIS-01](WORKBENCH-MATCHED-AREAS-ANALYSIS-01.md)。

## 2026-09-26：匹配区域一次综合 AI 分析

现有模板匹配的多个区域会在一份冻结输入中逐区携带答案与资料，用户点击一次生成一份综合建议；切换区域只用于浏览。旧单区历史记录保留。状态 `IMPLEMENTED_NOT_ACCEPTED`，本轮真实生成 0 次。实现与验证见 [WORKBENCH-MATCHED-AREAS-ANALYSIS-01](WORKBENCH-MATCHED-AREAS-ANALYSIS-01.md)。

## 2026-09-26：区域资料关联与独立 AI 分析

已在原工作台接入区域级分析，关系与文档正文存 PostgreSQL。五区各自关联资料，按区域读取答案和版本化正文；不改原 UI 风格，不混入其他区域答案。状态 `IMPLEMENTED_NOT_ACCEPTED`，本轮真实调用 0 次。资料登记、数据库结构、验证及边界见 [WORKBENCH-AREA-ANALYSIS-01](WORKBENCH-AREA-ANALYSIS-01.md)。

## 2026-09-26：车辆信息与固定区域模板匹配

已实现，待用户验收。沿用现有工作台 UI；大众/探岳/2019/DKVB 的 P0299 显示五区、P0236 显示三区，关系表匹配版本化完整 JSON。旧病例不变，零模型调用。范围、入口和验证见 [WORKBENCH-TEMPLATE-MATCH-01](WORKBENCH-TEMPLATE-MATCH-01.md)。下文保留历史停止点，不代表本次最新状态。

> 新窗口接手请先读 [截至 2026-09-25 的当前工作接手文档](CURRENT-HANDOFF-2026-09-25.md)。本文件按发生时间保留历史记录；下文开头的 R0 状态并非最新 C19 停止点。

更新：2026-09-22  
当前里程碑：`R0 COMPLETE`  
下一停止点：等待用户明确安排 R1；本记录不启动 R1，不改变任何既有接受状态。

## 1. 本记录的边界

R0 只完成必要只读核对并建立本恢复总记录。没有修改业务代码、迁移、测试、`STATUS.md` 或历史接受/审核记录；没有运行测试、写库、模型或搜索调用；没有重启、替换或停止服务；没有执行 Git 暂存、提交、重置、stash 或推送。

本轮核对依据：`STATUS.md`、WP-15 限定接受记录、DKVB/P0299 可信协议契约与结果 r1、当前协议/协议服务/观察服务/runner/协议集成测试/正式工作台源码、现行 fixture，以及规划目录中的 `维修知识手册.md`、`规格与判断关系.md` 和 `knowledge.json`。

这里保留 WP-00—15 的历史限定接受；产品恢复缺口不能反向改写为“历史全部失败”，历史技术接受也不能扩大为“完整产品已完成”。

## 2. R0 当前事实

### 2.1 最新停止点与能力边界

- `STATUS.md` 仍记录 WP-00—15 为各自限定接受，WP-16/17 为 `NOT_STARTED`，真实资料为 `NOT_MET`。
- WP-15 实际证明的真实模型链路仍只有：首项有据检查 → 浏览器保存观察 → 续轮保守 `unknown` → 刷新读回。第二项真实当前检查、真实最终报告语义和真实维修效果均未证明。
- 最新 DKVB/P0299 协议切片为 `IMPLEMENTED_NOT_ACCEPTED`，只适用于 `synthetic=true`、`DEMO`、`formal_usable=false`。
- 当前协议只登记到 CHK-05 分支、CHK-05-SUPPLEMENT、CHK-06 → CHK-07；CHK-07/08 之后没有登记关系，没有 handoff、区域小结或完成终点。
- 当前集成测试聚合覆盖三条 CHK-05 分支、CHK-06 → CHK-07、字段拒绝、幂等、更正、profile/source 失效等技术边界；它没有提交 CHK-07 或 CHK-08 的观察，也没有证明路径收尾。

### 2.2 已确认的当前缺陷

1. **选项语义错位**：CHK-07 协议值是 `localized/not_found/inconclusive`，公开候选却显示“插头松动/牢固”；CHK-08 协议值是 `loose/secure`，公开候选却显示“外壳完整/破损”。当前路由按 `choice_index` 从协议值数组取值，页面文字和保存语义可以不一致。
2. **没有业务终点**：`ProtocolService._decision()` 要求每个决定都存在 `next_check_id` 和候选，无法真正发布 handoff、区域小结或终点；当前 `decision` 虽允许 `handoff/conclude`，运行实现并不支持。
3. **unavailable 丢失协议身份**：`ObservationService._payload()` 对 `unavailable` 提前返回，只保存 reason/component/checked；续轮 `ProtocolService.route()` 又要求 `protocol_id/version/check_id`，正常“做不了”操作会被判为 `PROTOCOL_OBSERVATION_INVALID`。
4. **冻结快照未用于执行**：绑定行保存了 `binding_json.protocol`，但 `_binding()` 仍用 `protocol_id/version` 从进程内 `REGISTRY` 读取当前对象；同名版本代码变化会静默改变历史病例行为。
5. **静态校验不足**：当前 schema 只检查 ID 重复和引用存在，没有检查每个公开选项的唯一出口、可达性、终点完整性、循环退出边界或 `completion_conditions` 的可执行语义。
6. **协议并非正常病例入口能力**：当前必须由私有准备脚本调用 `ProtocolService.register()`；正式病例创建没有 mode/policy 配置，也没有按车辆和资料自动选择适配协议。
7. **历史误映射风险**：凡是 `dkvb-p0299-guided-demo@1.0.0` 下已经提交 CHK-07/08 观察的病例，都不能在修复后按新标签静默重解释。R0 没有扫描或改写用户/历史数据库；R1 必须用只读查询识别并标记，保留原 choice、原标签快照、协议版本和观察内容。

### 2.3 Git 与可恢复基准

- 仓库分支为 `main`，尚无 `HEAD`。
- index 当前有 32 个条目；27 个为 staged add，5 个为 staged 后又有工作区修改。
- `git ls-files --others --exclude-standard` 本轮列出至少 4115 个未跟踪文件，其中约 3816 个在 `docs/`；若干历史 pytest 临时目录返回访问拒绝，因此该数字不是无遗漏的最终清单。
- 原 WP-00 暂存区仍存在。本轮没有改变它；不能用 `git diff` 代替未跟踪文件清点，也不能自动重置原暂存区。
- R0 两次只读核对期间，指定业务源码和 `STATUS.md` 未观察到内容变化。这个短时采样不能证明没有其他执行者；当前只能记录“未发现并发写入证据”，不能写成“确认无并发”。R1 开始前必须再次比较工作区和本节列出的关键文件。

### 2.4 基准提交候选与排除项

得到用户提交授权后，基准应按 allowlist 审阅，而不是直接 `git add -A`。

**候选纳入**

- 根配置与锁文件：`.gitattributes`、`.gitignore`、`.dockerignore`、`.env.example`、版本文件、`pyproject.toml`、requirements、`uv.lock`、前端 package/lock；
- `backend/`、`migrations/`、`frontend/src/`、`frontend/tests/`、`frontend/scripts/`、`deploy/`、`scripts/`、`skills/`、`tests/` 和 `evals/` 中的源码、固定 fixture 与正式测试；
- `docs/adr/`、`docs/api/`、`docs/architecture/`、`docs/runbooks/`、`docs/reference/`；
- `docs/implementation/` 中的状态、契约、结果、接受记录和确实作为接受依据的精简证据/manifest。

**明确排除**

- `.env`、访问令牌、数据库口令、Cookie、私有运行状态和任何真实凭据；
- `.local-data/`、`.test-runs/`、`.venv/`、node_modules、缓存、日志、数据库文件、storage、备份和模型权重；
- `frontend/dist*` 等生成构建；
- `docs/**/pytest-*`、`docs/**/repair-*/tmp` 等测试临时树；
- 尚未分类的根 `diagnosis.json`（当前仅确认是一次诊断输出结构，不先纳入基准）；
- PDF/图片/压缩包等被现行 `.gitignore` 排除的本地原件，除非之后逐项确认许可和必要性。

路径级敏感词扫描确认 `.env` 存在且已忽略；源代码、脚本和测试中也有 token/password 等配置或占位词命中。命中不等于含真实密钥。建立基准前只对 allowlist 做一次内容复核，报告路径与类别，不复制值；历史 evidence 和临时树不为此重复全仓扫描。

恢复方案：在获得提交授权前，以“当前文件路径 + 工作区状态 + 本记录 + R1 开始前关键文件内容比较”定位基准；获得授权后再保护原 index、审阅 allowlist/排除项并建立一次基准提交。没有授权时不让 Git 治理阻塞 R1 的范围决定。

## 3. 当前实例与唯一主入口建议

R0 只读端口核对（2026-09-22）：

| 入口 | 当前用途与对应关系 | R0判断 |
| --- | --- | --- |
| `http://localhost:5215/` → API `8215` | WP-15 正式 React/Vite 工作台；隔离 `xiutu_test_formal_user_*` 数据库和独立 storage。前端从正式源码目录运行；API 进程早于最新可信协议源码启动，不能假定内存代码等于当前文件。 | **建议作为 R1 完成后的唯一正式主入口**，但本轮不重启、不覆盖。 |
| `http://127.0.0.1:5225/` → API `8225` | 最新 trusted-protocol r1 专题实例；同一正式源码目录的 Vite/API/worker，独立 `xiutu_test_dkvb_protocol_*` 数据库和 storage；用户体验病例停在 CHK-05。 | 仅保留为历史 synthetic 验证实例；不升级为产品主入口。 |
| 5180 / 5196 | 旧资料预览/专题切片。R0 未发现当前监听。 | 保留历史，不作为恢复主入口。 |

5215/8215 与 5225/8225 同时存在，且源码、进程启动时间和隔离数据不同；“页面能打开”不能证明正在体验同一代码/数据版本。R1 实施完成并通过约定验证后，另按部署授权把正式 5215 实例更新到明确版本；旧实例不删除、不覆盖。R0 不提供“已可体验 R1”的入口。

## 4. 可保留资产

- PostgreSQL、现有迁移、UnitOfWork、owner/revision/graph_epoch 和幂等边界；
- jobs/runs、租约、心跳、SSE、checkpoint、fencing 和事务发布；
- 文档版本、解析、索引、检索、Evidence 快照和来源撤销门禁；
- 观察、更正、stale、区域、报告及最终报告门禁；
- ProposalService 的身份、引用、适配、规格和发布硬门禁；
- `diagnosis_protocol_bindings` 的病例/epoch 绑定思路与已保存 `binding_json`；
- 正式 React 工作台、资料中心、历史病例和生成 OpenAPI 类型；
- 当前协议的 profile/manifest/source 复核、确定性不调用模型、原事务发布接线。

以上资产是增量修复基础，不代表其全部产品语义已经完成。

## 5. R1 唯一参考子流程

### 5.1 范围选择

R1 只实现“CHK-05 局部泄漏定位 → CHK-06 已确认接头问题处理 → CHK-07 处理后复检 → CHK-11 最终演示复检/区域小结”，并为不进入此主线的结果给出有内容的 handoff。CHK-08/09/10 只作为交接目标说明，不在 R1 展开成第二套完整流程。

资料性质始终为 `synthetic=true`、`DEMO`、`formal_usable=false`：

- CHK-05 方法与限制：`维修知识手册.md` CHK-05，S02-P5/P6；测试压力不得超过 0.5 bar，且不能用保压下降判定泄漏。
- CHK-06：同手册 CHK-06，S02-P2；只在已有局部定位证据时记录模拟处理，完成不等于修好。
- CHK-07：同手册 CHK-07 与 `规格与判断关系.md` DS-02；新 run 的三帧目标/实际绝对压力和症状必须与旧阶段分开保存。
- CHK-11：同手册 CHK-11 与 DS-03；全部条件成立才产生 DEMO 区域小结，不自动生成最终报告。

### 5.2 稳定输入、后继和终点

协议 v2 使用服务端发布的稳定 `option_id`，保存 `option_id + 当时标签快照 + 结构化字段`；不能再靠两份数组的同一 `choice_index` 解释语义。

| 当前检查 | 输入/稳定值 | 必填字段 | 后继或终点 |
| --- | --- | --- | --- |
| CHK-05 | `leak.localized` | `leak_object_id`、`leak_location`、`evidence_kind`（visual/touch/leak_spray/ultrasound） | CHK-06 |
| CHK-05 | `leak.not_found` | 无 | `HANDOFF_CONTROL_DIRECTION`：本项未发现局部漏点；下一方向是 CHK-08，不能写系统正常/故障排除 |
| CHK-05 | `leak.inconclusive` | 无 | CHK-05-SUPPLEMENT |
| CHK-05 | unavailable | reason | `HANDOFF_UNAVAILABLE`：保留未检查事实并列出需补工具/可观察部位 |
| CHK-05-SUPPLEMENT | `leak.localized` | 同 CHK-05 定位字段 | CHK-06 |
| CHK-05-SUPPLEMENT | `leak.inconclusive` 或 unavailable | reason/现有缺项 | 补充最多一次后进入有内容 handoff，不允许无限自循环 |
| CHK-06 | `repair.completed` | 处理对象、模拟动作、完成状态；建立 `after_air_repair` 阶段 | CHK-07 |
| CHK-06 | `repair.not_completed` 或 unavailable | 未完成原因 | `HANDOFF_REPAIR_PENDING`，不发布“已修复” |
| CHK-07 | 结构化复检 | 新 `run_id`；`leak_result`；三帧 target/actual hPa absolute、`DEMO_LOAD_STABLE`；symptom present/absent | 按下列规则决定 |
| CHK-07 | 无漏点 + DS-02 三帧在带内 + 症状 absent | 上述完整 | CHK-11 |
| CHK-07 | 无漏点 + 三帧持续不足 | 上述完整 | `HANDOFF_CONTROL_DIRECTION`（CHK-08），说明一个问题已处理但仍有残余异常 |
| CHK-07 | 同处仍可定位泄漏 | 对象、位置和证据 | `HANDOFF_REPAIR_RECHECK`，指出返回 CHK-05/06 的理由；R1 不自动无限循环 |
| CHK-07 | 压力在带内但症状仍在 | 上述完整 | `HANDOFF_OTHER_DIRECTION`（CHK-10），不能说整车正常 |
| CHK-07 | mixed/缺帧/单位工况不明 | 具体缺项 | `need_input`；补齐失败后 handoff |
| CHK-11 | DS-03 完整 | 最新三帧在带内、症状 absent、P0299 absent、已处理问题全部复核、无未解决冲突 | `AREA_SUMMARY_DEMO_PASS`（CON-06 语义）；仅演示复检通过，最终报告仍由用户主动请求 |
| CHK-11 | 任一条件不满足或不可做 | 失败/缺项明细 | `HANDOFF_FINAL_RECHECK_INCOMPLETE`（CHK-10 语义） |

两条验收用用户路径：

1. 至少三项的完成路径：CHK-05 localized → CHK-06 completed → CHK-07 recovered → CHK-11 → DEMO 区域小结。
2. 合理提前交接路径：CHK-05 not_found 或 unavailable → 有内容 handoff；不得伪造下一检查、正常结论或系统错误。

## 6. R1 实现清单

以下是 R1 的已实施范围；交付状态仍是 `IMPLEMENTED_NOT_ACCEPTED`。

### 6.1 数据与迁移

当前 Alembic head 为 `0013_trusted_diagnosis_protocols`。R1 如实施，新增一个接在 0013 后的迁移（最终编号以当时 head 为准）：

- `cases` 增加可空历史兼容的 `diagnosis_mode`、`policy_version`；新病例由服务端校验，R1 只开放 `conservative`，自由模式在 UI 明示开发中；`web_enabled` 按用户决定推迟到 R3，本迁移未新增该字段；
- `diagnosis_protocol_bindings` 增加 `content_hash` 和历史 `requires_review` 标记；新 v2 绑定必须有 hash，旧 v1 行不改写原 `binding_json`/观察内容；
- 不为 option 新建表：稳定 `option_id`、标签快照及结构化字段保存在现有 JSON 观察负载；只有出现可证明的查询/约束需要时才扩大迁移。

### 6.2 后端文件、方法和 I/O

- 新增 `backend/app/protocols/dkvb_p0299_demo_v2.json`（或等价单一数据文件）及小型 loader：同一输入定义派生表单和 transition；包含 package id/version/content hash、适配、checks、options、transitions、handoffs、terminals、来源和循环上限。
- `backend/app/agents/trusted_protocol.py`：扩展 `option_id`、choice/action/composite、terminal/handoff 和可执行 completion rule；增加 `validate_protocol_package()` 检查可达性、每值唯一出口、终点、互斥、循环上限和来源；移除手写索引耦合。
- `backend/app/services/protocol_service.py`：新增 `select_for_case()`、`bind_for_case()`；`_binding()` 从 `binding_json.protocol` 读取冻结字节并校验 hash，REGISTRY 只判断批准/撤销；`validate_observation_fields()` 接收 option/action/composite；`route()` 输出 `next_check | need_input | handoff | area_summary`，0/多条命中均阻断。
- `backend/app/domain/schemas.py`、`repositories/cases.py`、`services/case_service.py`、`infrastructure/orm.py`：CreateCase/CaseSnapshot 增加 mode/policy；owner、信任级别和 protocol id 不由浏览器提供；病例创建保存配置并做资料/协议预检。
- `backend/app/services/diagnosis_service.py`：`start()` 在受控流程确认或创建适配绑定；空资料、无适配协议、自由模式未开放分别返回稳定业务码。
- `backend/app/services/observation_service.py` 与 `correction_service.py`：unavailable 也保存协议身份和 `option_id=unavailable`；正常观察保存 stable option id，不从展示文字正则反推协议语义；更正复制冻结 bytes/hash，旧 v1 误映射记录标 `requires_review`。
- `backend/app/agents/runner.py`：按病例 mode 显式分派；R1 conservative 调冻结协议 planner，free 返回未开放业务状态，不能偷偷走固定树或旧自由模型路径。
- `backend/app/services/publish_service.py`：复用 owner/revision/epoch/lease/fencing/事务门禁发布 step；增加受限 terminal publisher，把 handoff/DEMO area summary 持久化，不制造假步骤；最终报告门禁保持独立。
- 更新病例、观察、协议决定和终点 API/OpenAPI；重新生成 `docs/api/openapi.wp14.json` 与 `frontend/src/generated/api-schema.ts` 并审阅实际差异。

### 6.3 前端文件和交互

- `frontend/src/formal/state.ts`、病例类型与 `WorkbenchPage.tsx`：首页选择保守模式；自由模式可见但明确“R3 开发中”且不可假装可用；提交后始终显示当前 mode。
- `frontend/src/formal/diagnosis/types.ts`、`WorkbenchParts.tsx`：按服务端 option id/字段定义呈现 choice/action/composite；unavailable 仍带当前协议身份；按钮提交后展示下一检查、补项、handoff 或小结。
- 保留当前三栏外壳，但主栏只突出一个当前动作；UUID/revision/epoch/transition 继续折叠。
- 历史 v1 `requires_review` 病例显示“旧协议观察需确认”，不以新标签渲染旧 choice。

### 6.4 调用顺序

```text
首页填写病例并选择 conservative
→ CaseService 创建病例、冻结资料、保存 mode/policy
→ ProtocolService.select_for_case / bind_for_case 保存协议 bytes + content_hash
→ DiagnosisService.start 创建 run
→ worker 读取 run/case/epoch/冻结协议
→ ProtocolService.route 产生 DecisionEnvelope
→ ProposalService/来源/适配硬门禁
→ PublishService 事务发布 step 或 terminal
→ 工作台读取服务端快照
→ 用户按 option_id 提交观察（含 unavailable）
→ ObservationService 原子保存标签/值快照并创建下一 run
→ 重复直到下一检查、补项、handoff 或 DEMO 区域小结
```

## 7. R1 最小验证与停止规则

### 7.1 必须回答的问题

1. 新病例无需私有脚本绑定即可选择保守模式并获得适配 v2 协议；自由模式不会被伪装成可用。
2. 静态检查能拒绝无出口、歧义、不可达、缺终点、无限补项、未知引用和 hash 不匹配。
3. 所有本轮可见离散值都到达下一稳定状态或明确终点；CHK-07/08 原错位反例被直接关闭。
4. unavailable 保存后能到有内容 handoff，不触发 `PROTOCOL_OBSERVATION_INVALID`。
5. 修改进程内同 id/version 注册对象不能改变已绑定病例；冻结 bytes/hash 决定历史执行。
6. v1 历史观察不被新标签静默重解释；更正后按新 epoch/新事实路由。
7. owner/revision/epoch、幂等、来源撤销、重复提交和旧 run fencing 继续成立。
8. 浏览器完成两条路径：一条 CHK-05→06→07→11 到 DEMO 小结；一条 CHK-05 后合理提前 handoff；刷新、来源打开和一次更正仍成立。

### 7.2 选择的最小测试/体验范围

- 协议 loader/static validator 定点单元测试；
- 改造现有 `tests/integration/test_dkvb_trusted_protocol.py`：全选项出口、原错位反例、unavailable、冻结 hash、自动绑定、幂等、撤销和更正；只使用一个现有专用测试数据库/夹具；
- `frontend/tests/wp15-workbench.test.tsx` 与 `frontend/tests/state.test.ts` 的受影响用例；
- API 改动后的 typecheck 与 OpenAPI 漂移检查；
- 两条浏览器参考旅程，必须提交最后一项并看到 handoff/小结，不能停在卡片出现；
- 不调用模型；保守路径应保持模型/工具调用 0。

不默认运行全仓回归、性能测试、真实模型、联网、WP-16/17、全车型矩阵或第二套演示实例。未改变的 WP-00—15 能力引用既有证据。

### 7.3 扩大验证的触发条件

- 新迁移或 cases/config 语义影响既有非协议病例 → 增加直接相关病例/API兼容测试；
- terminal publisher 改动共享区域/报告状态 → 增加该共享状态的定点集成反例；
- OpenAPI 差异超出病例/观察/协议响应 → 检查被波及的生成类型和对应前端用例；
- 浏览器旅程出现观察丢失、错误解释、重复副作用、越权或错误引用 → 先定位根因，再只复核修复差异、原反例和直接依赖；
- R1 开始后发现其他执行者写入同一源码 → 停止固化基准并报告冲突，不竞争覆盖。

### 7.4 R1 通过与停止条件

预定定点验证全部通过、两条浏览器路径到明确终点、无未解决阻断项后立即交付，状态仅记 `IMPLEMENTED_NOT_ACCEPTED` 并等待用户体验/接受。非阻断重构和扩展进入待办。不进入 R2，不调用真实模型，不部署到其他端口，不自动建立独立审核任务或重复全仓验证。

## 8. 真实资料缺项与负责人

真实资料资格仍为 `NOT_MET`。本机专题包证明存在可追溯原件线索和已视觉核对页面，但 `formal_approved=false`，且作者整理关系/DS 阈值不是厂家标准。

| 缺项 | 当前状态 | 需要的责任方 |
| --- | --- | --- |
| 原件许可、版本和可使用范围 | 未确认 | 资料提供者/用户 |
| 精确车型、发动机和配置适配 | 未完成正式审核 | 熟悉车型的维修审核者 |
| P0299 对应正式诊断计划与分支依据 | 当前仅 FACT + EDITORIAL/DEMO 组合 | 维修审核者 |
| 完整位置/方法/工况/规格 | 部分页面已整理，仍非正式资格 | 资料提供者 + 维修审核者 |
| 处理后复核和真实完成标准 | 当前 DS-02/03 为合成阈值 | 维修审核者 |
| 实车效果 | 未验证 | 用户后续明确安排的实车验证 |

R1 继续只交付 synthetic 参考旅程。不能因 R1 路径跑通而把上述缺项标为满足；资料准备从本记录持续跟踪，但不在 R0/R1 扫描全机或自动导入用户其他目录。

## 9. R0 验证结果与停止点

- 已完成文档结构、路径和所引用当前文件存在性核对；恢复记录原先不存在，本次为首次创建。
- 已对照源码确认第 2.2 节缺陷和第 5 节参考旅程来源语义。
- 已只读核对 Git、运行记录与端口；没有输出凭据值。
- 本轮模型调用数 0，搜索调用数 0；未做自动化测试或独立审核。

**R0 到此停止。下一动作只能由用户明确安排 R1。**

## 10. R1 实施结果与体验停止点（2026-09-22）

状态：`IMPLEMENTED_NOT_ACCEPTED`。

- 已落地 conservative 病例模式、`policy_version`、协议 v2 冻结快照与 `content_hash`、历史 `requires_review` 门禁；`0014_conservative_protocol_r1` 已用于现有体验库。
- 表单和路由由同一冻结协议的稳定 `option_id` 派生；浏览器只提交 option/结构化观察，transition 仍由服务端决定。
- CHK-05 → CHK-06 → CHK-07 → CHK-11 能到 `AREA_SUMMARY_DEMO_PASS`；not_found、未完成、残余异常、复检不足、最终不完整及 unavailable 均有明确 handoff/terminal，不再伪造 CHK-07/08 后继。
- unavailable 保存协议 id/version/hash/check 身份，并能以 `HANDOFF_UNAVAILABLE` 形成有内容区域卡；最终报告门禁保持未就绪。
- conservative worker 只走冻结协议；本轮定向集成和两条浏览器旅程的 `tool_call_count=0`，未调用真实模型。
- 最小验证结果：协议静态单元测试 `3 passed`；现有 DKVB 定向集成 `1 passed`；OpenAPI/前端类型已重新生成且 typecheck 通过；两条浏览器路径均提交到最后终点。
- 现有体验实例保持在 `http://localhost:5215/`；历史病例搜索已停留在 `R1 DEMO`，最上方两条 `draft rev 0` 病例留给用户亲自体验。资料明确为 `synthetic=true`、`formal_usable=false`。
- 未运行全仓回归，未建立独立审核任务，未新增演示端口，未进入 R2；本节不表示用户接受、实车验证或真实资料资格满足。

**R1 到此停止，等待用户亲自体验和接受决定。**

## 11. R1-UX-01 产品主路径恢复实施结果

状态：`IMPLEMENTED_NOT_ACCEPTED`。

### 11.1 实际变更

- 创建前资格校验：保守模式只接受“虚拟探岳 DKVB 演示台架 / 2020 / EA888 Gen3B DEMO / DKVB-DEMO / P0299”，并在写入病例前检查全部受控协议原文片段；不支持场景返回 `CONSERVATIVE_SCENARIO_UNSUPPORTED`，资料不完整返回 `CONSERVATIVE_MATERIAL_MISSING`，均不留下空病例。
- 首页只呈现一个当前支持场景和一个创建主操作；自由模式明确为“R3 开发中”，本轮未新增 `web_enabled`。
- 病例快照增加服务端派生的 `experience` 分类；历史页默认加载并按“可继续 / 等待补充 / 已完成 / 建议重新开始 / 历史参考”分组，后面三类折叠，不再用裸 `status`、`revision` 作为主文案。
- 工作台用协议终点和体验分类覆盖原始状态：完整终点显示“演示诊断路径已完成”，unavailable 显示“病例已暂停，等待补充检查条件”，普通失败显示“本次运行无法继续”；服务端状态、UUID、revision、epoch 和 terminal code 只在技术详情中显示。
- 终点与失败页提供“返回病例列表 / 从支持场景重新开始 / 查看已保存观察”恢复操作；登录输入会去除首尾空白和误带的单个反引号。
- 两条干净体验病例已建立且未启动：`【待体验】R1 完整路径`（`bbbecf53-1aee-49f9-9855-5b3e3d0814b0`）和 `【待体验】R1 无法检查路径`（`e7561a8f-9534-4c94-a7f5-93c642a70457`）。

### 11.2 最小验证结果

- 创建门禁反例：不支持车辆得到 HTTP 422 / `CONSERVATIVE_SCENARIO_UNSUPPORTED`，前后病例数不变。
- 协议静态单元测试：`3 passed`；DKVB 直接相关集成测试：`1 passed`，覆盖完整协议与 unavailable，未调用真实模型。
- 前端直接相关测试：`3 files / 16 tests passed`；TypeScript typecheck 通过；OpenAPI 与生成类型已更新。
- 浏览器路径：历史分类可理解；既有完整病例到“演示诊断路径已完成”；新建验证病例只有“开始诊断”主操作且刷新后恢复 CHK-05；提交 unavailable 后到明确暂停终点，原因和已保存观察在刷新后仍存在；历史筛选可恢复该病例。
- 体验实例复用原端口并保持运行：Web `5215`、API `8215`、MCP `8315`、worker 均存活。浏览器停留在历史页的 `【待体验】R1` 两条病例。
- 未运行全仓回归、未建立独立审核任务、未新增端口、未进入 R2、未调用真实模型。一次定向集成测试因缺少隔离数据库环境失败、一次因临时目录落在旧项目边界失败；修正为现有隔离测试库和仓库 `.local-data` 后通过，失败事实保留。

实施/验证/自审耗时为本轮交互内约 1 小时以内（估计）；实际模型调用 0，联网搜索 0，token 统计未知。没有独立审核，本节仅记录执行者自检。

**R1-UX-01 到此停止。当前版本等待用户亲自体验，不进入 R2。**

## 12. R1-UX-02 受控诊断交互重构实施结果

状态：`IMPLEMENTED_NOT_ACCEPTED`。

### 12.1 修改文件与实现

- `backend/app/agents/trusted_protocol_v2.py`：协议版本提升为 `2.1.0`，为每个冻结检查增加任务摘要、原因、操作步骤、完成后说明、依据适用范围/限制和片段进度；CHK-07 增加“复检恢复 / 仍然增压不足 / 数据不足”三个明确标注 synthetic 的演示场景。旧 `2.0.0` 绑定仍在批准列表中，仅用于保持历史快照可执行。
- `backend/app/services/protocol_service.py`：CHK-07 缺省时由服务端生成稳定复检记录编号；CHK-11 从最近一条有效 CHK-07 观察复制三帧目标/实际压力并重新校验；terminal 带回冻结来源引用，transition 仍只由服务端根据稳定 `option_id` 和结构化字段决定。
- `frontend/src/formal/diagnosis/types.ts`、`WorkbenchParts.tsx`、`presentation.ts`、`frontend/src/formal/pages/WorkbenchPage.tsx`、`frontend/src/formal.css`：实现任务式说明、进度条、结果按钮、CHK-07 预设/手工三帧表、即时差值与格式提示、CHK-11 引用摘要、折叠技术字段、可读观察历史和结构化演示小结。
- `frontend/tests/wp15-workbench.test.tsx`、`tests/unit/test_conservative_protocol_r1.py`、`tests/integration/test_dkvb_trusted_protocol.py`：只调整直接相关断言；集成路径改为验证自动编号、CHK-11 服务端复用和 terminal 来源引用。

依据摘要直接来自病例绑定时冻结的协议 `presentation`，与协议版本和 `content_hash` 一同进入快照；前端只负责展示，不根据标题或按钮文字推断路由。原先逐条匿名“查看依据 1…5”改为一个“查看资料原文与出处”入口，抽屉按 evidence id 合并展示来源名称、支持关系、资料形式、定位和失效状态。

单一协议动作由页面自动选中，不再渲染成单选框。真正互斥的结果使用结果按钮；普通非协议表单仍保留原有单选兼容。CHK-07 的三种演示场景自动填入表格但明确标为 synthetic，手工模式逐帧显示 `hPa absolute`、目标值、实际值、差值和即时判断；复检编号不出现在用户输入区。CHK-11 页面显示被引用记录编号和三帧摘要，用户只确认症状、P0299、处理复核和冲突四项新增事实。

片段进度只显示“定位局部泄漏 → 模拟处理 → 处理后复检 → 最终复核 → 演示小结”，并持续声明不是完整汽车诊断。完成小结分为“已观察到 / 本片段支持的判断 / 本片段不能证明 / 后续操作”，最终报告仍保持不可生成。

### 12.2 真人体验入口

- Web：`http://localhost:5215/history`，已停留在筛选 `R1-UX-02` 的历史页；复用 API `8215`、MCP `8315` 和现有 worker，没有新增端口。
- `【待体验】R1-UX-02 完整路径`：`37352a78-82e7-4ad8-85c9-c3979c687ac6`，已启动并停在第一项定位观察。
- `【待体验】R1-UX-02 手工三帧路径`：`cac07821-9a78-4fd6-85ff-0bde376a1bfd`，已准备到 CHK-07，用户可直接选择“手工录入复检数据”。

### 12.3 最小验证结果

- 协议展示/完整出口单元测试：`3 passed`。
- 现有 DKVB 定向集成：`1 passed`；覆盖 CHK-05→06→07→11、自动复检编号、最终数据复用、unavailable、终点和既有安全反例，`tool_call_count=0`。
- 工作台直接相关组件：`1 file / 16 tests passed`；TypeScript typecheck 通过。协议展示仍位于现有通用 validation JSON 中，本轮没有 OpenAPI schema 变化，因此未重新生成 OpenAPI。
- 真人浏览器路径 1：使用“复检恢复”到达“本次增压空气系统演示复检已完成”，刷新后四条观察、复检编号、三帧引用、小结、合并资料入口均存在，最终报告仍禁用。
- 真人浏览器路径 2：手工输入三帧后即时看到差值和单位，完整提交后由服务端进入“残余增压不足，下一方向为调节机构检查”的明确 handoff。
- 初次复用旧测试环境时分别遇到缺少数据库设置、Windows 临时目录权限和旧环境来源读取失败；未扩大测试，改用项目已有的唯一隔离库定点脚本后通过。

### 12.4 尚未解决的问题与停止点

- 本轮仍仅是 `DKVB/P0299 增压空气系统局部泄漏处理与复检演示片段`；资料继续为 `synthetic=true / formal_usable=false`，不能代表真实车辆、完整故障树、实车效果或正式维修结论。
- 真实资料资格、其他车型/故障、自由 AI 模式、联网搜索和 `web_enabled` 均未处理；`web_enabled` 继续推迟到 R3。
- 未运行全仓回归，未新建独立审核任务或端口，未调用真实模型，未进入 R2/R3。本状态不表示用户接受。

**R1-UX-02 到此停止，保持必要体验服务运行，等待用户亲自体验。**

## R1-FLOW-01 DKVB/P0299 保守模式全流程实施结果

状态：`IMPLEMENTED_NOT_ACCEPTED`。

- 新增冻结协议 `3.0.0`，入口改为 CHK-00，覆盖 CHK-00—CHK-11、一次定位补充、`unavailable`、内容化 CHK-10 交接和 AREA_SUMMARY；稳定 `option_id` 由服务端决定路由。旧 `2.0.0/2.1.0` 继续只按各自快照解释，历史页标记为“旧版协议参考”。本轮未增加 `web_enabled`。
- CHK-03/CHK-07 使用同次三帧 `hPa absolute` 合成记录。CHK-07 直接恢复时 CHK-11 复用 `after_air_repair`；CHK-09 完成后 CHK-11 强制新增 `after_control_setup` 记录和新 run id，不覆盖 CHK-07 残余增压不足历史。
- 前端改为全流程任务/进度表达，提供静态可信度场景、负荷三帧场景与手工录入、空气路径/调节机构结构化观察、受控执行、交接说明和区分最终数据来源的完整小结。实际已完成进度来自有效观察，不把跳过节点显示为已完成。
- 浏览器已实际验证三条参考路径：最长路径 `CHK-00→01→02→03→04→05→06→07→08→09→11→AREA_SUMMARY`；泄漏处理后直接恢复 `CHK-00→…→07→11→AREA_SUMMARY`；测量不可信 `CHK-00→01→02→10→HANDOFF_CONSERVATIVE`。三条路径均为 deterministic synthetic 协议，未调用真实模型。
- 定点验证：协议单测 `4 passed`；TypeScript `tsc --noEmit` 通过；浏览器三路径通过。Vite build 与定向 Vitest 都在写既有 `node_modules/.vite-temp` 时遇到 Windows `EPERM`，未为此扩大权限或改跑全仓回归；现有 5215 开发服务已通过实际浏览器加载并运行修改。
- 真人体验病例（均绑定 `3.0.0`、停在 CHK-00、观察数 0）：最长完整路径 `c7074c21-6241-40dd-b58f-15daca2c5812`；泄漏处理后直接恢复 `d1fe68c0-6390-4961-9da0-2c8bfb9f9576`；测量不可信交接 `c0c40173-09ba-4c8a-ab3b-917379571a43`。
- 体验环境继续复用 Web `5215`、API `8215`、MCP `8315` 和现有 worker；未新增端口、未新建独立审核任务、未运行全仓回归、未进入 R2/R3、未调用真实模型。资料仍为 `synthetic=true / formal_usable=false`，不代表真实车辆验证或正式维修结论。

**R1-FLOW-01 到此停止，等待用户亲自体验，不进入后续工作包。**

## R1-FLOW-02 病例数据继承与任务页面重构实施结果

状态：`IMPLEMENTED_NOT_ACCEPTED`。

- 病例创建事务现在一次性冻结接诊快照、资料绑定、协议 `3.1.0` 绑定、系统 CHK-00 事实及首个 CHK-01 任务；病例创建后直接处于 `waiting_input`，刷新不会重复创建任务。接诊快照包含车辆、故障描述、故障码、诊断模式、证据策略和 synthetic 边界，且与用户后续观察分开显示。
- 冻结协议 `3.1.0` 从 CHK-01 开始；保留 `3.0.0` 只解释既有快照并在历史页标为“旧版全流程参考”。CHK-01 只补充症状条件、其他故障码、近期管路作业和说明，不重复要求用户录入病例创建页已有字段。协议每一步使用稳定 `option_id`、独立任务标题/问题/操作/记录/结果预告及依据性质，服务端继续决定路由。
- 任务页在 CHK-01 使用单列布局和只读病例摘要；后续显示五阶段进度、当前任务、系统接诊事实与用户观察。区域名称在 CHK-01—03 显示“病例与测量确认”，从 CHK-04 起显示“增压系统检查区域”。`unavailable`、测量不可信交接、完整 `AREA_SUMMARY` 和刷新恢复均保留。
- 数据层新增 `cases.intake_snapshot` JSONB 与 `intake_snapshot` 观察类型，迁移头为 `0015_r1_flow_02_intake_snapshot`；OpenAPI 与前端生成类型已经同步。相关服务支持共享事务连接，避免病例、资料、协议和首任务出现半完成状态。
- 定点验证：协议单元测试 `4 passed`；TypeScript typecheck 通过；迁移库为 `0015_r1_flow_02_intake_snapshot (head)`。只读 API 核对两条病例均为 revision 1、`waiting_input`、协议 `3.1.0`、当前 CHK-01、且只有一条系统接诊事实，CHK-01 用户字段没有被病例页数据伪填。
- 浏览器参考路径一实际完成 `CHK-01→02→03→04→05→06→07→08→09→11→AREA_SUMMARY_DEMO_PASS`，验证两个任务步骤的“资料原文与出处”入口、控制设置后新复检记录、完整小结及刷新恢复。参考路径二实际完成 `CHK-01→02→10→HANDOFF_CONSERVATIVE`，验证测量链不可信说明、保守交接、已保存事实及刷新恢复。
- 两条体验病例：最长路径 `cde9d409-21cf-432d-bb06-db20f59980e8`；测量不可信交接 `6eb4e3d9-da47-4ca7-bba9-392160efe74b`。历史页可用 `R1-FLOW-02` 筛选找到二者。
- 体验环境继续复用 Web `5215`、API `8215`、MCP `8315` 和现有 worker。未运行全仓回归、未新建独立审核任务或演示端口、未调用真实模型、未新增 `web_enabled`、未进入 R2/R3。资料仍为 `synthetic=true / formal_usable=false`，不代表真实车辆验证、正式维修结论或用户接受。

**R1-FLOW-02 到此停止，等待用户亲自体验。**

## R1-WORKBENCH-01 区域化诊断工作台实施结果

状态：`IMPLEMENTED_NOT_ACCEPTED`。

### 页面结构与服务端投影

- 病例页面已经由固定三栏替换为五段式工作台：紧凑病例标题、横向车辆与故障信息、诊断问题区域卡片、区域内部件/检查动作、全病例综合分析。空左栏、空右栏、空报告和“本区域尚无结论”占位不再渲染；技术版本、revision、epoch 和 terminal code 继续降级到技术详情。
- 新增 `GET /api/v2/cases/{case_id}/workbench-view`。`WorkbenchViewService` 只读取病例快照、冻结协议、当前有效观察、当前检查和当前 epoch 终点，派生区域、部件、动作、锁定原因及综合分析；不新增事实表、完成布尔值或第二套状态机。前端点击卡片只改变本地查看选择，只有当前服务端动作可以提交。
- 车辆与故障区继承 `intake_snapshot`，集中展示车型、VIN、年款、发动机系列/代码、故障描述、故障码、症状条件、近期维修和其他故障码；未知值显示“未提供”。车型、发动机或故障码实质更正仍提示重新建立病例，不静默改变协议适用范围。
- 宽屏采用自适应全宽网格，区域卡片自动换行，区域详情为部件导航与动作区；两个窄屏断点依次收敛为较少列和单栏。状态同时用文字与图标表达；完成动画只在 session 内首次由非完成转为完成时播放，刷新后不会重复。

### 区域、优先级和完成规则

- 区域 A“病例与测量确认”映射 CHK-00—03；区域 B“增压空气通路”映射 CHK-04、CHK-05、CHK-05-SUPPLEMENT、CHK-06、CHK-07；区域 C“增压调节机构”映射 CHK-08—09；区域 D“其他方向与保守交接”映射 CHK-10 / unavailable / handoff；区域 E“最终复核”映射 CHK-11 和终点小结。
- 排序只显示“建议优先级 1—5”。依据是 P0299、有效观察、冻结协议顺序和前置条件；没有百分比或故障概率。区域 B 在测量链确认后开放，区域 C 只在无漏点或处理后仍有残余增压不足时开放，区域 D 在测量/资料/执行条件不足时开放，区域 E 只在路径具备最终复检条件时开放。
- 区域与部件状态按有效观察、当前检查、终点和未解决异常派生。只有服务端已经确认该区域所需动作完成且没有对应未处理冲突时才显示勾选；交接区域显示“已交接”而不是失败。局部泄漏定位部件同时展示 CHK-05 与一次补充动作，未到达动作只能预览，不能提前提交。

### 综合分析与更正回退

- 综合区只汇总当前 epoch 的有效观察：已确认事实、已处理问题、仍存在异常、未检查项和建议下一步。诊断中只显示“阶段性诊断总结”；达到 AREA_SUMMARY 条件后才显示受限的“演示诊断总结”和实际发生过的维修/复检流程。始终保留 `synthetic/DEMO`、非实车验证、非正式换件建议和正式最终报告不可生成的边界。
- 浏览器中把最长路径的 CHK-07 从“仍然增压不足”更正为压力恢复后，原观察仍保留，服务端产生新 epoch；区域 C 从已完成撤回为 `0 / 2` 且未开放，CHK-09/旧 CHK-11 不再计入当前小结，页面返回新的 CHK-11 当前动作。撤回不是前端自行推断。

### 修改文件

- 后端：`backend/app/services/workbench_view_service.py`、`backend/app/domain/schemas.py`、`backend/app/api/cases.py`、`backend/app/main.py`。
- 前端：`frontend/src/formal/diagnosis/RegionalWorkbench.tsx`、`frontend/src/formal/pages/RegionalCaseWorkbench.tsx`、`frontend/src/formal/pages/WorkbenchPage.tsx`、`frontend/src/formal/diagnosis/types.ts`、`frontend/src/formal.css`、`frontend/src/generated/api-schema.ts`。
- 契约、验证和体验准备：`docs/api/openapi.wp14.json`、`tests/unit/test_workbench_view_projection.py`、`scripts/r1_experience_seed.py`。

### 病例与最小验证

- 验证参考病例：最长路径 `4f1b220b-b00f-4dab-b0b1-30a8fd6c11bb`；测量不可信交接 `f435fb3a-bce3-4bde-a275-6266d0d9cda8`。
- 未操作体验病例：`【待体验】R1-WORKBENCH-01 最长路径` 为 `6d83cce9-f7f7-4e2f-96a2-de52069d2aee`；`【待体验】R1-WORKBENCH-01 保守交接` 为 `2b0208d8-501e-4cd7-be0b-b8aba4b3ab9e`。两者都只包含病例创建时的系统 intake 事实，停在 CHK-01，未提交用户观察。
- 定点单元测试 `9 passed`：覆盖五区域映射、锁定/开放、保守交接、最终完成及既有 `3.1.0` 协议；唯一警告是沙箱不能写 `.pytest_cache`，不影响测试结果。TypeScript typecheck 通过，OpenAPI 漂移检查通过。
- 浏览器最长路径实际经过 CHK-01→02→03→04→05→06→07→08→09→11→AREA_SUMMARY，验证区域 C 动态开放、区域勾选、演示小结、刷新恢复和 correction 回退；测量异常路径实际经过 CHK-01→02→10→HANDOFF_CONSERVATIVE，验证区域 D 交接、后续锁定、缺项说明、无最终维修方案和刷新恢复。两条待体验病例均在浏览器核对为未操作。

### 未解决问题与停止点

- 仍仅覆盖冻结协议 `3.1.0` 的 DKVB/P0299 synthetic 演示范围；真实资料资格、实车效果、其他车型/故障、自由 AI 模式、网络补充和 `web_enabled` 均未处理。
- 正式最终报告门禁继续关闭。本轮未运行全仓回归，未调用真实模型，未进入 R2/R3，未新增端口、独立审核任务、封存包或大体量测试产物。
- 体验环境继续复用 Web `5215`、API `8215`、MCP `8315` 和必要 worker。本状态不表示用户接受。

**R1-WORKBENCH-01 到此停止，等待用户亲自体验。**

## UI-FREEZE-01 区域—部件—动作工作台原型

状态：`DESIGN_PROTOTYPE_NOT_ACCEPTED`。

- 新增独立静态原型路由 `http://localhost:5215/design/workbench-v2`，使用纯前端 mock 状态演示“建议排查区域 → 部件 → 多个检查动作 → 综合诊断分析”；正式 `/workbench`、后端、病例、协议、数据库和模型均未改动或调用。
- 原型包含五个系统区域、部件选择、管路接头六动作闭环、结构化泄漏记录、动态开放/重排、区域完成动效、综合结论及初始/发现泄漏/处理后恢复/处理后仍异常/完成演示快捷场景。页面固定标明“界面交互原型 · 数据不会保存 · 尚未连接诊断协议”，所有结论均为 synthetic/DEMO。
- 代码集中在 `frontend/src/formal/design/workbench-v2/`，仅在 `frontend/src/main.tsx` 增加独立路径入口。交付截图位于 `docs/implementation/product-recovery/assets/ui-freeze-01/`。
- 最小验证：TypeScript `tsc --noEmit` 通过；浏览器实际验证区域/部件选择、逐动作推进、泄漏记录、残余异常重排、完成态综合结论、重置、1440 宽屏和 430 窄屏无横向溢出。未运行全仓回归，未新增端口，未进入后续工作包。

**UI-FREEZE-01 到此停止，等待用户亲自体验。**

## UI-FREEZE-02 工作台原型多区域交互状态机补全

状态：`DESIGN_PROTOTYPE_NOT_ACCEPTED`。

- 原型状态改为以 `area_id + component_id + action_id` 保存动作结果，并为每个部件维护独立当前动作；增压空气通路四部件、增压压力测量四部件和增压调节机构四部件均可按自身动作链操作、切换、查看与更正，不再存在仅 `pipe-connector` 可执行的分支。
- 空气通路部件可独立排查，管路接头保留结构化泄漏位置、模拟处理和复检；压力测量使用带 `hPa absolute` 单位的简化结构化字段，进度只来自实际记录，无法取得会进入保守提示；调节机构只在空气通路必要检查完成且存在残余增压不足或压力异常时开放，并按 V465 连接器、调节连接机构、引导设置、设置后复检逐级解锁。
- 区域进入状态明确区分 `ready`、`waiting_prerequisite` 和 `unconfigured`。涡轮增压器本体及其他动力系统方向固定显示“资料/协议尚未配置”，只允许查看缺失说明，不提供虚假动作或结果按钮。综合分析汇总不同区域/部件的正常、异常、无法取得和待排查状态，持续保留 synthetic/DEMO 边界。
- 最小验证：TypeScript typecheck 通过；原型状态机定点测试 `1 file / 3 tests passed`，覆盖部件隔离、顺序推进、区域解锁、更正回退及 waiting/unconfigured 区分；浏览器实际完成多部件切换、压力测量与保守交接、调节机构逐级解锁、两个未配置区域四条路径，并核对 430px 窄屏无横向溢出。
- 正式 `/workbench`、后端、API、数据库、正式病例和协议运行时均未修改；未调用模型或网络，未新增端口，未运行全仓回归，未进入 R2/R3。

**UI-FREEZE-02 到此停止，等待用户亲自体验。**

## UI-FREEZE-03 五区域全路径形态原型与综合分析收敛

状态：`DESIGN_PROTOTYPE_NOT_ACCEPTED`。

- 涡轮增压器本体与其他动力系统方向已接入同一套 `area_id + component_id + action_id` 原型状态机；两区各含五个可操作部件，并持续标明“synthetic 演示协议，仅用于验证界面与流程”。涡轮路径只输出线索或保守交接，其他动力路径只输出由已记录事实导出的方向建议。
- 三条主分支现为动态计算：空气通路和原症状均恢复时，下游显示“本路径不需要进入”；增压仍异常且调节机构未解决时开放涡轮路径；增压恢复但原症状仍在时开放其他动力系统路径。上游更正会即时重算入口，已失效分支记录保留为“历史演示记录，当前路径已改变”，但不再参与当前问题与建议。
- 综合分析收敛为五区域摘要、优先问题（默认最多三项）、待处理（最多三项）和一个主建议加可选次建议；动作明细移入“查看诊断记录”，区域摘要可按需展开。
- 最小验证限定为 TypeScript typecheck、单个状态机定点测试文件、五条浏览器参考路径和 430px 窄屏检查；正式 `/workbench`、后端、API、数据库、协议运行时均未修改，未调用模型或网络，未新增端口，未运行全仓回归，未进入 R2/R3。

**UI-FREEZE-03 到此停止，等待用户亲自体验。**

## UI-DKVB-CONTENT-01 探岳维修资料1 v2 原型接入

状态：`DESIGN_CONTENT_PROTOTYPE_NOT_ACCEPTED`。

- `/design/workbench-v2` 保留既有页面结构和视觉方向，内容层切换为 `探岳 DKVB / P0299 深度诊断专题资料包 v2`：7 个阶段、5 个主区域、34 张主题卡、78 个稳定问题 ID、359 个显式结构化选项、26 个核心结果状态、12 条关键路由和 12 条演示病例全部进入统一前端数据层。
- 顶部提供 12 病例选择器、“从空白状态开始”和“重置当前病例”；病例切换先显示确认层，不静默覆盖。S0 接诊可展开和更正；S1—S5 保持五区域卡、部件列表和问题工作区；S6 单独保存处理与复检记录。
- 压力阶段支持环境/G31/G71静态绝对压力、自动差值与离群分类，以及三帧转速、负荷、驾驶请求、目标/实际绝对压力、自动差值和趋势语言；30/250/150 hPa 均明确标记为专题演示规则。
- 16 张本地维修手册/电路图 PNG 和 3 张 SVG 示意图复制到 `frontend/public/workbench-v2-assets/`，按具体资料名称提供页面内查看、缩放和新标签原图入口，并显示中文来源标签。
- 路由使用最新有效事实计算。更正上游结果不会删除下游填写记录；失效记录改为“历史记录，当前路径已改变”，不再进入当前问题、解释和建议。综合区收敛为已确认事实、已发现问题、尚待排查、当前解释和建议下一步。
- 最小验证限定为 TypeScript typecheck、单个内容状态定点测试文件、78 ID/12 病例/19 图片计数、C01/C04/C09/C10 浏览器路径、上游更正与历史保留、桌面和430px布局及控制台检查。未修改正式 `/workbench`、后端、API、数据库或迁移，未调用模型或网络，未进入 R2/R3。

**UI-DKVB-CONTENT-01 到此停止，等待用户亲自体验。**

## WORKBENCH-V2-INTEGRATION-01 首条正式病例接线

状态：`IMPLEMENTED_NOT_ACCEPTED`。仅虚拟 DKVB/P0299 合成病例的 V2 正式入口与 AIR-07 → AIR-15 → RET-01 → RET-04 纵向路径已接通服务端保存、更正和恢复；其余专题块仍按待接入显示。真实资料、正式 AI 和最终报告门禁边界不变。实际 case_id、浏览器核对、运行文件与待退役文件见[实施记录](WORKBENCH-V2-INTEGRATION-01.md)。到此停止，等待用户亲自体验。

## WORKBENCH-ADAPT-A01 新工作台专题候选包（仅阶段 A）

状态：`CANDIDATE_READY_NOT_ACCEPTED`。在不覆盖当前冻结专题与既有病例绑定的前提下，已隔离生成包含 78 题、359 选项、五区 34 卡、14 张长内容卡、19 图、26 结果和 12 路由的[机器可读候选包](../../../backend/app/topics/candidates/tanyue-dkvb-p0299-a01-candidate.json)，并完成 ID、依赖、来源/图片、派生无环及代表性事实的轻量校验。逐题阶段/前置条件、关键冲突、首次 AI 与最终报告门禁边界、阶段 B 最小数据库/API 接线和未解决项见[内容映射与运行契约](WORKBENCH-ADAPT-A01.md)。**本轮未启用新运行逻辑，页面行为未改变**；未迁移数据库、调用模型或进入阶段 B/C/D，等待用户确认。

## WORKBENCH-ADAPT-B01 新专题全部问题正式接线（仅阶段 B）

状态：`IMPLEMENTED_NOT_ACCEPTED`。新 `2.2.0-b01` 合成专题已对新病例启用：78 题按用户观察、服务端派生、条件操作或处理后复检处理；五区独立记录、不可变更正、完整历史与分页、服务端综合投影及原报告门禁保留。5215 正式入口可创建专题病例；干净体验病例和定点验证见[阶段 B 实施记录](WORKBENCH-ADAPT-B01.md)。AI 尚未接入，规则摘要不冒充模型建议；未进入阶段 C/D，等待用户亲自验收。

## WORKBENCH-UX-03 选项自动保存与页面减负

状态：`IMPLEMENTED_NOT_ACCEPTED`。正式 V2 问题块移除通用观察依据、更正原因及独立保存按钮；普通单选点选即保存、改选追加更正，多选短暂防抖保存完整集合，结构化字段齐备后在失焦时保存。无法检查可不填原因，服务端如实标记“原因未提供”；空多选保持“未选择”，不解释为正常。每题显示保存中、已保存或失败重试，跨题写入串行协调病例版本，失败草稿留在页面。各模块重复的“为什么检查／位置与边界”大卡片已移除，独有资料入口移至模块标题附近。独立 DEMO 浏览器病例验证了首次保存、改选历史、快速多选、数值校验、受控操作失败重试、刷新恢复、双窗口版本冲突与保留草稿后重试、图片入口；用户体验用空白病例为 `f8ab9827-e839-4c60-b5b1-2ff654a6752f`。未调用模型、未改旧数据或进入 AI 接线，等待用户体验。

## WORKBENCH-UX-04 输入框手动保存与顺序展开

状态：`IMPLEMENTED_NOT_ACCEPTED`。正式 V2 中需要文字、原因、测量或复检字段的选择改为单题手动“保存”；输入与失焦不提交，改写当前有效值仍追加更正历史，同一次复检更正不新建轮次。纯选项继续点选保存，多选防抖保存后由“下一项”结束选择；仅服务端确认后按本模块、同区域下一模块的显示顺序展开未完成可操作题，失败与主动切换不抢导航。五区共用“纳入本轮排查计划”面板已移除；服务端从接诊计划和专题已配置规则计算新增必需项，浏览与普通可选观察不扩大整区计划，旧病例既有计划保留。独立验证病例 `a6ded35e-88fe-4483-8cb3-ea64f0b64310` 核对了原因/数值失焦不保存、手动保存与更正刷新、纯选项及跨模块推进、多选不提前离开、受控条件失败留稿；干净体验病例 `aebbde34-35c2-4b54-af3e-aa2cf83d88d0`。TypeScript typecheck 与 B01 定点测试通过；未接 AI、未清旧数据、未进入后续工作包，等待用户体验。

## WORKBENCH-UX-05 取消自动滚动、精简状态与综合分析折叠

状态：`IMPLEMENTED_NOT_ACCEPTED`。正式 V2 保存成功后仍展开下一道可操作题，但不再调用平滑滚动，也不自动收起刚完成的问题；题目列表单独关闭浏览器滚动锚定，手动滚动保持可用。排查题草稿不再显示“未保存”徽标/占位文案，内部草稿、校验、保存失败重试和离开提醒不变。综合分析四栏分别折叠：长列表默认前三条、长段落默认约六行，保留总数和全部服务端内容，关键冲突与安全原因优先可见；投影刷新不重置展开状态，切换病例重置。独立合成病例 `3a435826-b534-4d7b-b933-54afd9645c47` 在 5215 页面验证纯选项与数值题保存后下一题展开且 `scrollY` 不变、必填校验、受控操作保存失败留稿、多栏独立展开/收起和刷新保留、430px 无横向溢出；TypeScript typecheck 通过。所附参考录像未能实际观看，本轮不声称复现视频全部操作。未改诊断规则、检查计划、数据保存方式或 AI，等待用户体验。

## WORKBENCH-ADAPT-B02 条件判断、完成度与复检轮次

状态：`IMPLEMENTED_NOT_ACCEPTED`。新 `2.2.1-b02` 版本隔离修复九个条件操作的稳定选项校验、无法取得时的派生状态和首次分析交接准备、RET-01 未处理不建轮次及处理更正依赖、固定卡片顺序下的动态推荐。旧 B01 病例不重绑，既有 UX 操作不回退；AI 未接入，最终报告门禁未放宽。干净体验病例与实际服务端、浏览器定点验证见[同一阶段 B 实施记录中的 B02 小节](WORKBENCH-ADAPT-B01.md)。仅阶段 B，等待用户验收，不进入 C/D。

## WORKBENCH-ADAPT-C01 正式病例建议接线（仅阶段 C）

状态：`IMPLEMENTED_NOT_ACCEPTED`。用户接受 B02 的范围仅为合成专题工作台体验和执行流程，不代表真实车辆诊断能力验收。现有 AI 区域接入服务端冻结快照、专题资料正文、异步任务、结构校验与持久化建议；开发实例仅启用模型替身，未调用真实模型。事实更正使旧建议过期；建议只导航到实际处理，不自动写维修事实，独立复检沿用 B02 轮次。资料范围、模型预算、定点和浏览器验证、体验病例及限制见[阶段 C 实施记录](WORKBENCH-ADAPT-C01.md)。最终报告门禁未放宽；不进入阶段 D，等待有限真实模型体验的另行授权。

## WORKBENCH-ADAPT-C02 真实调用前补齐与独立体验准备

状态：`IMPLEMENTED_NOT_ACCEPTED`。补上本地手册正文对应的有限 `action_id` 清单和服务端范围/引用/受控文字校验；否定表述不再仅因含“确诊/排除”被误拦，越界技术操作和参数仍保守拒绝。缺证据结果以可读题名导航到原始问题，旧分析继续可见且过期状态保留。通过正式 API 建立独立模拟气路病例 `cd369e59-694d-4ceb-9a55-42aaea8b9090`，只读预检完成；现有 5215 仍为替身模式，未发起本病例分析。资料范围、预算、定点/浏览器核对与真实调用前阻断见[ C02 实施记录](WORKBENCH-ADAPT-C02.md)。**本轮真实模型调用数为 0**；等待用户单独授权一次体验，不进入 C03/D。

## WORKBENCH-ADAPT-C03 首次真实模型体验：预检与一次调用

状态：`BLOCKED_BEFORE_MODEL_CALL`，2026-09-24。本轮用户授权最多一次真实生成，但只读核对发现仓库实际 `E:\Work\xiutu-v5\.env` 已有密钥、配置模型为 `deepseek-chat`；DeepSeek 当前官方 [模型列表](https://api-docs.deepseek.com/quick_start/pricing/) 仅列 `deepseek-flash` 与 `deepseek-v4-pro`，[V4 发布说明](https://api-docs.deepseek.com/news/news260424/) 明确 `deepseek-chat` 于 2026-07-24 退役不可访问。按“不擅自替换模型、配置有歧义即停止”边界，未切换模型、未开启真实模式、未提交病例分析、未产生付费调用。当前 5215 仍为替身模式；目标病例 revision 42、41 条均标明模拟的有效观察、B02 合成专题绑定，首次建议门禁允许但范围仅 `supplement_or_handoff`；已存在同 revision 的**替身**结果 `3a5bc5ed-d728-46fa-b630-0af859b97d9e`，不冒充真实结果。输入预览 33,646 字符、粗估 14,231 tokens，输出仍为 1,536 tokens。另发现直接 `load_settings(project_env=True)` 被现有 `.env` 的 `embedding_local_files_only` 值挡住；仅在只读核对中对该无关设置传入安全覆盖才确认密钥/型号，并未修改 `.env`。等待用户明确选择受支持型号及相应一次调用授权后，另行安全注入现有开发实例并复核预算；不自动重试或进入阶段 D。

### 用户指定 `deepseek-flash` 后的一次真实调用结果

用户随后明确选择 `deepseek-flash`，沿用本轮一次调用授权。2026-09-24 仅对独立合成病例 `cd369e59-694d-4ceb-9a55-42aaea8b9090` 的 revision 42 短时开启既有 5215/8215 实例的真实路径；密钥由项目 `.env` 在进程内读取，未修改或输出 `.env`，输出上限调整为 4,096 tokens。正式病例分析接口以幂等键 `c03-cd369e59-r42-20260924` 创建分析 `544360e8-dae4-47a6-96b6-57671577b012`，仍使用服务端冻结的 41 条模拟观察、派生/缺项及绑定专题的两段手册摘录，允许范围为 `supplement_or_handoff`。一次真实生成已从 `deepseek-flash` 返回，账本 `544360e8-dae4-47a6-96b6-57671577b012:1` 记录 `received`、`finish_reason=stop`、输入 15,028 / 输出 2,347 / 合计 17,375 tokens。发布校验随后以 `ANALYSIS_SCOPE_EXCEEDED` 拒绝结果，分析状态为 `failed` 且无有效建议正文；该代码可能对应受限范围内出现支持方向、处理操作或操作类型不符，未保留可据以确定具体哪一种的原始回复，不能把模型结果表述为已通过。病例 revision 仍为 42，原替身结果仍与本次真实失败分开。未降低校验、未改病例事实、未发起第二次生成。已停止短时真实模式并按原配置重启：API/Web/worker 存活，`XIUTU_C01_MODEL_MODE=stub`、`XIUTU_C01_REAL_AUTHORIZED=0`、运行实例密钥为空；普通点击不会调用付费模型。实际费用无可靠结算依据，不估算金额。**本次真实体验未成功发布建议；后续若要调整提示词或再试，需另行决定并单独授权新的付费调用。**

## WORKBENCH-ADAPT-C04 分析失败定位与输出契约修复

状态：`IMPLEMENTED_NOT_ACCEPTED`。在现有 `case_analyses` 上通过增量迁移 `0017_case_analysis_diagnostics` 加入唯一的受限 `diagnostic_json`，不改病例事实、旧建议、不可变观察或最终报告门禁。模型响应到达后、解析及业务校验前，先持久化原始响应的受限副本（UTF-8 最多 32 KiB，超限明确标 `truncated` 并保留全文哈希、原始长度与调用定位；常见凭据形态先遮盖）；随后分别写入解析概要、结构/业务校验阶段、稳定规则 ID、字段路径、允许范围、期望条件和限长实际值。诊断数据保留 30 天，过期读取拒绝，后续捕获时惰性清除；普通建议列表/工作台不返回原文。仅隔离 `APP_MODE=test`、已登录且拥有该病例的本地诊断操作员可经 `GET /api/v2/cases/{case_id}/analyses/{analysis_id}/diagnostic` 查看；未鉴权返回 401。诊断记录保存失败时停止发布，也不再次调用模型。旧 C03 分析 `544360e8-dae4-47a6-96b6-57671577b012` 保持原 `failed` 状态，该诊断接口返回 `not_retained`：**当时未保留模型响应，具体触发字段无法恢复**。

新提案契约版本 `case-advice-proposal-c04-v1` 随新快照冻结；`supplement_or_handoff` 的模型 schema 明示 `supported_directions` 为空、步骤只可 `check/handoff`，其他范围只暴露适用种类及冻结清单中的 action ID；未知范围拒绝。模型不再逐字提供受控操作四段正文，只提交 `action_id`、有效观察依据及可选来源；服务端从该次快照的 `action_catalog` 校验范围、事实和来源后填入动作、前提、复检与停止条件，再执行原有最终建议校验。越界内容不静默删除，旧版已发布 `CaseAdviceDraft` 原样读取。普通 AI 区仅显示简明失败原因，不展示未经校验的操作原文。

定点人工样例（**不是** C03 已丢失的回复）验证了两个不同的范围规则、冻结操作组装及未知 ID/错来源/缺事实拒绝、解析与结构错误单次捕获、存储失败阻止发布、否定表述和越界断言；C01/C02/C04 定点合计 27 passed，前端 TypeScript typecheck 通过。原 WP15 合成库迁移到 `0017` 后，旧成功替身建议仍为 `current`、C03 真实失败仍为 `failed` 且未被补造内容；实际 API 验证普通视图不含诊断原文、授权诊断读取为 `not_retained`、未鉴权为 401。沿用 5215，真实模式和付费授权仍关闭。**本轮真实模型调用数为 0**；这些人工样例不能证明任意自然语言安全，也不代表已修复 C03 当次模型输出。

## WORKBENCH-ADAPT-C05 一次真实体验：环境阻断前的准备

状态：`BLOCKED_BEFORE_MODEL_CALL`，2026-09-24。用户授权一次 `DeepSeek / deepseek-flash` 真实生成，目标仍为独立 DEMO 病例 `cd369e59-694d-4ceb-9a55-42aaea8b9090`。本轮只在现有正式路径增加精确病例、revision、幂等键的 C05 一次性授权保护；旧 C03 失败不占用 C05 窗口，而任何采用 `dkvb-c04-v1` 契约的真实尝试（包括失败）均阻止再次创建。worker 也独立检查病例、revision、模型及契约版本，默认实例仍为 `stub`、授权 `0`、运行密钥为空。项目 `.env` 的密钥通过原有配置加载器确认存在，未输出或修改密钥；定点 C04 测试 6 passed，默认配置与 C05 限定配置的无调用检查通过。

执行前发现原 5215/8215 实例均未运行，原 5433 数据库不可连接，Docker daemon 未启动；尝试启动 Docker Desktop 及其服务后，当前会话仍无法访问 daemon 或目标数据库。因此无法核对目标病例的**当前** revision、有效事实、在途任务和迁移状态，未开启真实模式、未提交分析请求、未生成新分析 ID、未调用模型。C03 记录未改。待用户恢复原 Docker/5433 后，必须重新只读预检；若病例内容变化无法解释或已有 C05 尝试，不得直接调用。本轮真实模型请求数为 **0**，临时真实授权未开启。此记录不是 C05 体验完成证明，不进入阶段 D。

### 用户通知恢复后的重试预检

Docker daemon 可访问，核对 `xiutu-v5-postgres-1` 属于原项目、配置期望 `127.0.0.1:5433:5432`，数据仍在原命名卷 `xiutu-v5_wp01_pgdata`。该容器虽然 `healthy`，但 Docker 的有效 `NetworkSettings.Ports` 为 `{"5432/tcp":[]}`，`docker port` 明确显示没有公开端口；Windows 进程连接 5433 超时。仅对这个容器重启、再按原 `deploy/compose.yaml` 重建（保留同一数据卷）仍未恢复发布。原 5215/8215 服务未启动，无法通过正式病例 API 核对 revision、事实、迁移和在途任务。因此再次停在**模型调用前**：没有新分析 ID，真实请求数仍为 **0**，未启用临时真实授权，也未修改病例答案。需先恢复原 5433 的有效端口映射，然后重新完整预检；不能借数据库容器内部脚本绕过正式分析路径。

### 定位转发冲突并完成一次真实请求

后续用户明确要求继续 C05 并允许仅重启 Docker Desktop 的 `docker-desktop` WSL 引擎。只读检查确认 Docker context 为 `desktop-linux`、Compose 与容器 `HostConfig.PortBindings` 均要求 `127.0.0.1:5433:5432`，PostgreSQL 在容器内接受连接；但有效 `NetworkSettings.Ports` 为空、Windows 侧无 5433 监听且 TCP 连接超时。Docker Desktop 后端日志具体报 `failed to expose port: listen tcp4 127.0.0.1:5433: bind: address already in use`；其 WSL 网络命名空间中 `dockerd` 占有该端口。按用户限定只终止 `docker-desktop` 发行版，随后启动原 `xiutu-v5-postgres-1` 容器，**本次没有再次重建容器、没有删除卷或改全局网络配置**。有效映射变为 `127.0.0.1:5433`，Windows TCP 与应用凭据实际连接通过。原命名卷 `xiutu-v5_wp01_pgdata` 保留；隔离库 `xiutu_test_wp15_browser_adb08e25` 含原病例 revision 42、41 条专题观察、`0017_case_analysis_diagnostics` 迁移及 C03 `failed` 分析。API、worker、5215 Web 从同一启动脚本/数据库配置恢复。

正式 API 只读预检：目标病例 `cd369e59-694d-4ceb-9a55-42aaea8b9090` 仍绑定 `2.2.1-b02` synthetic DEMO 专题，首次建议门禁允许、范围仅 `supplement_or_handoff`；无在途分析或此前 C04 契约真实尝试。服务端快照含 41 条模拟观察、手册摘录 `C01-SRC-CHARGE-AIR-P1` 与 `C01-SRC-CHARGE-AIR-P5`、一个受控气路检查 action；快照约 33.7k 字符，连同 schema 和系统提示的上界约 37.7k 字符，低于 48k。短时开启精确限定病例、revision 42、幂等键的 `DeepSeek / deepseek-flash` 模式，输出上限 4,096 tokens，通过正式 `POST /api/v2/cases/{case_id}/analyses` **只提交一次**，新分析 `68b6ee08-4ff3-47cc-8331-5deaca8add5c`、run `afaaf92b-7a77-4abc-9094-298ae54a8291`。

本次唯一模型响应正常返回（账本 `68b6ee08-4ff3-47cc-8331-5deaca8add5c:1`，`finish_reason=stop`；输入 15,253、输出 1,036、合计 16,289 tokens）。C04 受限诊断保留 1,928 字符原始回复，未截断，解析成功；业务校验在 `steps[0].source_ids` 以 `ANALYSIS_ACTION_SOURCE_MISMATCH` / `action.source` 拒绝：冻结 action 清单要求摘录 ID `C01-SRC-CHARGE-AIR-P1`，模型提案给出通用来源 `SRC-CHARGE-AIR` 和编辑性演示来源 `EDITORIAL_DEMO`，不能据此发布受控技术检查。仅能确认首个命中的拒绝点，不推定其他字段全部合格；受限回复未作为建议展示或病例事实。分析持久化为 `failed`、无有效建议内容；正式 API 重新读取仍如此。病例 revision 42、41 条观察与 C03 失败状态未变。实际费用无可靠结算依据，记为未知。**真实生成请求数恰为 1，未重试。** 完成后立即停止短时真实实例并恢复原 5215/8215/worker：`stub`、付费授权 `0`、运行密钥为空；后续普通点击不会付费。状态：`FAILED_VALIDATION_NOT_ACCEPTED`，等待用户决定是否另行修订输出契约并重新授权；不进入阶段 D。

## WORKBENCH-ADAPT-C06 受控操作契约与 C05 离线重放

状态：`IMPLEMENTED_NOT_ACCEPTED`。新增区分受控操作与自由检查/交接的 `case-advice-proposal-c06-v1`：受控操作只由模型提议 action ID 和有效事实，服务端从冻结清单填入类型、正文、条件、来源及复检并严格校验；额外字段不能被静默忽略。C04 旧快照和已发布结果保持可读，C05 已消耗的一次真实尝试不因版本升级重置。C05 原受限响应完整、哈希吻合；除原 `action.source` 拒绝外，离线检查还发现三条交接步骤缺正文、多处来源 ID 不是冻结摘录，另有需区分误报与实质越界的自由文本命中。机械转换副本因这些缺项未通过新结构校验，**未发布、未改 C05 failed 状态**。代码、差异、未检查边界和 18 项定点结果见[ C06 实施记录](WORKBENCH-ADAPT-C06.md)。**本轮真实模型调用数为 0，授权继续关闭**；不进入阶段 D。

## WORKBENCH-ADAPT-C07 建议输出契约收敛

状态：`IMPLEMENTED_NOT_ACCEPTED`。新冻结契约 `case-advice-proposal-c07-v1` 保留服务端受控操作组装，简化自由检查/交接为具体建议、理由及有效观察或缺项引用，不再强求每步都写维修后复检等不适用字段；正文或引用缺失仍拒绝。模型可引用来源明确限于实际提供正文的摘录；局部分句、已保存数值与安全禁止语的定点误拦修正，同时继续拒绝混合肯定换件、编造限值和清单外技术操作。旧 C04/C06 快照可读，C05 原失败与受限回复不改。30 项相关定点、前端类型检查和 5215 独立 DEMO 替身页面（刷新、依据跳转、过期）已验证；细节及体验地址见[ C07 实施记录](WORKBENCH-ADAPT-C07.md)。**本轮真实模型调用数为 0，真实调用授权关闭；新契约真实 AI 效果尚未验证。** 不进入阶段 D。

## WORKBENCH-ADAPT-C08 新契约的一次真实体验

状态：`FAILED_VALIDATION_NOT_ACCEPTED`。独立 DEMO 病例 `97812694-5339-4e59-badc-d87a9bc5c431` 的 revision 42 使用冻结的 `case-advice-proposal-c07-v1`，通过正式分析接口向 `DeepSeek / deepseek-flash` 发出**恰好一次**真实生成，输出上限 4096 tokens。分析 `9d38a39d-0c61-428a-beae-53316ce9ceb9` 的响应完整留存，输入/输出/总用量为 15,877/1,660/17,537 tokens；业务校验首先在 `steps[1].action` 以 `text.unsupported_operation` 拒绝，另有自由文本参数越界问题，因此未发布建议、未重试。病例原观察及旧替身结果不变，C03/C05 失败保持原样。短时真实授权和密钥注入已关闭，同端口恢复替身模式；实际费用未知。预检、诊断边界、31 项定点验证与修改见[ C08 实施记录](WORKBENCH-ADAPT-C08.md)。不进入阶段 D，等待用户决定后续修复范围。

## WORKBENCH-ADAPT-C09 分开分析、补记录与操作权限

状态：`IMPLEMENTED_NOT_ACCEPTED`。新冻结提案契约 `case-advice-proposal-c09-v1` 允许引用有效观察形成有限的观察方向，使用稳定问题 ID 引导补记录；具体现场检查仍只能由冻结 `action_catalog` 组装。区分病例读数、服务端派生值、编辑性演示阈值和有适用范围的手册限制；全局不安全表述仍整体拒绝，独立不合格类别仅在明确标记 `partial` 后可部分发布。逐字段复核完整留存的 C08 受限回复，原分析继续 `failed`，未改病例事实；五区资料盘点后未把登记或图片冒充送模正文，也未新增受控操作。39 项相关定点与前端类型检查通过，独立 DEMO 病例 `d109a875-70e9-46aa-a198-7c75048aa8b3` 经正式替身路径生成可持久读取的测试结果；初次浏览器尝试遇到会话未登录，下文记录了登录后实际页面核对。分类、资料映射、离线转换边界与风险见 [C09 实施记录](WORKBENCH-ADAPT-C09.md)。**本轮真实模型调用数为 0，真实授权关闭；新契约真实 AI 效果尚未验证。**

### 登录后页面收尾

用户登录后，已在正式 5215 Chrome 工作台实际点击核对：原 [C09 替身体验病例](http://localhost:5215/workbench/d109a875-70e9-46aa-a198-7c75048aa8b3) 明示非真实 AI、完整通过及非确诊方向；AIR-07 事实、P1 正文、AIR-14 补记录和图片查看入口可用，导航不写观察；刷新后结果仍在，综合区折叠独立。另建只用于过期测试的模拟病例 `41adbf6d-3c3d-41e9-8e87-62d8eb6c2d13`，浏览器改选后原建议持续标 `stale`，输入原因失焦不保存、点击保存才提交；原体验病例仍保持 revision 42/41 条有效观察。既有 C08 失败页只读显示 `failed`，未展示受拒原文。现有替身机制没有持久化 `partial` 样本，故部分发布页面尚未浏览器实测，不能把定点检查冒称为这一项通过。详情见 [C09 登录后验证](WORKBENCH-ADAPT-C09.md#登录后浏览器收尾验证2026-09-24)。本次无业务代码修改、真实模型调用数 **0**，真实授权仍关闭；状态保持 `IMPLEMENTED_NOT_ACCEPTED`，待用户体验。

### 部分发布最后一项补验

此前“没有持久化 `partial` 样本”是补验前状态。现已在仅隔离测试模式可用的固定替身场景下，经正式病例分析任务、提案解析、分层校验和持久化得到 [独立部分通过 DEMO 病例](http://localhost:5215/workbench/b794d917-d3bb-49fa-b39a-8ae88e3d9577)：分析 `87ba6d9a-df71-4acb-a620-f4ad77beef3f` 保留 AIR-07 有效事实支持的观察方向，拒绝清单外操作 `steps[0].action_id`（`action.known`），已发布操作步骤为 0；revision 42、41 条模拟观察及处理／复检记录未改变。已在正式 5215 Chrome 页面实际查看“模型替身／非真实 AI”“部分通过”及未发布原因，点击 AIR-07 可定位原事实，刷新后状态、原因和依据均恢复；被拒操作没有可执行步骤或处理入口。无凭据画面已在验收对话中展示。详情见 [C09 最后一项记录](WORKBENCH-ADAPT-C09.md#最后一项部分通过场景2026-09-24)。相关定点 9 passed，真实模型调用数 **0**、授权关闭；`partial` 浏览器缺口已补齐，状态仍为 `IMPLEMENTED_NOT_ACCEPTED`，新契约真实 AI 效果未验证。

## WORKBENCH-ADAPT-C10 C09 契约一次真实生成

状态：`FAILED_VALIDATION_NOT_ACCEPTED`。原 [C09 DEMO 病例](http://localhost:5215/workbench/d109a875-70e9-46aa-a198-7c75048aa8b3) revision 42 经正式分析任务向 `DeepSeek / deepseek-flash` **恰好发出一次**真实生成（输出上限 4096 tokens），分析 `b6ab0831-8c3c-4499-89a2-3a41e52e0b71`。响应完整留存，用量为输入/输出/合计 `17,206/1,951/19,157` tokens；业务校验于 `uncertainty` 字段的 `number.provenance` 拒绝，疑与编辑性演示阈值限定语被逗号分句有关，剩余内容不能据此认定合格。未发布真实建议、未改病例观察、未重试；费用未知。临时真实授权关闭，原服务恢复 `stub`/`paid=false`。正式 5215 页面登录后实测显示历史“真实模型生成”失败状态，刷新仍在，早先替身建议未覆盖。细节、证据和当前模式/历史生成方式的文案边界见 [C10 实施记录](WORKBENCH-ADAPT-C10.md)。不进入阶段 D，后续真实调用需另行授权。

## WORKBENCH-ADAPT-C11 C10 原响应离线全字段诊断

状态：`IMPLEMENTED_NOT_ACCEPTED`。用 C10 完整受限原文与原冻结 revision 42 快照，逐字段找到 **8 处明确误拦、1 处实质越界、1 处来源适用性不确定**。修复跨分句演示阈值、受控资料安全引述和既有题目补录的误拦，同时补上对全局 `retest_plan` 新现场压力采集指令的拒绝。原文修复前在 `uncertainty/number.provenance` 整体拒绝；修复后在 `retest_plan/text.unsupported_operation` **仍整体拒绝**，不能因方向和步骤独立探针通过便部分发布。脱敏对照仅在本机已忽略的 `.local-data`，不写有效建议。相关定点 19 passed；运行服务未重启，页面仍为原行为。详细分类、校验边界和离线产物见 [C11 实施记录](WORKBENCH-ADAPT-C11.md)。**真实模型调用数 0、真实授权关闭、C10 保持 failed、原响应及病例事实未改、未发布新建议**。停止，等待用户决定；不进入阶段 D。

## WORKBENCH-ADAPT-C12 复检依赖与分层发布

状态：`IMPLEMENTED_NOT_ACCEPTED`。在不改 C10 原响应与冻结快照的前提下，逐项确认其三条当前事实方向与前三条补记录、一条冻结受控检查均不依赖未授权的“重新采集压力帧”；该全局复检段现可**仅在独立且无缺失安全限制时**隔离，并明示 `partial` 与“复检方案未获支持”，不展示新采集指令。C11 的 P1 适用性疑点定位为 `steps[4].source_ids`：P1 只覆盖气路座合/泄漏，不能作为整段跨区交接的资料依据，故该步另被隔离。原 C10 同一原文/快照离线结果为 `partial`（3 方向、4 步保留，复检段与跨区交接不发布），**未写回**原 `failed` 分析。28 项相关定点与前端类型检查通过；独立 [C12 替身病例](http://localhost:5215/workbench/1ff861f8-745d-49af-bb1e-7b436e606d2c) 经正式 API 持久化 `partial` 且刷新读取一致，5215/8215 已加载 C12、保持 `stub`/`paid=false`。浏览器自动化在 URL 安全定位时停止，**页面实测与截图未完成**，不能冒称验收通过。细节见 [C12 实施记录](WORKBENCH-ADAPT-C12.md)。**真实模型调用数 0、真实授权关闭；C10 仍 failed，原文和病例事实未改，离线结果不是新的真实生成成功。**

## WORKBENCH-ADAPT-C13 C12 后一次真实在线验证

状态：`FAILED_VALIDATION_NOT_ACCEPTED`。独立 [C12 DEMO 病例](http://localhost:5215/workbench/1ff861f8-745d-49af-bb1e-7b436e606d2c) revision 42，经正式任务对 `DeepSeek / deepseek-flash` 实际生成 **1 次**（输出上限 4096 tokens），新分析 `42f51091-6417-4f4d-8f80-0f8df68ac97a`。响应完整留存，输入/输出/合计 17,334/1,805/19,139 tokens；业务校验首拒 `summary` / `number.operation_limit`，独立探针还发现复检新采集指令、补记录的加压表述及交接来源适用性问题。**没有发布有效真实建议**，不把旧替身结果或 failed 页面当作成功；病例事实未改，未重试。Chrome 正式页刷新后仍显示历史“真实模型生成 · failed”，临时真实授权已关闭，同端口恢复 `stub`/`paid=false`；费用未知。受限诊断、可能误拦与实质边界见 [C13 实施记录](WORKBENCH-ADAPT-C13.md)。不改规则、不进入阶段 D，等待用户决定。

## WORKBENCH-ADAPT-C14 统一 AI 约束与生成契约

状态：`IMPLEMENTED_NOT_ACCEPTED`。新请求冻结 `case-advice-proposal-c14-v1`，把事实解释、补记录/交接与具体受控操作的责任分开：自由文本只按字段职责审查一次，最终发布只核对结构和冻结操作不变量；旧 C09 等策略仅用于旧快照。复检、维修步骤不再为凑模板而强制生成；题名、演示参数和受控操作正文由服务端展示。保留有效事实/来源引用、操作条件、来源适用性、必要安全依赖和明确 partial；修正同句已存压力与演示阈值、题名“响应”和否定安全说明的误拦。C08/C10/C13 受限原文仅离线回放，三条历史分析和病例事实未改。独立 [C14 替身体验病例](http://localhost:5215/workbench/87a7442d-3083-4b51-860b-5661644654f8) 经正式任务持久化为 partial，Chrome 实测并刷新恢复；详见 [C14 实施记录](WORKBENCH-ADAPT-C14.md)。本轮真实模型调用数 **0**、真实授权关闭，C14 的真实在线生成效果尚未验证；不进入阶段 D。

## WORKBENCH-ADAPT-C15 资料支持的模拟接头病例与一次真实请求

状态：`FAILED_VALIDATION_NOT_ACCEPTED`。独立 [C15 DEMO 病例](http://localhost:5215/workbench/1dd92a6c-c84e-41e5-bfa8-8676d8847342) revision 60，经正式接口保存 59 条明确标注模拟的维修前观察；接入 DKVB 增压空气系统手册第 1/2/5 页摘录及仅适用同型接头的受控处理动作，没有预置已维修或复检通过。`DeepSeek / deepseek-flash` 真实生成**恰好 1 次**（上限 4096 tokens），分析 `2063ccde-50e2-4b24-9514-ca6385dc39e2` 的完整响应在 `safety_notice/text.unlisted_operation` 被拒，**没有发布维修技术指导**；输入/输出/总用量 18,519/1,572/20,091 tokens，费用未知，未重试。病例事实不变，临时付费授权已关闭，原服务恢复 `stub`/`paid=false`；浏览器重启后需用户自行登录，登录后页面刷新验收未完成。实现、来源边界、受限诊断和实际差距见 [C15 实施记录](WORKBENCH-ADAPT-C15.md)。模拟记录不是实测，真实请求完成不等于真实维修能力验收；停止本轮，不进入阶段 D。

## WORKBENCH-ADAPT-C16 生成与校验职责收尾

状态：`IMPLEMENTED_NOT_ACCEPTED`。C15 完整原回复和原冻结快照的离线审查确认：首拒是模型重复写全局手册安全提醒与服务端受控动作的职责冲突；另有“维修人员”被当作维修指令的独立误拦。新请求采用 `case-advice-proposal-c16-v1`：模型不再填写全局安全／复检文字，也不重复收到受控动作正文；服务端仍从冻结清单装配并验证条件、资料和停止限制。旧快照照原契约读取。原回复只在可追溯的**兼容转换副本**中评估为 3 个方向、4 步 `complete`，没有改写原文、重发模型或发布建议；可读预览保存在受保护的本机 `.local-data/c16-preview.md`，不作为普通病例建议展示。28 项定点通过，正式页登录后只读核对 C15 仍为历史真实生成 `failed`。详细误拦、转换、预览权限与限制见 [C16 实施记录](WORKBENCH-ADAPT-C16.md)。**本轮真实模型调用数 0，真实授权关闭；C15 原分析和病例事实不变，C16 真实在线效果尚未验证。**

## WORKBENCH-ADAPT-C17 面向维修人员的正式指导

状态：`IMPLEMENTED_NOT_ACCEPTED`。后续新分析采用版本化 `case-advice-proposal-c17-v1`：提示词先解释当前判断与支持/反证，必要时才要求补录；受控动作仍由冻结清单装配；正式 AI 区按判断、必要确认、顺序指导、分支和处理后验证呈现，依据与内部 ID 收入详情。独立 [完整接头替身病例](http://localhost:5215/workbench/6b7a0127-5b79-4e49-9556-8204822d4188) 展示受控检查、同型接头条件性处理及复检；[关键压力证据不足](http://localhost:5215/workbench/23abbcbb-3452-4c8f-852f-b9d27dcab80c) 与 [接头记录冲突](http://localhost:5215/workbench/e924df00-de88-4f34-a841-dcaaa6173c27) 只显示针对性补录/澄清，不伪装成完整维修结论。三份均由正式任务持久化；Chrome 已查看完整、初版缺证据及冲突结果，最终缺证据措辞修正后因重启使令牌会话失效，页面再次核对待登录，不能冒称这一步已过。相关定点 33 passed、前端类型检查通过。C15 原病例与失败记录、旧成功建议仍可读；本轮仅加载 `stub`/`paid=false`，**真实模型调用数 0、授权关闭，新契约真实生成效果尚未验证**。详细实现、资料边界及页面地址见 [C17 实施记录](WORKBENCH-ADAPT-C17.md)。

### C17 登录后最终页面收尾

沿用 Chrome 已有合法会话，最终缺证据病例已在正式 5215 页面复核：已保存的 PRS-02 无法取得原因回显，正文仅建议以后获得实际结果时补录，否则保留原因交接；说明了压力证据缺失的用途和限制。点击补记录入口定位 PRS-02，未新增观察，刷新后 revision 60、59 条记录与最终措辞仍在。完整指导病例也经刷新、依据和图示入口复核；页面明确标注替身结果并显示判断、条件性处理及处理后验证，Chrome 已停在其指导开头。本次**无业务代码修复**；仅补记 [C17 页面收尾](WORKBENCH-ADAPT-C17.md#最终页面收尾2026-09-24)。状态仍为 `IMPLEMENTED_NOT_ACCEPTED`，真实模型调用数 0、真实授权关闭，新契约真实生成效果未验证。

## WORKBENCH-ADAPT-C18 C17 链路一次真实生成

状态：`FAILED_VALIDATION_NOT_ACCEPTED`。在 [C17 完整模拟接头病例](http://localhost:5215/workbench/6b7a0127-5b79-4e49-9556-8204822d4188) revision 60 上，经正式任务对 `DeepSeek / deepseek-flash` **恰好生成一次**（输出上限 4096 tokens）；分析 `6a17f8df-8802-47d7-9db1-2070303282e3` 的完整响应在 `unconfirmed_directions[1]` / `text.unlisted_operation` 被业务校验拒绝。受限只读诊断认为该处可能把未确认方向中的“执行器／基本设置”误当成操作指令，但未改规则、未再次生成，也未发布真实指导。用量输入/输出/合计为 **19,368/1,219/20,587 tokens**，实际费用未知。病例仍为 60/59 条有效观察，无处理或复检事实；Chrome 刷新后显示历史真实生成失败，原替身指导仍独立保存。临时授权已关闭，服务恢复 `stub`/`paid=false`。预检、拒绝详情及未完成的真实指导页面验收见 [C18 实施记录](WORKBENCH-ADAPT-C18.md)。不进入阶段 D。

## WORKBENCH-ADAPT-C19 新分析改为结构化建议

状态：`IMPLEMENTED_NOT_ACCEPTED`。新请求使用 `case-advice-open-c19-v1`：移除关键词、数值措辞、方向类型、受控 `action_id`、来源适用性及自由文本依赖等技术内容发布门禁；模型可直接撰写判断和维修建议，服务端保留 JSON 结构、病例权限、冻结快照、幂等、任务持久化与事实保存门禁。无效问题/观察/资料 ID 只在对应页面链接标“无法定位”或“未匹配”，不整份拒绝。旧结果和失败状态不重写。相关 Python 定点 91 passed、前端类型检查与渲染测试通过；5215 已加载 `stub`/`paid=false`。独立 [C19 替身体验病例](http://localhost:5215/workbench/663edce0-9a9a-4105-88a5-4dc01d697980) 的分析 `ac89bf6b-a733-4b19-a9b2-13293dc86c0e` 经正式任务保存；Chrome 实测 ACT-09 缺项导航不写观察，手动保存 DEMO 无法取得原因后 revision 60→61，旧建议标过期且刷新保留。详见 [C19 实施记录](WORKBENCH-ADAPT-C19.md)。**本轮真实模型调用数 0、真实授权关闭；新路径不提供系统对 AI 技术结论的审核保证，新契约真实生成尚未验证。**

## 本机 5215 自动登录

状态：`IMPLEMENTED_NOT_ACCEPTED`。当前 `wp15_workbench.py start` 默认在仅回环、非生产的开发实例启用自动身份：`/auth/session` 为 Chrome 和 Codex 内置浏览器分别建立可续期的 HttpOnly 会话，身份沿用原 runtime `actor`，不重绑病例。[根地址](http://localhost:5215/) 现进入正式 `/workbench`，旧资料预览仍在 `/preview`。页面刷新和本项目 API/Web/worker 重启后都无需输入令牌；在独立 C19 DEMO 病例中使用正式接口保存 X-05 测试记录，revision 61→62，原体验病例未改。关闭方式为停止该脚本登记的服务，再用 `start --manual-login` 启动；实测无 cookie 时恢复 401，之后已重新开启自动模式。Web/API 仅监听 `::1:5215` / `127.0.0.1:8215`，生产默认关闭，写入 Origin/CSRF、病例归属及 AI 付费门禁保留；免登录不构成真实模型付费授权。详情和验证边界见 [本机自动登录实施记录](WORKBENCH-LOCAL-AUTO-LOGIN.md)及 [启动说明](../../runbooks/frontend-diagnosis.md)。**本轮真实模型调用数 0，真实授权关闭。**

### C19 新链路首次真实生成（2026-09-25）

通过正式接口把 C17 完整模拟病例的 59 条维修前观察复制到独立 [C19 真实生成测试病例](http://localhost:5215/workbench/a506d2ac-fcfd-4d37-b411-64ab38f62efb)，revision 60；旧病例、替身结果和历史付费记录未改。`case-advice-open-c19-v1` 的完整输入约 36,294 字符、4 段摘录；运行实例限定 `DeepSeek / deepseek-flash`、4096 输出 tokens，对分析 `3ac3c93c-918d-4304-97dd-2b5f0f0dda5b` 发出**恰好 1 次**真实生成。任务以 `MODEL_TRUNCATED` 失败，未解析、未发布建议；账本记录本次尝试但**未保存到提供方用量，不能据此判断提供方当时是否返回**。SDK 在交付完整消息前抛出截断异常，故当时受限诊断只留存 `parse / MODEL_TRUNCATED`、分析 ID 与 revision，**没有原始回复、哈希或可阅读正文**，现已无法恢复。病例仍为 revision 60、59 条观察、0 条实际处理/复检。工作台刷新后显示“本次结果来源：真实模型生成”及失败状态，不以替身冒充；临时付费窗口已关闭，现为 `stub / paid=false`。此轮**未达到真实指导展示目标**，没有第二次调用。

### C19 截断留存与输出预算接线收尾（2026-09-25）

状态：`IMPLEMENTED_NOT_ACCEPTED`。后续调用若由 SDK 抛出 `LengthFinishReasonError`，网关从其 `completion` 读取实际存在的部分正文、`finish_reason`、返回模型和 usage，先写既有受限诊断，再以 `MODEL_TRUNCATED` 失败；正常返回 `finish_reason=length` 同样处理，不修补残缺 JSON、不发布建议、不重试。未返回的正文/usage 记为不可用而非 0；提供方长度终止与诊断库的 32 KiB 留存裁剪分别标记，原有 30 天留存边界和权限不变。历史 `3ac3c93c-918d-4304-97dd-2b5f0f0dda5b` 保持失败及原诊断，不回填不存在的材料。

病例分析输出预算现在统一由 `CASE_ANALYSIS_MAX_OUTPUT_TOKENS` 配置（十进制整数 256–16384）；快照、预检、网关请求和调用账本沿用同一个冻结值。WP-15 本地启动脚本在无付费授权的默认 `stub` 模式设置 **1536**，既有一次性真实启动仍设置 **4096**；旧 `XIUTU_C03_OUTPUT_TOKENS` / `XIUTU_C05_OUTPUT_TOKENS` 不再影响新分析。16384 只是资源配置上限，不是扩大付费授权；高于既有 4096 的真实预算仍须用户另行确认。离线模拟 SDK 截断、用量缺失、诊断存储失败、正常返回及 8192 传递的定点验证 **24 passed**。已只重启该项目的 API/Web/worker；正式 API 预检实测 `stub / paid=false / 1536`，本地自动登录可用，历史失败分析未改。详见 [C19 接线收尾记录](WORKBENCH-ADAPT-C19.md)。**本轮真实模型调用数 0，真实授权保持关闭。**

### C19 8192-token 真实回复交付（2026-09-25）

用户另行授权后，通过正式接口将原完整模拟剧本复制到独立 [C19 8192 DEMO 病例](http://localhost:5215/workbench/17c8ddf4-fd43-44cc-8f2c-f922d922b8af)，revision 60、59 条模拟维修前观察，不改原病例或历史失败分析。预检确认 `case-advice-open-c19-v1`、输入 36,299/48,000 字符、4 段资料摘录、`DeepSeek / deepseek-flash` 与输出上限 8192。正式分析 `b2cb1c80-f94e-4c43-bc0d-1f0acbc98052` **实际生成 1 次**，`finish_reason=stop`，实际输入/输出/总用量 **14,930/5,992/20,922 tokens**；响应、用量及哈希留存，结构解析后持久化为 `current`，费用未知。建议优先解释软管接头座合不良/泄漏，给出接头复核、资料摘录支持的重新座合/紧固、检漏、同工况压力复测及未解决时的后续方向。Chrome 正式页面及刷新实测可读，资料正文、图示和 AIR-07 事实入口可打开；病例仍为 60/59、无处理或复检事实。短时真实授权已关闭，服务恢复 `stub / paid=false` 与本地自动登录；历史结果仍标“真实模型生成”。这是模拟病例的 AI 建议，**不是经系统技术审核的实车维修结论**。细节与阅读限制见 [C19 实施记录](WORKBENCH-ADAPT-C19.md)。


### C19 新增气路详细参考一次真实分析（2026-09-25）

后续更新：两类故障对照及 `dkvb-c19-v5` 全病例优先级调整见 [C19 实施记录末尾](WORKBENCH-ADAPT-C19.md)。v5 先按事实判断方向，再按资料提供方法，并补充条件未触发的未答题上下文；不增加内容门禁。本次修改零模型调用，真实效果尚待验证。

`IMPLEMENTED_NOT_ACCEPTED`。目标病例 `17c8ddf4-fd43-44cc-8f2c-f922d922b8af` revision60、59条模拟观察保持，新分析 `43e16b6f-e643-4a80-8126-e31caaee1434` 已真实生成并保存；旧 `b2cb1c80-f94e-4c43-bc0d-1f0acbc98052` 不变且页面可展开。实际发送新详细参考的范围/性质说明及1—11、14、16节完整正文，未发12/13/15，替换旧气路摘录。DeepSeek/deepseek-flash一次，8192输出上限，usage 22,834/3,622/26,456；无重试。浏览器依据正文/图示/原题导航/刷新通过，观察、处理与复检事实不变；服务恢复stub/paid=false。摘要更简洁、结构适用性和复检指导更具体，但检漏设备连接仍不够展开；详情见 [C19最新记录](WORKBENCH-ADAPT-C19.md)。停止等待用户查看。
