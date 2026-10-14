# WP-10 ISSUE-001 剩余结论能力整改 r2

时间：2026-09-19T03:25:15.635952+08:00。执行者整改记录，等待仅针对本次结论路径的定点复核；不是审核关闭或接受记录。WP-10保持IMPLEMENTED_NOT_ACCEPTED，ISSUE-002—004沿用原r2已关闭结论，不重开整包、不进入WP-11。

## 1. 基准与根因

原r2指出：r1阻断了错误结论，但也统一拒绝hypothesis/temporarily_excluded，合法区域/步骤不能替代合法结论能力。原r2两条结论正例、失败断言和记录均未修改。本次没有把原测试改成“历史通过”；原输入没有可信映射，仍不能仅凭引用相等获准。新增测试显式建立可追溯的结构化映射，证明恢复后的成功路径。

开始baseline.json逐项匹配4093项审核交付/历史文件；main无HEAD，使用文件SHA256和Git index固定基准。index为c451d6e78b8f29fc818002923a19fb1a888139ced20679ad545f75e9692a9ec6。结束protection-check.json显示仅声明的六份既有文件改变，无其他基准差异；63项旧项目保护清单及原虚构资料hash保持。STATUS、接受记录、旧迁移和历史证据未改。不读取私有.env或真实费用账本。

## 2. 最小支持关系与信任来源

新增TrustedConclusionRule，规则格式1，由可信应用通过ProposalService(..., conclusion_rules=(...))显式注入，默认空、最多16项、不可变且ID唯一。模型输入仅能引用support_rule_id/conclusion_scope，不能提交规则、reviewed或premises_satisfied。没有自动从上传文件/approved文档注册规则的行为，没有规则管理平台或观察写入API。

每项规则绑定owner/case/profile/component、evidence/document_version、quote SHA256、authorization_epoch、reviewed_by/reviewed_at和engine工况；排除另绑定准确spec_id与完整已批准definition规范JSON哈希。审核字段是可信装配的责任凭据，不是系统替人工验证推理的承诺；真实装配必须单独审阅“来源→结构关系”，不能从文档批准状态推导规则已审。本轮只在synthetic测试代码中明确提供映射，生产默认无规则。

映射来源：tests/fixtures/wp10/conclusion-support-synthetic.json记录原r2审核脚本路径及SHA256，保留两条新增合成规则原句；这两条是r2新增合成例，不冒称来自用户原虚构文件。测试上传该来源、绑定实际不可变证据后，可信代码创建带实际版本/epoch/hash/审核者和时间的映射；排除引用WP06真实创建/批准的合成Spec。没有修改原虚构资料。

| 模板 | 从当前DB读取的必要前提 | 服务端生成的结论 |
| --- | --- | --- |
| connector_detached_hypothesis | 当前case/revision、同component、checked=true、engine一致、connector_state=detached | contact_fault待验证假设，尚未确诊 |
| housing_intact_comparison_exclusion | 同条件housing_state=intact，加精确Spec版本/定义hash对应的当前有效within_range比较 | 仅暂时排除housing_damage，其他原因未定，不表示整件正常 |

模板按结构类型执行，不按P01或审核例句分支；P01、Q02各自两类正例均通过。模型finding只允许映射绑定的完整来源quote，防止自由扩写；quote相等仅是来源完整性条件，还必须通过上述受信规则和实际前提。真正可使用的结论是服务端conclusion_support，不是把候选原文当诊断结论。

## 3. 校验与失败边界

- 复用既有owner/case/revision/manifest/版本/适配/撤销门禁，映射另验证profile、epoch/hash及精确来源关系。
- 所选观察ID必须来自当前有效集合并提供每个前提；读取所有同对象相关有效观察，未选中的冲突也阻断。superseded旧观察不算当前前提。观察payload的受控字段为component_key、checked、conditions、connector_state/housing_state或comparison_id，来自可信DB读取，不来自模型满足声明。
- 排除需精确批准且未needs_review的Spec及有效来源；比较必须属于当前case/该Spec，完整定义hash与工况一致，复用get_comparison当前有效性。失效、错case/spec、超限、缺一个前提、未检查或工况不符均阻断。within_range单独仍不能排除。
- assessment/scope必须等于模板允许范围；外壳破损不能扩为整个部件正常。hypothesis保持待验证，unknown/not_checked/insufficient_data保持needs_input。
- 支持评估前及其后的最终owner锁内重验均执行上述校验。支持阶段发生来源/规格撤销或新增冲突观察，最终检查拒绝；不返回有效conclusion_support。通过仍published=false、diagnosis=false，不实现正式状态发布或网络发送后的即时撤回。
- 不支持其他推理模板、任意工况/NLP、自由因果链；没有映射仍ASSESSMENT_UNCERTAIN。不是统一拒绝两类合法结论。

## 4. 文件与接口变化

既有六份：backend/app/agents/state.py（候选新增两个可选字段）；backend/app/validators/proposal.py（调用结论硬门禁、保留旧无映射拒绝路径）；backend/app/services/proposal_service.py（应用注入及最终证明输出）；docs/implementation/phase-04/wp-10-contract.md；docs/api/wp-10-proposals.md；docs/api/wp-10-proposal.schema.json。实际差异见证据目录六个.diff。

新增：backend/app/agents/conclusion_rules.py、backend/app/validators/conclusion.py、tests/integration/test_wp10_conclusions.py、tests/unit/test_wp10_rule_contract.py、tests/fixtures/wp10/conclusion-support-synthetic.json、docs/api/wp-10-trusted-conclusion-rule.schema.json，以及本报告/证据。

