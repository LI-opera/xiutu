# WP-10 r2 四项整改定点复核

结论：**CHANGES_REQUIRED**。ISSUE-002、003、004在列明的有界技术范围内关闭；ISSUE-001的原误放行反例已阻断，但有据结论的成功路径被统一禁用，属于功能收缩，**未完整关闭**。本轮未发现新的越权或误放行问题；不重开整包审核，不要求通用NLP、付费裁判、WP11持久图或报告流程。

时间：2026-09-19T02:56:28.265653+08:00。**本任务参与过WP10实施、整改及先前审核，本次是同任务切换审核角色，不属于不同任务独立审核。** 没有修改实现、原测试、STATUS、接受记录、历史报告/证据、迁移或Git index。本报告不是用户接受。

## 1. 基准、版本及实际差异

已读取适用路径（项目与上级未发现AGENTS）、STATUS、r1审核、r1整改、当前契约/API、四个改动实现文件、新增测试、两轮原始证据；并核对P4说明第4节、A404/A405及总指南WP10，判断结论功能收缩的边界。

- 工作根E:/Work/xiutu-v5；main，无HEAD（exit128），按文件哈希及Git index核对，没有因此跳过基准。
- 整改delivery-hashes及seal全部匹配。纳入本轮保护的输入共 **4,045项**；开始/结束均无差异。index SHA256 `c451d6e78b8f29fc818002923a19fb1a888139ced20679ad545f75e9692a9ec6`。git根、分支、暂存/未暂存/未跟踪输出见git-*.json。
- 相比r1审核，已有文件变化恰为4个实现文件、WP10契约/API说明及STATUS首段，共7份；新增正式集成/单元测试和整改报告/证据，符合声明。WP06比较器、旧迁移、预算等未变。见declared-diff.json。
- 原审核七个失败实例的业务断言均保留，正式回归仅调整导入/输出位置和格式，表格实例后来追加更强错误码断言。assertion-preservation.json已用AST核对，没有修改原反例或原失败记录。
- 结束旧项目63项、原虚构资料/副本及全部保护输入不变；见verification.json。原源SHA256仍为e4896ccde323186e8c2c01ca5187b3edfa25977b5a74cb6be45f1a682dedd888。

版本不得混淆：历史完整364是更早上下文收尾修正前基准；原35项是其后版本；整改53项及CLI发生在表头source路径补正前；最终补正只验证4项。本轮在最终字节版本重跑选定集合，**没有声称整改后全量364通过**。

## 2. 本轮执行与证据

Docker Server29.4.0，现有xiutu-v5-postgres-1为running，project=xiutu-v5/service=postgres，127.0.0.1:5433归属匹配。仅新建隔离库 **xiutu_test_wp10r2_083d6a30d8ef**，不复用此前审核/整改库；临时目录及输出全新，基线/环境/运行包装脚本均留存。

凭据只静默读取本项目受保护数据库配置用于测试连接；未读取私有.env或真实费用账本，无付费模型请求。本轮数据、规格、规则与观察全部synthetic，真实HTTP资料链及PG服务被实际使用，未替换业务校验。没有启动BGE、重跑E10或前端/第二环境。测试fixture只终止自身进程，未停数据库或删既有库卷。

| 版本/证据 | 通过/失败/错误/跳过 | 退出码及说明 |
| --- | --- | --- |
| 历史完整364 | 364/0/0/0 | 原执行证据，1条已知警告，本轮未运行 |
| 原收尾/审核35 | 各35/0/0/0 | 各自历史基准，本轮未重新全套运行 |
| 整改targeted | 53/0/0/0 | 0，表头路径补正前；CLI另1通过 |
| 整改header-targeted | 业务未执行/1收集错误 | 2，同名单元文件错误保留 |
| 整改header-corrected | 4/0/0/0 | 0，补正后定点；不覆盖首轮版本 |
| **本轮targeted.xml** | **19/0/0/0** | **0**，102.91秒，无警告输出 |
| **本轮supplemental.xml** | **1/2/0/0** | **1**，24.48秒，无警告输出；两项合法结论成功预期失败 |

不累加重复运行次数为功能覆盖数。selection.json列去重选择：原七个业务反例；不同部件/工况；错case、失效比较、旧history、错量和不相关理由；现有批准规格/篡改/同组冲突/单记录/第二次复测综合用例；3项表头单元及2项同义词/标题指纹例。未重复选择已在综合用例覆盖的valid/single/second实例。

新增3项仅针对用户指定的结论成功路径和表头独立作用缺口，位于本轮test_audit_wp10_r2.py。每个实例只执行一次，没有失败后循环重跑或现场修改。CLI引用整改1项通过证据：它展示区域与待补，不证明合法结论路径；source层级变化由本轮真实表格对照验证，无需再跑同等CLI。

cwd均为E:/Work/xiutu-v5；完整命令、起止时间、退出码与日志分别在label.json/txt，JUnit均使用正斜杠：

