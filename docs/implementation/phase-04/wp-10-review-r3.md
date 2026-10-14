# WP-10 ISSUE-001 剩余结论路径定点复核 r3

结论：**REVIEW_PASS（限定合成资料技术范围）**。ISSUE-001的有据hypothesis/temporarily_excluded成功路径及原误放行保护已在本次两类结构模板范围内完成验证，判定**RESOLVED**。结合r2未变部分，建议用户接受WP-10限定技术交付；ISSUE-002—004保持已关闭，不重开整包。没有发现本次差异必须继续整改的问题。本结论不是用户接受、真实维修效果或整个P4验收。

时间：2026-09-19T09:07:04.845862+08:00。**本任务参与过实施、整改及先前审核，本轮是同任务切换审核角色，不属于不同任务独立审核。** 本轮没有修改业务实现、原测试、STATUS或接受记录。

## 1. 基准、差异及版本

已检查项目/上级及项目内适用AGENTS路径，未发现适用AGENTS；读取STATUS、r2审核、r2整改、当前契约/API/schema、结论规则/校验器、proposal_service、相关差异、观察repository及证据有效性服务、测试和来源映射。

整改delivery-hashes.json、seal.json（报告与全部证据）、Git index均与当前一致。审核固定 **4172项** 输入，开始/结束均无差异。main无HEAD，未仅依靠git diff；git根/分支/HEAD/status输出见git-*.json。index SHA256为c451d6e78b8f29fc818002923a19fb1a888139ced20679ad545f75e9692a9ec6。

相对原r2审核，六份既有文件变化与声明一致：agents/state.py、validators/proposal.py、services/proposal_service.py、WP10契约/API说明及模型提案schema；新增可信规则/结论校验器/测试/映射与应用专用schema等。support.py、repetition.py、WP06服务/比较器、旧迁移、预算等未变。difference-review.json记录核对。新增superseded夹具修正只推进隔离case/后继观察revision，保留旧ID及拒绝断言，未弱化业务要求。

原r2两个无映射结论正例的失败记录、原断言及历史日志未覆盖。新路径增加可信结构关系，不将旧“只有自然语言来源”输入偷偷解释为已审核规则。来源映射hash指向原r2测试文件且实际匹配；两条是审核新增合成规则，不冒称来自用户原虚构资料。

结束旧项目63项保护文件及原虚构资料/副本未变；STATUS、接受记录、历史证据和Git index均未变。见verification.json、baseline.json。私有.env、真实费用账本均未读取或封存。

证据版本严格分开：历史完整364项不代表当前完整回归；整改新增首轮22通过/1失败/1错误，后续2通过，最终受影响回归22通过，不是新增24项最终整体重跑。本轮实际重新运行最终24项结论测试及5项规则测试，另3项受影响回归，不累加重复历史运行作为功能覆盖数。

## 2. ISSUE-001成功路径与信任边界

**RESOLVED，仅限以下两种模板。**

| 模板 | 当前实际前提 | 获准候选范围 |
| --- | --- | --- |
| connector_detached_hypothesis | 当前owner/case/revision下checked、同对象/engine工况、connector_state=detached观察 | 接触不良待验证假设；confirmed=false，尚未确诊 |
| housing_intact_comparison_exclusion | housing_state=intact观察，加精确批准Spec与当前有效合格比较，工况/定义一致 | 仅暂时排除外壳破损，其他原因未定，不是整件正常 |

本轮P01/Q02各两类正例实际通过（conclusion-success-*.json）。生产代码按kind/component字段解释受控模板，没有P01专用分支或按审核句子选择程序跳转。模板仍是小型人工/可信代码批准的结构关系，不证明一般因果推理或任意文字理解。

`agents/conclusion_rules.py:17–52`定义应用专用不可变映射，绑定owner/case/profile、component、证据/版本/hash/epoch、reviewer/time、engine，排除另绑定Spec ID及完整定义hash。`validators/proposal.py:56–65`仅从可信构造参数接收对象、最多16项、唯一ID并固定映射。`agents/state.py:82–91`的模型候选只允许规则ID/结论scope，不包含规则正文或审核授权字段。模型提供随机ID、reviewed/rules/premises_satisfied、错scope/assessment/对象均拒绝。

