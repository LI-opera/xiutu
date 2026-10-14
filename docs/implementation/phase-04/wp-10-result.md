# WP-10 实施结果

状态：IMPLEMENTED_NOT_ACCEPTED。仅本包合成资料技术实施与执行者自测，等待一次集中审核及用户决定；不自行审核或接受，不启动WP-11，不接受整个P4。

## 现在能体验什么

可以在隔离环境展示用户虚构冷却资料的真实片段与来源，提出数量不固定的有据物理区域，检查步骤位置、工况、动作、规格和引用，显示明确的拒绝/待补原因。五类提案具有实际Pydantic schema；支持关系不确定、未检查、无规格或重复检查均不会被强行当成已完成诊断。免费CLI经过真实HTTP、PostgreSQL、资料worker和本地E5，再调用本包应用内校验；没有网页工作台、正式图、观察写入或报告。

## 基准与范围

已读取适用路径（未发现适用AGENTS）、STATUS、WP09接受/r2、P4说明和A404/A405清单、总指南提案/证据/规格/预算契约及用户指定虚构文件。WP09接受后基准3743项，授权差异为STATUS接受更新，见baseline.json；main无HEAD，Git index按SHA256固定。没有重做已接受包审核。

用户原文：`E:\Work\v4-double\冷却系统完整清晰维修树（虚构交互样例）.md`。按字节复制到tests/fixtures/wp10/cooling-synthetic.md，source.json记录来源、SHA256、synthetic=true/formal_usable=false。SHA256：`e4896ccde323186e8c2c01ca5187b3edfa25977b5a74cb6be45f1a682dedd888`。没有将文档指令作为系统授权、固定五区域或跳转表。独立extra-synthetic.md中的1—2 V及engine=off是新增虚构台架标准，不来自原文，Ux未当物理单位。

真实资料仍NOT_MET，原WP10/真实效果验收前的门槛目前未满足，不顺延或标为通过。本次用户授权只允许合成技术验证，formal/synthetic门禁原实现不改。

## 实际文件与接口

新增：

- backend/app/agents/state.py、proposer.py及prompts/initial.md、next_step.md：五类型、受信上下文、一次修复；正式业务ID/状态不由模型写入。
- backend/app/validators/proposal.py、support.py、repetition.py：只读硬门禁、完整上下文支持判定、动作/部件/测量/工况重复键与冲突复测。
- backend/app/services/proposal_service.py：复用EvidenceService、Spec与观察repository；owner锁读取，支持判断后最终重验，输出候选而非发布。
- tests/unit/test_wp10_schema.py、tests/integration/test_wp10_proposals.py、test_wp10_context.py和合成fixtures；scripts/demo_proposals.py。
- 本包契约、结果、独立证据、docs/api/wp-10-proposals.md与真实导出schema/hash。

更新README、CHANGELOG、STATUS。没有修改已有业务实现、依赖锁或迁移；head仍0008，旧迁移保持原样；没有新增公开HTTP提案路由。应用接口和输入输出/调用顺序详见[契约](wp-10-contract.md)及[接口文档](../../api/wp-10-proposals.md)。

## A404/A405 技术自测

| 项目 | 本轮证明 | 证据 |
| --- | --- | --- |
| A404 引用、位置及规格 | 虚构ID、错owner/case/version/revision、撤销、车型冲突、formal/synthetic混用拒绝；无位置/工况/动作/规格给缺项；approved定义按Decimal字段硬比，不允许改上下界/quantity/unit/conditions；测量不能藏在choice中 | targeted-final.xml、context-fixed.xml、hard-gates-*.json、spec-and-retest-*.json |
| A404 说法支持 | 引用存在但不支持说法进入uncertain；unsupported/错误裁判结构不放行；提案判断期间撤销在最终重验拒绝；新增真实quote截去否定反例先失败，修正后拒绝 | context-before2.xml/txt、context-fixed.xml、test_context_boundary.py；正式回归test_wp10_context.py |
| A405 重复与复测 | 改标题/检查同义词仍同fingerprint；同规格同工况真实比较一合格一超限，加当前观察/引用理由才允许一次复测；无冲突、不相关观察、第二复测拒绝；排除不能忽略其他冲突记录 | unit.xml、context-fixed.xml、spec-and-retest-*.json |
| 提案与预算 | 五类型/嵌套extra拒绝、区域1—8且最多两层；request_tools白名单和既有输入校验；同一ProposalTurn最多两次提案，后续重复调用不再发送；预算耗尽明确退出；支持与提案共用网关 | tests/unit/test_wp10_schema.py、context-fixed.xml |
| 演示及隔离 | 真实上传→解析→审核→索引→冻结会话→绑定证据→预览/缺项；合成始终非正式可用；只生成候选，不写图/观察/报告 | demo.json/txt、demo-artifacts/demo.xml及JSON |

