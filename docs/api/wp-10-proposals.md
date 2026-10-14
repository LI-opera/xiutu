# WP-10 提案校验接口（合成技术范围）

本包提供应用内接口与隔离CLI，不新增公开HTTP路由，不创建正式步骤、区域、观察、run或报告。

## 输入与调用顺序

`ProposalEnvelope`是带type判别的Pydantic union，完整JSON schema见[wp-10-proposal.schema.json](wp-10-proposal.schema.json)。五类为request_tools、propose_areas、propose_step、conclude_area、need_input。所有受控模型extra=forbid；模型不能指定actor/case/profile/manifest/status/正式ID。

可信应用构造`ProposalContext(actor, case_id, revision, allowed_tools, history)`，调用`ProposalService(engine, settings, support).validate(context, candidate)`。actor从登录或既有工具上下文取得；history只从可信既有检查生成，不能从模型JSON填充。owner锁内复用WP06资格和冻结范围，再做支持/重复检查，最后重新验证来源与revision。该最终点只批准预览；未来WP11持久发布必须重新鉴权和校验，不能沿用旧accepted结果。

## 返回

`accepted`表示候选符合本包技术校验；`disposition`为candidate/request_tools/needs_input；`issues`包含code/path/detail。`support`给出supported/unsupported/uncertain和原文；`provenance`含evidence/version/chunk/index/hash/locator。`fingerprint`用于重复检查。`candidate`只是模型候选；`published=false`、`diagnosis=false`。synthetic环境显式返回synthetic=true。

need_input可以是结构有效的accepted=true，但disposition始终needs_input，不能据此执行维修。unknown/not_checked/insufficient_data同样进入待补。没有观察不允许排除；存在冲突记录不能只挑正常记录排除。

典型错误：PROPOSAL_SCHEMA_INVALID、CITATION_INVALID、SOURCE_INVALID、CONTEXT_INCOMPLETE、SCOPE_NOT_MATCHED、LOCATION_MISSING、CONDITIONS_MISSING、SPEC_REQUIRED、SPEC_VALUE_MISMATCH、STRUCTURED_SPEC_REQUIRED、CLAIM_UNSUPPORTED/UNCERTAIN、DUPLICATE_CHECK、RETEST_REASON_UNSUPPORTED、RETEST_LIMIT、NOT_CHECKED、EXCLUSION_CONFLICT、REPAIR_EXHAUSTED。引用越权返回既有NOT_FOUND，不回显未授权原文。

## 有界修复与工具

`ProposalRunner(gateway, service).run(context, messages, ProposalTurn())`使用既有网关单次request，整个turn最多两次提案（一次修复），不另开结构修复预算。ModelSupport如启用必须共享同一gateway；默认ExtractiveSupport无需模型，仅保守抽取，无法确认改写或推理就uncertain。测试使用MockTransport，不证明真实模型质量。

request_tools仅返回通过既有INPUTS与可信allowlist的意图，最多6项/3次search；不直接执行。调用仍须进入已接受的ToolExecutor预算/权限/审计。本包没有自动Agent循环。

## 免费演示

在README已有隔离测试库准备步骤完成后，项目根执行：

```powershell
$env:PYTHONPATH = "$PWD/backend"
uv run --frozen python -B scripts/demo_proposals.py
```

必须设置loopback:5433的全新xiutu_test_*测试库TEST_DATABASE_URL，不回退开发库。需要已有本地E5供资料索引，不联网下载、不付费调用。入口使用真实HTTP上传/解析/审核/索引/建会话/绑定证据，再通过应用内接口打印资料片段、单个有据区域、缺工况/规格、无支持说法和未检查不能排除。工件保存.test-runs/wp10-demo-UUID，不删除历史。它是开发依赖下可复现演示，不是产品UI。

## 材料与边界

用户虚构原文件的字节副本及来源SHA256见tests/fixtures/wp10/source.json；没有把树转为跳转表。额外1—2 V/engine=off标准仅在extra-synthetic.md中标作新增虚构台架数据，与用户原文区分；Ux不是物理单位。原真实资料门槛仍NOT_MET，原WP10/真实效果前截止要求未满足，不能用本包技术测试代替。引用支持不等于真实维修结论；无正式Agent、图、观察写入、报告或页面。

默认支持校验另要求原chunk中的完整段落或完整表格行；截去否定/条件的局部quote即使UUID/hash/offset都真实也返回CONTEXT_INCOMPLETE。保守边界可能使长段落或复杂改写进入待补，这是明确限制，不宣称一般语义推理。


## r1整改后的运行时语义与history v2