**信任来源是可信应用装配，不是上传文档approved，不是UUID或hash本身。** reviewer/time是该可信装配的审核责任记录，不是系统验证人员资质或签名的功能。默认无规则，未装配时ASSESSMENT_UNCERTAIN；测试夹具单独明确提供映射，生产不加载它。与用户允许的小型有界关系一致，不要求本包扩建生产审核UI/注册平台。

`validators/conclusion.py:18–66`复验映射归属、来源版本/hash/epoch、现有资料有效性及精确适配，并要求finding只引用已映射的唯一完整来源。quote相等只是关联完整性；还必须由可信规则和实际数据库前提授权。输出`conclusion_support`由服务生成限定statement（约第173行起），候选finding不直接充当结论。published=false/diagnosis=false保持。

## 3. 前提、反例及最终重验

`ObservationRepository.read`按当前case/revision读取有效观察，排除已被替代记录；原case/revision、冻结manifest和当前资格门禁保留。`conclusion.py:68–105`要求所选有效观察提供状态前提，并扫描未选择的相关观察；不允许藏掉冲突、未检查或错工况记录。

排除路径（约第107–172行）复用当前证据及get_comparison有效性：Spec必须approved且未needs_review、同case/对象/工况、完整定义hash一致；比较必须同case/同Spec、当前有效、输入工况和定义一致并为within_range。既有审核撤销后重新批准不清除旧比较复核要求。

本轮实际反例覆盖：

- 模型伪造规则/审核信息、错owner/case/profile/version/hash/epoch、扩大对象/assessment/scope、无映射；
- 缺一个前提、未检查、观察相反、工况不符、旧观察已替代；
- 错Spec、跨case比较、失效比较、撤销来源、未选中的超限比较；
- 单一within_range及普通部件介绍仍不能授权排除/位置；
- unknown/not_checked/insufficient_data仍needs_input且无有效结论支持。

`proposal_service.py:20–23、97–125`在支持判断前后均通过owner锁调用硬门禁。三项最终重验测试在真正支持回调期间通过HTTP撤销来源/规格或插入真实隔离冲突观察，随后最终门禁拒绝且conclusion_support=None。回调只控制发生变化的时点，不替换数据库有效性规则。返回候选不等于后续正式发布，不承诺锁释放/网络返回后的即时撤回。

原位置、支持/身份/数值及单一within_range误放行回归也实际通过。ISSUE-002—004引用原r2已验证且算法未变的结论；此次不重新开启它们。

## 4. 本轮环境及命令

最初Docker Linux引擎管道不存在，docker version/inspect exit1；创建测试库、迁移连接超时exit1，业务用例未执行。没有将其写成业务断言失败。用户表示将启动现有服务后，只读复查确认Docker29.4.0恢复、xiutu-v5-postgres-1 running、project/service标签正确且127.0.0.1:5433归属匹配；没有自行重建/修改容器。

新隔离库：**xiutu_test_wp10r3_2d5571f4f684**。create-ready与migrate-ready成功，只应用已有0008迁移准备隔离库，没有修改迁移文件或重做迁移验收。旧库/卷未删除，测试API/worker由既有fixture创建和清理，不停止未知服务。

仅静默加载项目受保护DB凭据用于新测试连接，APP_MODE=test；current_import证明导入当前工作区backend。没有私有.env、真实费用账本、付费模型、BGE/E10/质量评测、未变CLI、前端或第二环境运行。真实HTTP资料/规格准备与PostgreSQL门禁没有被mock替代。

| 本轮执行 | 统计 | 退出码 |
| --- | --- | --- |
| unit.xml | 5通过，0失败/错误/跳过，0.07秒 | 0 |
| targeted.xml | 27通过，0失败/错误/跳过，286.04秒 | 0 |

27项为最终新增结论24项及原location_role、within_exclusion、hard_source_support_and_repetition三项。已包含最终重验，未重复选等价实例。每项本轮只执行一次，无警告输出，未放宽断言或重跑到通过。5项规则测试单独先运行，不重复纳入后续集合。schema-source.json确认两个导出schema与运行时完全一致、映射源hash匹配。

