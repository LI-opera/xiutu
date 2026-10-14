# WP-10 集中审核 r1

结论：**CHANGES_REQUIRED**。A404、A405均有本轮真实隔离数据库反例，当前不建议接受WP-10。仅要求针对ISSUE-001—004整改及定点复核，不重开其他工作包或整个P4；未要求实现通用语义引擎、WP11图、观察写入、最终报告或网页。

审核日期：2026-09-19（Asia/Shanghai）。本任务参与过WP-10实施及上下文修正，本次切换审核角色，**不属于不同任务独立审核**。以下本轮测试与执行者旧证据明确区分。没有修改实现、STATUS、接受记录、历史日志、旧迁移或Git index。

## 1. 依据、基准与保护

已读取适用路径（E:/、E:/Work及项目/子目录未发现适用AGENTS）、STATUS、WP10契约/结果/API说明与导出schema、原始证据、P4说明/验收清单、总指南WP10与8.4/8.5等规格和支持契约。真实资料仍NOT_MET，原WP10/真实效果验收前截止要求尚未满足；虚构语料授权不改变这一状态。

- 根目录E:/Work/xiutu-v5；分支main，无HEAD（rev-parse退出128），没有以此跳过核对。暂存、未暂存、未跟踪清单及命令退出码保存在本轮baseline.json。
- 最终delivery-hashes **3921项全部匹配**；seal绑定的交付清单、保护记录及result SHA256一致；Git index为`c451d6e78b8f29fc818002923a19fb1a888139ced20679ad545f75e9692a9ec6`，开始/结束一致。
- 完整364项之后改变的已有源码仅agents/proposer.py、validators/proposal.py、validators/support.py、tests/unit/test_wp10_schema.py，另新增test_wp10_context.py，与交付披露一致。364项是**上下文收尾修正前**的完整回归，不是当前最终字节版本全量运行。最终schema与运行时Pydantic导出相等。
- 用户原虚构源与副本SHA256均为`e4896ccde323186e8c2c01ca5187b3edfa25977b5a74cb6be45f1a682dedd888`；额外数值fixture单独标synthetic，未冒称来自原文。
- 结束保护核对：3923项输入（交付3921＋manifest/seal）无变化；旧项目63项保护文件、原虚构源及Git index无变化。见baseline.json、verification.json。审核只新增本报告/本轮证据及隔离测试工件。

## 2. 本轮环境、命令与结果

证据目录：`docs/implementation/phase-04/evidence/wp-10-review-r1/`。cwd均为E:/Work/xiutu-v5；导入当前backend源码，使用现有venv，没有旧editable副本。Docker Server29.4.0，xiutu-v5-postgres-1为running，Compose标签project=xiutu-v5/service=postgres，5433仅绑定127.0.0.1。仅复用其服务，新库为`xiutu_test_wp10audit_50660333855b`，迁移到0008；未停既有服务、重建容器或删除库卷。

数据库凭据只从项目受保护本地数据库配置静默用于连接；未读私有.env或真实费用账本。所有补充模型交互为MockTransport和新临时账本，无付费请求。额外观察仅为本轮数据库合成fixture，没有改观察实现。

| 证据版本/运行 | 通过/失败/错误/跳过 | 退出码/说明 |
| --- | --- | --- |
| 历史完整full.xml | 364/0/0/0 | 0，1条既有Starlette/anyio警告；994.52秒，本轮只核查未重跑 |
| 历史收尾context-fixed.xml | 35/0/0/0 | 0，执行者旧证据 |
| **本轮targeted.xml** | **35/0/0/0** | **0**，38.16秒，无警告输出 |
| **本轮audit.xml** | **3/6/0/0** | **1**，61.21秒；六个业务断言失败，不是fixture/环境错误 |
| **本轮audit-retest-budget.xml** | **1/1/0/0** | **1**，20.85秒；共享预算通过，伪冲突复测失败 |
| **本轮demo-artifacts/demo.xml** | **1/0/0/0** | **0**，12.11秒；实际免费CLI |

不累加重复测试为功能覆盖数。每个补充实例只运行一次；没有放宽断言、循环重跑或现场修实现。补充扩大原因仅为代码中发现的字段关系、数值绑定与复测分组缺口，没有运行全套364、前端、第二环境、BGE质量或E10。