这是执行者自测证据，不是独立审核结论。观察fixture仅在隔离库直接插入，用于复用既有只读repository；未新增观察写入API。

## 实际命令、结果与失败历史

cwd均为`E:\Work\xiutu-v5`。使用新隔离库`xiutu_test_wp10_547b9be46375`、独立.test-runs路径和evidence/wp-10；复用已确认xiutu-v5专用数据库服务，不停止未知服务、不删库卷。迁移回归按既有入口另建唯一子库。测试凭据静默注入，没有读取旧.env或真实模型费用账本。

完整命令、起止时间、退出码见各label.json；原始输出label.txt、JUnit label.xml。执行包装器run.py只为本轮隔离配置和脱敏日志，不改变测试断言。主要命令：

```text
.venv/Scripts/python.exe -B docs/implementation/phase-04/evidence/wp-10/run.py targeted-final PY -B -m pytest tests/unit/test_wp10_schema.py tests/integration/test_wp10_proposals.py -q -s -p no:cacheprovider --basetemp=.test-runs/wp10-final-739e --junitxml=docs/implementation/phase-04/evidence/wp-10/targeted-final.xml
.venv/Scripts/python.exe -B docs/implementation/phase-04/evidence/wp-10/run.py full powershell -NoProfile -ExecutionPolicy Bypass -File scripts/test.ps1
.venv/Scripts/python.exe -B docs/implementation/phase-04/evidence/wp-10/run.py context-fixed PY -B -m pytest tests/unit/test_wp10_schema.py tests/integration/test_wp10_proposals.py tests/integration/test_wp10_context.py -q -s -p no:cacheprovider --basetemp=.test-runs/wp10-context-b952 --junitxml=docs/implementation/phase-04/evidence/wp-10/context-fixed.xml
.venv/Scripts/python.exe -B docs/implementation/phase-04/evidence/wp-10/run.py demo PY -B scripts/demo_proposals.py
```

| 标签 | 退出码 | 通过/失败/错误/跳过 | 实际起止时间 |
| --- | --- | --- | --- |
| create | 0 | — | 2026-09-19T01:38:10.091107+08:00 → 2026-09-19T01:38:10.896217+08:00 |
| migrate | 0 | — | 2026-09-19T01:38:10.992197+08:00 → 2026-09-19T01:38:12.224854+08:00 |
| unit | 0 | 23/0/0/0 | 2026-09-19T01:35:16.381823+08:00 → 2026-09-19T01:35:22.476844+08:00 |
| integration | 1 | 2/1/0/0 | 2026-09-19T01:38:12.322972+08:00 → 2026-09-19T01:38:41.209096+08:00 |
| targeted-fix | 2 | 0/0/1/0 | 2026-09-19T01:41:56.459132+08:00 → 2026-09-19T01:41:59.983364+08:00 |
| targeted-fix2 | 1 | 23/1/0/0 | 2026-09-19T01:42:12.458550+08:00 → 2026-09-19T01:42:27.304489+08:00 |
| targeted-fix3 | 0 | 1/0/0/0 | 2026-09-19T01:43:03.375592+08:00 → 2026-09-19T01:43:13.766241+08:00 |
| targeted-final | 0 | 27/0/0/0 | 2026-09-19T01:44:20.060013+08:00 → 2026-09-19T01:44:54.778098+08:00 |
| full | 0 | 364/0/0/0 | 2026-09-19T01:45:18.450977+08:00 → 2026-09-19T02:01:55.896063+08:00 |
| context-before | 1 | 0/0/1/0 | 2026-09-19T02:02:16.951729+08:00 → 2026-09-19T02:02:19.549886+08:00 |
| context-before2 | 1 | 0/1/0/0 | 2026-09-19T02:02:51.514090+08:00 → 2026-09-19T02:03:01.328728+08:00 |
| context-fixed | 0 | 35/0/0/0 | 2026-09-19T02:04:04.740237+08:00 → 2026-09-19T02:04:43.993941+08:00 |
| lint-final | 0 | — | 2026-09-19T02:05:02.432208+08:00 → 2026-09-19T02:05:02.593613+08:00 |
| demo | 0 | 1/0/0/0 | 2026-09-19T02:05:02.684653+08:00 → 2026-09-19T02:05:15.064712+08:00 |