本轮测试启动超时未复现，**历史首次根因未确认**；本轮成功不代表已修复平台问题。原整改API启动失败记录与本轮Docker不可用记录是不同事件，均保留。

cwd均E:/Work/xiutu-v5。以下命令/时间与同名.json、.txt原始日志一致，JUnit使用正斜杠；selection.json记录最初计划，实际完成状态以execution.json和本报告为准。

- **create**：exit 1；2026-09-19T08:57:57.105977+08:00 → 2026-09-19T08:58:00.412569+08:00。
  `E:\Work\xiutu-v5\.venv\Scripts\python.exe -B scripts/probes/prepare_database.py --name xiutu_test_wp10r3_2d5571f4f684`
- **migrate**：exit 1；2026-09-19T08:58:00.499753+08:00 → 2026-09-19T08:58:03.919333+08:00。
  `E:\Work\xiutu-v5\.venv\Scripts\python.exe -B -m alembic upgrade head`
- **unit**：exit 0；2026-09-19T08:58:29.041013+08:00 → 2026-09-19T08:58:30.968470+08:00。
  `E:\Work\xiutu-v5\.venv\Scripts\python.exe -B -m pytest tests/unit/test_wp10_rule_contract.py -q -p no:cacheprovider --basetemp=.test-runs/wp10r3-unit-c7b3 --junitxml=docs/implementation/phase-04/evidence/wp-10-review-r3/unit.xml`
- **create-ready**：exit 0；2026-09-19T09:00:11.390014+08:00 → 2026-09-19T09:00:12.128539+08:00。
  `E:\Work\xiutu-v5\.venv\Scripts\python.exe -B scripts/probes/prepare_database.py --name xiutu_test_wp10r3_2d5571f4f684`
- **migrate-ready**：exit 0；2026-09-19T09:00:12.224578+08:00 → 2026-09-19T09:00:13.438005+08:00。
  `E:\Work\xiutu-v5\.venv\Scripts\python.exe -B -m alembic upgrade head`
- **targeted**：exit 0；2026-09-19T09:00:13.526343+08:00 → 2026-09-19T09:05:01.332702+08:00。
  `E:\Work\xiutu-v5\.venv\Scripts\python.exe -B -m pytest tests/integration/test_wp10_conclusions.py tests/integration/test_wp10_remediation.py::test_business_boundaries[location_role] tests/integration/test_wp10_remediation.py::test_business_boundaries[within_exclusion] tests/integration/test_wp10_proposals.py::test_hard_source_support_and_repetition -q -p no:cacheprovider --basetemp=.test-runs/wp10r3-targeted-b6d2 --junitxml=docs/implementation/phase-04/evidence/wp-10-review-r3/targeted.xml`

## 5. 建议接受范围与保留项

结合r2未变结论，WP-10可建议在**合成资料、有界五类提案校验、批准规格硬校验、对象去重/复测、当前两类可信结论结构模板**范围内接受。ISSUE-001剩余功能缺项在该范围内关闭，无本次新必须整改项；用户接受权保留。

非阻断/未实现边界继续保留：规则仅由可信应用装配，生产默认无规则；模板之外的自由推理待补，不能自动从人审文档抽取可执行规则；未来真实规则装配与观察写入接入须复测信任和revision边界。没有通用NLP、生产规则UI、持久诊断图、正式观察写入、报告发布、网页或生产恢复验收。owner粗锁、性能/监控/清理等既有待办不扩为本次阻断。

真实资料NOT_MET，原WP10/真实效果验收前截止要求尚未满足，不因合成规则获准而顺延或标通过；合成规格不是维修标准，within_range不代表部件正常。E10保留已验证deepseek-flash限定证据，Linux BGE未验证、混合模型排序待办、历史SSE/Compose未确认根因及同任务流程限制不变。

本轮仅新增本报告和审核证据/隔离工件，不修改实现、STATUS、接受记录、历史/旧项目/迁移或Git index。没有提交推送、付费调用或进入WP-11。停止，等待用户决定。