| 标签 | 退出码 | 起止时间 | 实际命令（cwd如上） |
| --- | --- | --- | --- |
| create | `0` | 2026-09-19T02:17:02.902959+08:00 → 2026-09-19T02:17:03.717936+08:00 | `E:\Work\xiutu-v5\.venv\Scripts\python.exe -B scripts/probes/prepare_database.py --name xiutu_test_wp10audit_50660333855b` |
| migrate | `0` | 2026-09-19T02:17:03.815288+08:00 → 2026-09-19T02:17:05.031464+08:00 | `E:\Work\xiutu-v5\.venv\Scripts\python.exe -B -m alembic upgrade head` |
| targeted | `0` | 2026-09-19T02:17:05.128100+08:00 → 2026-09-19T02:17:45.548540+08:00 | `E:\Work\xiutu-v5\.venv\Scripts\python.exe -B -m pytest tests/unit/test_wp10_schema.py tests/integration/test_wp10_proposals.py tests/integration/test_wp10_context.py -q -s -p no:cacheprovider --basetemp=.test-runs/wp10-review-targeted-a78c --junitxml=docs/implementation/phase-04/evidence/wp-10-review-r1/targeted.xml` |
| audit | `1` | 2026-09-19T02:18:59.705905+08:00 → 2026-09-19T02:20:02.300574+08:00 | `E:\Work\xiutu-v5\.venv\Scripts\python.exe -B -m pytest docs/implementation/phase-04/evidence/wp-10-review-r1/test_audit_wp10.py -q -s -p no:cacheprovider --basetemp=.test-runs/wp10-review-audit-851a --junitxml=docs/implementation/phase-04/evidence/wp-10-review-r1/audit.xml` |
| audit-retest-budget | `1` | 2026-09-19T02:21:12.427380+08:00 → 2026-09-19T02:21:35.297849+08:00 | `E:\Work\xiutu-v5\.venv\Scripts\python.exe -B -m pytest docs/implementation/phase-04/evidence/wp-10-review-r1/test_audit_retest_budget.py -q -s -p no:cacheprovider --basetemp=.test-runs/wp10-review-retest-f83e --junitxml=docs/implementation/phase-04/evidence/wp-10-review-r1/audit-retest-budget.xml` |
| demo | `0` | 2026-09-19T02:20:02.402880+08:00 → 2026-09-19T02:20:16.793499+08:00 | `E:\Work\xiutu-v5\.venv\Scripts\python.exe -B scripts/demo_proposals.py` |

原输出为各label.txt，完整参数/时间为label.json，失败断言为XML。run.py仅为本轮新库配置和日志脱敏包装，未改业务测试。补充测试位于test_audit_wp10.py、test_audit_retest_budget.py；它们调用当前真实ProposalService/EvidenceService和真实HTTP资料流程，不替换校验或数据库行为。唯一模型替身用于预算验证。

## 3. A404/A405逐项判断

| 检查 | 判断 | 证据与边界 |
| --- | --- | --- |
| 五类型、nested extra、可信上下文、正式ID/status | PASS | 本轮35项及代码：模型union不接收actor/case/profile/status/id；ProposalContext为可信应用内参数，无公开反序列化入口，候选published=false |
| owner/case/version/冻结索引、车型、撤销/最终重验 | PASS（本轮覆盖与代码范围） | 35项复跑含虚构引用、错owner/case/version/revision、撤销期间重验、车型冲突、formal拒绝；复用WP06 source/validity，未改底层权限；未来发布仍需新校验 |
| 截去否定/条件、普通无支持改写、多项说法 | PASS（已覆盖反例） | 原context回归和六个边界单元通过；新multi_claim增加无依据H01说法被拒绝。改写/复杂推理仍uncertain，未宣称通用语义能力 |
| 至少一组合法区域与步骤 | PASS | 原35项真实PG中的单区域、choice步骤、批准规格measurement步骤通过；审核valid与CLI也通过，非“全部拒绝” |
| 字段语义、结论依据 | **FAIL** | ISSUE-001：真实完整引用仍被放入不相干location或作为排除依据 |
| 规格数值/单位/工况硬门禁与表格上下文 | **FAIL** | 对显式Spec逐字段Decimal比对可用，但ISSUE-002存在绕过及跨字段工况不一致 |
| **A404整体** | **FAIL** | 身份与引用完整性通过不能代替具体说法/数值依据 |
| 改标题/已支持同义词重复、不同部件/明显不同工况 | PASS（已覆盖） | 原35项、audit的distinct_component_and_conditions通过 |
| 不同检查对象不得误合并 | **FAIL** | ISSUE-003：插头和外壳检查被同一inspect键合并 |
| 合理复测、无冲突/第二次/有效性门禁 | 部分PASS、整体FAIL | 原同spec冲突复测、单记录拒绝、第二次拒绝通过；代码复用comparison当前有效性；ISSUE-004却把不同quantity/spec拼为冲突 |
| **A405整体** | **FAIL** | 去重对象粒度和冲突分组需要修正 |
| 一次结构/业务修复、预算耗尽 | PASS（本轮范围） | 35项检查turn上限/重复调用与模式；追加真实ProposalService＋同一ModelSupport gateway测试：预置calls=4，提案发1次后支持判断被5次门禁阻断，只1条隔离预留，不另发/另修复 |
| synthetic隔离与固定树边界 | PASS | 原文与新增fixture分开；formal服务拒绝synthetic；无固定五区域/跳转表；未实现后续图或报告 |