- **create**：exit 0；2026-09-19T02:50:16.917815+08:00 → 2026-09-19T02:50:17.655267+08:00。
  `E:\Work\xiutu-v5\.venv\Scripts\python.exe -B scripts/probes/prepare_database.py --name xiutu_test_wp10r2_083d6a30d8ef`

- **migrate**：exit 0；2026-09-19T02:50:17.752316+08:00 → 2026-09-19T02:50:18.959435+08:00。
  `E:\Work\xiutu-v5\.venv\Scripts\python.exe -B -m alembic upgrade head`

- **targeted**：exit 0；2026-09-19T02:50:46.799161+08:00 → 2026-09-19T02:52:31.754365+08:00。
  `E:\Work\xiutu-v5\.venv\Scripts\python.exe -B -m pytest tests/integration/test_wp10_remediation.py::test_business_boundaries[location_role] tests/integration/test_wp10_remediation.py::test_business_boundaries[condition_conflict] tests/integration/test_wp10_remediation.py::test_business_boundaries[table_numeric] tests/integration/test_wp10_remediation.py::test_business_boundaries[chinese_number] tests/integration/test_wp10_remediation.py::test_business_boundaries[within_exclusion] tests/integration/test_wp10_remediation.py::test_business_boundaries[distinct_action] tests/integration/test_wp10_remediation.py::test_retest_requires_same_measurement_conflict tests/integration/test_wp10_remediation.py::test_distinct_component_and_conditions tests/integration/test_wp10_remediation.py::test_retest_association_and_history[wrong_case] tests/integration/test_wp10_remediation.py::test_retest_association_and_history[invalid_comparison] tests/integration/test_wp10_remediation.py::test_retest_association_and_history[old_history] tests/integration/test_wp10_remediation.py::test_retest_association_and_history[wrong_quantity] tests/integration/test_wp10_remediation.py::test_retest_association_and_history[unrelated_reason] tests/integration/test_wp10_proposals.py::test_spec_hard_numbers_retest_and_scope tests/unit/test_wp10_role_grammar.py tests/unit/test_wp10_schema.py::test_semantic_fingerprint_ignores_title -q -p no:cacheprovider --basetemp=.test-runs/wp10r2-targeted-6aa9 --junitxml=E:/Work/xiutu-v5/docs/implementation/phase-04/evidence/wp-10-review-r2/targeted.xml`

- **supplemental**：exit 1；2026-09-19T02:53:09.019053+08:00 → 2026-09-19T02:53:35.112124+08:00。
  `E:\Work\xiutu-v5\.venv\Scripts\python.exe -B -m pytest docs/implementation/phase-04/evidence/wp-10-review-r2/test_audit_wp10_r2.py -q -p no:cacheprovider --basetemp=.test-runs/wp10r2-supplemental-eca9 --junitxml=docs/implementation/phase-04/evidence/wp-10-review-r2/supplemental.xml`


## 3. 四项复核判断

### ISSUE-001：部分修复，UNRESOLVED（功能收缩；原安全漏洞已阻断）

亲测location_role和within_exclusion均正确拒绝：部件介绍不再充当位置，within_range不再直接授权排除。location角色受有界空间语法与真实引用检查，已有合法位置/步骤仍可用。

但是`backend/app/validators/proposal.py:134–144`对hypothesis/temporarily_excluded**无条件**添加ASSESSMENT_UNCERTAIN；`services/proposal_service.py:44`因此跳过支持判断。没有“读取更充分依据后允许”的分支；换支持实现也不能通过。其余三种assessment仅表示unknown/not_checked/insufficient_data且进入needs_input，不是合法诊断结论成功路径。

本轮补充两组由审核夹具明确编写的合成规则：

1. 原文明确“观察到P01插头松脱时，将接触不良列为待验证假设”，并提供当前case中checked且connector_state=detached的观察。
2. 原文明确“外壳完整且当前测量合格时，仅暂时排除外壳破损，其他原因未定”，并提供housing_state=intact及当前有效批准规格的within_range比较。

规则经现有synthetic资料上传/解析/审核/索引/绑定，引用完整、case有效，步骤规格正例先通过。两次result的唯一错误均为ASSESSMENT_UNCERTAIN，support为空；不是缺引用、错case、失效比较或测试环境错误。见conclusion-hypothesis.json、conclusion-temporarily_excluded.json、supplemental.xml及测试第47行失败断言。

这些是**有界合法结论路径的审核正例**，不是宣称任意上传因果规则就应自动可信，更不是实际维修真值。即便不采用这两句作为最终受支持语法，代码也证明当前不存在任何可通过的这两类结论。位置/区域/步骤正例不能替代这一缺项。

与原计划/r1的关系：P4要求conclude_area及重要说法支持校验；r1允许“支持不足/无法可靠判定时保守拒绝”，不要求通用NLP，并只要求保留区域/步骤正例。本次门禁满足了**不误放行**的最小安全目标，但从按依据判断变成整类禁用，不能据此称五类提案校验能力完整恢复。整改契约虽然披露了收缩，但执行者改文档不是用户已接受缩减。