请求JSON schema字段未改。请同时遵守[契约受支持表达](../implementation/phase-04/wp-10-contract.md#r1-四项整改受支持表达与兼容边界)：location需明确空间关系，动作需可解析的操作+部件+有界对象；自由数值choice、自由interpretation、未审核的因果/排除关系进入待补。测量动作quantity与已批准input规格绑定，实际engine工况必须相同。原文包含某句话不等于它能承担任意字段角色。

返回fingerprint改为`v2:<sha256>`；PriorCheck仍为可信应用的fingerprint/component_key/retest_count。旧无版本history返回HISTORY_UNSUPPORTED，不能当作未检查或原样添加v2前缀；从原始检查内容重建后才可使用。新错误包括LOCATION_UNCERTAIN、ASSESSMENT_UNCERTAIN、CONDITIONS_UNCERTAIN、CHOICE_SEMANTICS_UNCERTAIN、INTERPRETATION_UNCERTAIN、MEASUREMENT_USE_MISMATCH、SPEC_CONDITIONS_MISMATCH、RETEST_REASON_UNCERTAIN。

复测候选的每个spec/quantity/conditions组都需同组当前有效冲突；不能用不同规格的正常与超限结果拼接。最多一次复测及来源/观察有效性不变。新增正式回归tests/integration/test_wp10_remediation.py覆盖原七个反例及复测组合；本次不声称重新全量364通过。


## r2 有界结论支持接口

`ConcludeArea`新增可选`support_rule_id: UUID`和`conclusion_scope: contact_fault | housing_damage`。其他字段不变，extra=forbid。模型仅提规则ID，不能传`reviewed`、`rules`、`premises_satisfied`等授权数据。旧请求缺映射仍明确待补；unknown/not_checked/insufficient_data继续needs_input。

受信应用单独调用`ProposalService(engine, settings, support=None, *, conclusion_rules=(rule, ...))`，最多16个不重复ID的不可变`TrustedConclusionRule`。应用专用schema见[wp-10-trusted-conclusion-rule.schema.json](wp-10-trusted-conclusion-rule.schema.json)，**不是模型tool或公开API输入schema**。规则格式version=1，绑定owner/case/profile/component、证据ID/版本/quote SHA256/epoch、reviewer/time/engine；排除模板还绑定spec_id及定义的规范JSON SHA256。默认规则集为空，没有读取上传资料后自动执行的路径。

两种模板（component可变，不硬编码P01）：

| kind | 必要当前事实 | 输出限定 |
| --- | --- | --- |
| connector_detached_hypothesis | 同component、checked、同engine工况的connector_state=detached | hypothesis/contact_fault，仅待验证假设，尚未确诊 |
| housing_intact_comparison_exclusion | housing_state=intact，加同spec/定义hash/engine工况的当前有效within_range | temporarily_excluded/housing_damage，仅暂时排除外壳破损，其他原因未知，不代表整件正常 |

观察前提来自当前case/revision的有效DB记录；不能仅用候选给出的布尔值。selected IDs须提供每个前提，同时检查所有有效相关观察是否冲突，不能通过不选择坏记录来隐藏。未检查、缺值、不同工况、无效比较、错spec/case/对象、来源撤销及epoch/hash变化拒绝。旧有效性和最终owner锁内重验继续保留。

finding是来源原quote而非自由扩写的结论；必须与被审核映射的唯一依据完全对应。通过后服务返回`conclusion_support`：rule_id/hash、reviewer/time、来源、assessment、component、scope、conditions、服务端生成statement、observation_ids/comparison_ids、confirmed=false、other_causes=unknown。拒绝或未知状态没有有效conclusion_support。`candidate`仍为原输入预览，不能绕过这个结果当发布授权；published=false/diagnosis=false保持。

错误：ASSESSMENT_UNCERTAIN（缺可信映射）；SUPPORT_RULE_SCOPE_MISMATCH、CONCLUSION_SCOPE_MISMATCH、SUPPORT_SOURCE_INVALID/MISMATCH、SUPPORT_PREMISE_MISSING/CONFLICT、SUPPORT_SPEC_INVALID、SUPPORT_COMPARISON_MISMATCH/INVALID。通用来源/权限错误继续沿用。

仅合成测试装配提供本轮映射：tests/fixtures/wp10/conclusion-support-synthetic.json保留r2原句来源及hash，tests/integration/test_wp10_conclusions.py显式建立case关联与review记录。规则映射代码需要单独审阅，文档人工approved不等于批准其全部推理；本包没有规则管理/观察写入/正式Agent接口。真实业务装配默认无规则，不加载测试fixture。