“PASS”均限所述合成技术检查，不表示真实维修验收；本报告没有对尚未到期WP11功能判失败。

## 4. 必须整改项

### ISSUE-001 / P1 / A404：引用文本相等没有证明字段或结论成立

位置：`backend/app/services/proposal_service.py:49`（仅传claim.text/quotes）、`backend/app/validators/support.py:22`（相等即supported）、`backend/app/validators/proposal.py:132`（位置只查有无）、`:272`（排除主要核对within_range）。

最小反例（均为本轮真实HTTP绑定的完整合法引用）：

1. 保留合法步骤其他字段，只把location换成“P01 是隔离台架的合成检查部件。”。无任何位置信息，实际仍accepted=true、issues=[]。见location_role.json / audit.xml对应实例。
2. 建合法approved规格和1.5 V的within_range比较，加入当前checked观察；conclude_area.finding仅为同一句“合成检查部件”，assessment填temporarily_excluded。没有支持排除的规则/说法，实际仍accepted=true。见within_exclusion.json。

影响：上下文边界和逐字存在被当成字段/结论支持，位置仍可实际缺失；合格比较可以直接升级为排除许可。即使published=false，这仍是当前候选校验核心契约失败，不是要求实现报告。

最小整改：校验具体字段角色及完整主张（包括assessment），不能只验证一段引用文本；位置不含可核对定位、排除缺少支持关系时返回缺项/uncertain。within_range只能是观察事实，不单独构成排除理由。允许保守拒绝，不要求通用NLP或付费裁判；保留明确有据区域/步骤正例。

定点复核：上述2实例须拒绝；保留无位置、未知/未检查、合法步骤和已有完整段落反例，无需整包重跑。

### ISSUE-002 / P1 / A404：数值门禁遗漏表头/中文数值，步骤工况未绑定规格工况

位置：`backend/app/validators/support.py:59`、`:65`、`:83`；`backend/app/validators/proposal.py:98`、`:158`、`:211`；`backend/app/services/proposal_service.py:50`。

三个独立实测触发：

- table_numeric：表头为“电压合格范围（V），仅engine=off”，完整行`| P01 | 1–2 |`被放入choice，未引用任何MeasurementSpec。locator确实保留表头，但门禁只看行文本；accepted=true。表头存在于provenance不等于参与单位/工况校验。
- chinese_number：action为真实完整引用“检查 P01 电压是否为一伏。”，operation=inspect、input=choice，无Spec，accepted=true。正常中文形式绕过仅阿拉伯数字/有限关键词的正则与measure标签判断。
- condition_conflict：Spec原定义完整、approved且conditions={engine:off}；只把步骤前置工况改成另一条真实引用“发动机运转，engine=on。”，accepted=true。每个字段分别有来源，但相互矛盾；既有Decimal比较没有检查这个关系。

影响：声明“数值只经已审核Spec、工况一致”的核心保证不成立，可通过choice/inspect/表格载体或跨字段冲突绕过。