无迁移、无新HTTP写API。旧请求兼容解析但无映射不会自动推断；可信规则schema与模型候选schema分开导出。support.py、repetition.py、WP06比较器、预算和已关闭问题对应算法没有修改。

## 5. 实际验证与失败保留

工作目录均E:/Work/xiutu-v5，Python为当前.venv/Scripts/python.exe，导入当前backend。Docker既有xiutu-v5-postgres-1/loopback5433已核对，只创建隔离库xiutu_test_wp10con_8c05bc481695，未删除既有库/卷或停止既有服务。测试经真实HTTP准备合成来源、解析/索引和规格，再以服务入口验证结论；没有付费模型或模型选型/质量评测。新测试库迁移至现有0008，仅准备环境，无迁移代码改动。

每条命令、cwd、起止时间和退出码见同名.json；原始输出与JUnit分别为.txt/.xml。运行器run.py只静默加载项目专用DB凭据，不加载.env，设置APP_MODE=test及独立输出/数据目录。

| 本轮执行 | 退出码 | 结果与证据 |
| --- | --- | --- |
| create / migrate | 0 / 0 | 新隔离库及既有迁移；create.json、migrate.json |
| conclusions（新增24实例首轮） | 1 | 22通过、1失败、1错误，0跳过；conclusions.xml/txt |
| corrected（仅两实例） | 0 | 2通过，0失败/错误/跳过；corrected.xml/txt |
| regression（受影响旧路径及规则schema） | 0 | 22通过，0失败/错误/跳过；regression.xml/txt |
| Ruff本次相关实现及测试 | 0 | 首次lint.json/txt；夹具修正后再次check通过，见final-static.json |

首轮失败不是放宽业务断言：superseded夹具在同revision插入替代观察，既有0007数据库lineage约束正确拒绝。仅新测试改为推进隔离case revision并以新revision插入后继，保留旧ID作为待拒绝输入；断言仍为不接受。另一项在Rig.setup启动API时15秒有界等待耗尽，业务测试尚未执行，日志为空、首次根因未确认。没有扩大超时或修改已有夹具；保留失败XML，定点再运行这两项各一次后通过，不解释为平台问题已修复。启动失败遗留子进程按PID/父子关系/创建时间和命令核对后清理；startup-timeout.json记录，辅助psutil检查不可用，未安装依赖。没有循环全量跑到通过。

新增24实例的22项首次已通过，其余2项修正/重试后通过；不声称最终测试文件24项重新整体跑过。新增测试的最终变化只在superseded夹具revision；生产实现从首轮到结束无变化。22项受影响回归在当前最终实现运行，不将重复运行累加成不同功能覆盖数。

可复制的定点入口（使用新临时路径和显式TEST_DATABASE_URL，禁止复用会被pytest清空的既有basetemp）：

```powershell
.venv/Scripts/python.exe -B -m pytest tests/integration/test_wp10_conclusions.py tests/unit/test_wp10_rule_contract.py -q -p no:cacheprovider --basetemp=.test-runs/<全新UUID> --junitxml=<全新输出目录>/conclusions.xml
```

本轮精确命令无需猜测：conclusions.json、corrected.json、regression.json保存argv全列表。回归选择为union/指纹schema、位置/来源/支持/最终重验、批准规格/数值/工况、表格/中文数值、插头外壳区分和同规格冲突复测，未重开ISSUE-002—004。没有重跑364项、前端、第二环境、BGE或E10，也未重跑免费CLI旧路径。

### 正反例证据

- conclusion-success-*.json：P01/Q02两类合法结论及受信映射实际来源/审核元数据。
- conclusion-forgery-*.json：模型伪规则/审核标记、scope/assessment/对象扩大、错误绑定及无映射拒绝。
- conclusion-premise-*.json：未检查、缺状态/比较、工况冲突、未选冲突、旧观察失效。
- conclusion-invalid-*.json：错Spec、错case、比较失效（重新批准不清除旧复核）、超限冲突、来源撤销。
- conclusion-final-*.json：支持评估之后的来源/观察/比较变化在最终重验被拒绝。
- location_role.json、within_exclusion.json、table_numeric.json、chinese_number.json、condition_conflict.json、distinct_action.json、unrelated-measurement-conflict.json：原安全门禁定点回归。

## 6. 历史证据、保留项与停止

历史完整364项、原35项、r1整改53+4项、原r2定点19及补充1通过/2失败均属于各自历史字节版本；本次不改写、不宣称整改后完整回归或审核通过。原r2对ISSUE-002—004的关闭结论保留，本次仅提供ISSUE-001剩余功能差异供复核，不自行关闭问题。

规则仅由synthetic可信装配提供，尚无生产规则审核/注册UI或持久规则管理；观察写入、持久图、正式报告、通用语义理解均未实现。合成规格/规则不是维修标准。真实资料NOT_MET，原WP10/真实效果验收前截止要求尚未满足，不顺延、不改formal门禁。E10既有deepseek-flash限定结论、Linux BGE未验证、混合模型排序/性能等非阻断项、SSE首次及Compose历史根因未确认继续保留。同任务实施/整改/审核历史限制不变，本报告是执行者自测，不声称独立审核。

未改STATUS、接受记录、历史证据、旧项目/迁移或Git index；未提交推送、未付费调用、未读取/重置真实费用账本。停止，等待仅针对本次结论路径的定点复核。