保留必须处理项（同一ISSUE，不新开工作包）：**P2功能缺项**。最小处理是明确至少一种可核验的有界结论/支持关系表达，使满足当前依据与观察的正例可通过，同时普通介绍/单一within_range仍拒绝；或者由用户明确决定接受不含这两类结论成功能力的缩减范围。无需实现通用语义引擎、真实裁判、发布任务或诊断图。本轮不替用户批准这种范围调整，不现场扩建。

复核只需该有界结论正反例及受影响门禁，不重开整包。原r1的P1误放行风险已解除，未把上述功能缺项夸大为新的数据泄露或不安全放行。

### ISSUE-002：RESOLVED，限定受支持语法

原表格choice、中文“一伏”inspect、engine=on与已审核off冲突三例均拒绝；现有批准Spec正例以及lower/upper/unit/conditions/quantity篡改反例通过预期检查。

表头确实从`support.py:117`的`locator.source.table_header`读取，`proposal.py:94–103`实际使用。除了3项单元测试，本轮做了真实PG/引用对照：保持同一合法步骤和非数值choice，把purpose从无单位的描述表行换为带单位/engine条件的标准表行。前者accepted=true；后者唯一错误为STRUCTURED_SPEC_REQUIRED，没有CHOICE_SEMANTICS_UNCERTAIN。provenance中真实表头含engine=off，见table-header-only.json。这证明表头门禁独立参与，而非借另一门禁提前拒绝。

动作数量/物理量集合、component、规格版本及实际engine条件与批准定义绑定；定义中的单位、范围、包含标记仍逐字段硬校验。没有改WP06 Decimal比较器。当前只支持列明动作/对象、engine on/off及有限非数值choice；其他表达明确待补，自由interpretation也统一待补。该能力不是通用表格单位抽取或中文数字理解；不将这些未实现能力写成通过。此限制已披露，针对原三个绕过与批准规格使用路径，整改成立。

### ISSUE-003：RESOLVED，v2受信历史边界

`repetition.py:32–42`解析操作/当前部件/受控实际对象；`:57–82`将其写入v2指纹，而非仅inspect或原始title。真实插头→外壳历史测试允许下一检查；同检查改标题/检查→查看指纹相同，重复分支仍有效。不同部件和工况键不同。

`proposal_service.py:73–81`明确拒绝无v2前缀历史；本轮old_history返回HISTORY_UNSUPPORTED。没有清空、自动加前缀或猜测旧对象的代码。可信history不来自模型输入，本包没有持久调用方迁移；文档要求未来调用方从原检查内容重建，不能简单加v2。此为兼容限制，不冒称旧记录自动升级已完成。

### ISSUE-004：RESOLVED，当前受支持测量对象范围

`proposal.py:464–505`以规范化component、spec_id版本、quantity、完整conditions分组；本包受控measure对象是部件对应的电压/电阻/压力/温度，尚无针脚等任意子对象语义。每个拟复测组都必须具备有效within/out两种结果。真实跨电压/电阻规格反例拒绝，不能跨组拼冲突。

亲测同spec/同工况真实冲突允许；单记录、错case观察、撤销后重新批准但旧比较仍invalid、不相关理由、第二次复测均拒绝。检查结果不是仅从线程或随机时序推断；这些用例是实际数据库关系/状态校验，无并发窗口改动需要新增锁演练。保留当前case/revision、checked、部件、当前比较有效性和同检查history门禁，不增加观察写入或工作流。

## 4. 限定接受边界与必要能力

可供用户限定接受的已验证部分：来源/身份/冻结范围等r1未变保护；有界区域与位置/步骤；批准规格使用绑定、表格标准门禁；对象级去重和同组冲突复测；未知/未检查/资料不足待补。A405本次整改范围通过，A404原误放行反例通过。

**尚未实现且不能被上述正例替代**：有充分依据时hypothesis/temporarily_excluded的成功路径及其支持关系表达。因此不建议按原“五类提案均具有有据判断能力”收口；本轮总体CHANGES_REQUIRED，而非BLOCKED（环境与测试可运行）。若用户另行明确接受上述缩减范围，应在接受记录中排除合法结论成功能力，不能把它变成已经实现的WP10功能。这里不是接受整个P4或授权WP11。

非阻断限制：有限工况/对象语法可能过度待补；自由interpretation、复杂推理、任意表格解析未实现；旧history需可信重建。性能、owner粗锁、监控和清理仍为既有待办，不据此要求扩建或拒绝已验证子范围。

真实资料NOT_MET，原WP10/真实效果前截止要求未满足，不因合成数据通过顺延；E10保留既有deepseek-flash限定证据，Linux BGE未验证，历史SSE/Compose根因未确认、同任务流程限制等不变。没有真实维修语义/效果或生产恢复结论。

## 5. 停止与交付

本轮只新增此报告、evidence/wp-10-review-r2及隔离工件。未修改实现、STATUS、接受记录、旧项目、旧迁移、历史证据或Git index；没有付费调用、提交推送或进入WP11。测试失败原样保留，未现场修复。报告及证据由本轮seal.json封存，等待用户决定。