最小整改：数值主张必须有受控结构及批准Spec关联；检查使用位置的量、单位、范围和工况，不仅检查asserted定义与数据库定义相等。将表头/适用条件纳入所用表格依据。不支持的数字载体明确待补/拒绝，不能只扩几条正则后宣称任意自然语言安全。拒绝明确engine=on/off冲突；不用LLM替代硬校验。

定点复核：三实例、现有approved数值正例、Decimal上下界/单位/工况变更反例及未审核拒绝；不要求重新实现WP06比较器。

### ISSUE-003 / P2 / A405：去重键丢失实际动作对象

位置：`backend/app/validators/repetition.py:27`—40，尤其operations仅为a.operation集合；`backend/app/services/proposal_service.py:73`。

复现：同一P01、相同工况，真实资料分别支持“检查 P01 插头。”与“检查 P01 外壳。”；两者单独均accepted=true。把插头检查fingerprint写入可信history后，外壳检查返回DUPLICATE_CHECK（expected accepted=true）。见distinct_action.json、audit.xml。

影响：实际不同检查被拦截为重复，阻止合理下一步；不是只改标题的重复，也不是要求无限语义模型。

最小整改：在有界受控动作语义中保留实际对象/检查内容或经验证的动作标识，同时归一已支持的同义表达；不能只保留inspect/measure大类，也不能简单把title加入键而重新允许改标题绕过。

定点复核：插头/外壳应不同；同一检查改标题/检查-查看应重复；不同部件、明确不同工况及测量对象正例保留。

### ISSUE-004 / P2 / A405：不同规格结果被汇总成伪冲突

位置：`backend/app/validators/proposal.py:330`—371。各比较只需匹配任意一个input.measurements，随后全局outcomes集合丢失spec/quantity分组。

复现：同一P01下两份真实人工批准的合成规格，电压1—2 V与电阻1—2 ohm；当前观察为1.5 V（within_range）和3 ohm（out_of_range）。这是两个不同测量结果，没有同一规格的相互矛盾。提案含两份合法Spec和“记录冲突”理由，实际获准复测accepted=true。见unrelated-measurement-conflict.json及audit-retest-budget.xml失败实例。

影响：可用不相干的正常/超限结果制造复测理由，违背“同规格同工况有效冲突”的本包明确契约。

最小整改：按同一规范化测量对象、规格版本/物理量和工况验证冲突对，不能跨组凑within/out；复测理由须关联该冲突组。无需扩建观察写入或通用工作流。

定点复核：不同quantity/spec组合拒绝；既有相同spec/工况的冲突允许；单记录、错case、失效比较及第二次复测继续拒绝。

## 5. 非阻断建议与未验证项

- N01：STATUS第3行仍写WP10—17未开始，与下方WP10 IMPLEMENTED_NOT_ACCEPTED及停止点不一致；后续文档同步即可，本轮未修改，不单独否决工作包。
- owner粗锁、保守词表/抽取导致的过度待补、性能和监控属于既有/非阻断改进。本轮只对已实测的特定错误合并提出整改，不要求通用语义模型。
- ModelSupport与ProposalRunner需可信应用组装同一个gateway。本轮实际验证该约定下预算共享；未来图接入应保留这一组装约束，不能另开预算。
- 复测专用的“错case观察/已失效比较”组合本轮只检查了代码门禁，未再独立构造每个组合；35项覆盖的错case引用、规格撤销与第二次复测不能冒称这些组合全都亲测。已发现的跨规格伪冲突另有真实失败证据。
- 没有验证真实模型提案质量、自然语言普遍蕴含或真实维修效果。E10沿用WP09既有限定deepseek-flash结论，不重跑、不扩大。
- Linux BGE部署NOT_VERIFIED、真实资料NOT_MET及原截止节点未满足、SSE/Compose历史首次根因未确认、同任务实施/审核流程限制均保留。合成规格与within_range不是维修结论。
- 最终重验只保护本包预览；未来持久发布要重新验证，不要求本包实现网络之后即时撤销或WP11事务。

## 6. 接受建议与停止

当前不建议接受WP10：A404/A405反例涉及本包承诺的依据与重复/复测行为。建议只修ISSUE-001—004，再运行对应反例与受影响正例定点复核；可复用本轮35项及历史364项的未变证据，无新跨模块风险不必重跑整包。没有现场修实现或生成用户接受记录，不提交推送、不进入WP11。

本轮证据与报告完成后停止，等待用户决定。