- 首轮复测用例失败最终定位为测试helper默认mV，1.5/3都超限；显式V后才形成预期冲突。曾补UUID字符串规范化，但它不是该失败根因。首次及中间失败均保留；没有放宽断言。
- targeted-fix因新单元/集成测试同名而收集错误，仅重命名单元测试；context-before因证据目录未载入tests/conftest而fixture缺失，移入正式测试目录，保留相同业务断言后context-before2真实失败。
- 完整入口只运行一次：**364 passed、0 failed/error/skipped、1条既有Starlette/anyio弃用警告，994.52秒，exit0**。full-code-hashes.json固定其155项代码/测试/脚本基准。
- 完整运行后，基于明确代码风险新增否定上下文反例，证明真实引用也可能不支持说法；修复后**35项受影响定点通过**，CLI**1项通过**、ruff通过。没有再次运行完整入口，不把364项称为最终字节版本重跑结果，不累加为功能覆盖数。

完整后改动：
- backend/app/agents/proposer.py
- backend/app/validators/proposal.py
- backend/app/validators/support.py
- tests/unit/test_wp10_schema.py

另新增tests/integration/test_wp10_context.py。修复增加上下文边界；proposer加载既有next_step提示，新增离线调用断言覆盖。额外合成fixture保留独立段落边界及“新增虚构”标注，没有更改用户原文或其数值含义。最终交付哈希及封存见delivery-hashes.json/seal.json，保护核对见protection-final.json。所有初始失败和中间输出原样保留。

## 亲自运行

按README隔离测试库步骤设置全新xiutu_test_*的TEST_DATABASE_URL，不使用业务库，然后：

```powershell
$env:PYTHONPATH = "$PWD/backend"
uv run --frozen python -B scripts/demo_proposals.py
```

入口拒绝缺配置/不合规目标；使用现有本地E5与开发测试依赖，不付费、不下载模型。输出新.test-runs/wp10-demo-UUID：来源片段、有据单区域、缺位置/工况/规格、无支持说法及未检查不能排除。实测入口exit0、1 passed。它不是网页工作台或真实维修建议。

## 限制、未验证与停止

- 本包付费调用0；没有读取或重置真实账本/共享5元额度。MockTransport只证明模型接口、修复和预算契约，不证明真实提案质量或维修语义。E10沿用WP09已接受的deepseek-flash限定原证据，不扩大。
- 默认支持判断保守：完整段落或表格行再做逐字支持；改写、复杂跨段因果或资料不足会待补。可选ModelSupport仅离线验证；不能把源文内容存在当实际真值。自然语言普遍蕴含能力、人工真实语料评测未验证。
- 反重复是有界动作词及结构化键，工况/动作复杂改写、过度拦截等需后续真实资料评测；不宣称任意语义去重。合理复测当前限于受支持测量冲突；其他理由需待补。
- 预览最终重验与未来持久发布是不同边界；WP11必须重新校验，不能沿用accepted快照。没有持久图、正式运行turn、观察提交、报告任务或前端。
- **真实资料NOT_MET，原WP10/真实效果验收前截止要求尚未满足**；合成规格不是实际标准，within_range不是部件正常。Linux BGE部署未验证、历史SSE/Compose根因未确认、同任务历史流程限制和既有非阻断待办保留。全套测试中SSE通过不代表查明历史首次根因。
- 当前没有已知未解决的本包合成技术阻断项；真实资料门槛未满足是明确保留的实际验收缺口。后续建议做专业标注支持集和重复语义评测，不在本包扩建。
- 旧项目63项保护文件、原虚构源、旧迁移、接受记录和历史证据保持不变；Git index不变。只进行实现与自测，不生成REVIEW_PASS、不自行接受。不提交推送、不启动WP11。
