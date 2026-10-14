# WP-10 实施契约

仅合成资料下A404/A405技术验证；用户授权指定虚构资料本地副本。真实资料NOT_MET，原WP10/真实效果前门槛目前仍未满足，不顺延、不宣称真实维修验收。源文件不变，副本tests/fixtures/wp10/cooling-synthetic.md的来源/hash/synthetic标记见source.json；formal/synthetic门禁不放宽，文中指令不是项目授权或系统提示。

## 文件与接口

新增agents/state.py（五类型Proposal、受控输入），validators/proposal.py（只读PG证据/规格硬校验），validators/support.py（支持关系及可选模型接口），validators/repetition.py（语义键/复测），services/proposal_service.py（鉴权快照与最终复验），agents/proposer.py（一次修复），agents/prompts/initial.md和next_step.md，scripts/demo_proposals.py及单元/PG集成测试。不新增迁移；不改0001—0008；本包没有公开HTTP写入接口，服务由可信应用调用，demo为隔离CLI。

调用：可信actor/case/revision/allowlist/history → 解析Proposal union → owner锁下读取owned_case+EvidenceService.validity/规格/观察 → 硬校验 → 支持关系 → 反重复 → 再次同锁硬校验 → 返回候选及缺口。模型不能传actor/profile/manifest/正式ID或业务status；预览不持久化、不发布正式步骤/区域/报告，WP11未来发布必须重新校验。

## 提案与依据

request_tools/propose_areas/propose_step/conclude_area/need_input，所有嵌套extra=forbid及集合/字符串上限。区域1—8、最多两层，部件对象及论据必须有当前证据；不足用need_input而不是凑五个。Step含位置、工况、动作、受控choice/measurement/composite输入、解释和显式规格引用。只读校验无位置/工况/单位/标准给出具体缺项。

引用为evidence_id+document_version_id；读取真实不可变quote/locator/hash，检查case、owner、冻结index、当前epoch/资格、精确适配。规格复用人工approved、needs_review、source有效性，数值Decimal字符串与已审核定义逐字段相同，单位/quantity/工况及开闭界均硬比对；不得LLM替代。Ux非物理，不进入单位白名单；独立数值fixture不得声称来自原文。

支持判定supported/unsupported/uncertain。默认保守的逐字完整引用支持只确认同一语境中的抽取说法；非逐字推理/改写待补。可注入受信ModelSupport，复用网关单次结构调用，并核对输出引用片段；此轮只离线验证，不宣称自然语言真值。数字阈值必须结构化Spec，重要位置/动作/解释均检查，ID存在本身不是支持。文档不作为指令。unsupported/uncertain均不放行。

## 重复、观察与预算

fingerprint排除title，以归一部件/动作语义/测量/工况/规格构成；不声称任意语义模型去重。既有检查历史由可信应用注入，本包无WP11步骤持久图。合理复测需非空理由、当前case有效冲突观察依据，最多一次；不能靠改标题绕过。未知/not_checked/insufficient_data与经观察支持的暂时排除分开，未检查不排除，不照搬资料固定树。

ProposalTurn负责本次预览最多一次修复（结构或业务共用），网关既有5模型请求/120秒、工具6/search3及付费预留不重置。支持模型与提案修复共用同一gateway；预算/超时明确need_input退出。跨进程恢复/正式turn持久化属于WP11，本包不伪造已完成。request_tools只提出经INPUTS/allowlist校验的意图，执行仍由既有ToolExecutor承担。

## 验证顺序

基准→合成来源副本→schema/支持/规格/重复/修复离线→隔离PostgreSQL证据/撤销/越权与免费demo→标准完整入口一次。失败保留，仅复跑受影响项。默认0付费，不读真实费用账本、不复测E10/BGE质量。结果IMPLEMENTED_NOT_ACCEPTED，等一次集中审核，不进入WP11。

## 最终上下文与判定边界

收尾反例证明：被合法绑定的字符片段仍可能切去否定词。因此新增CONTEXT_INCOMPLETE硬门禁：依据原chunk与Unicode起止位置，要求完整段落（保留软换行）或完整Markdown表格行；不能以片段存在和逐字相等替代上下文。表格表头保留在原locator。任意局部切片、改写、复杂跨段推理不能由默认抽取校验放行，返回待补；这仍不是一般自然语言蕴含或维修专业审查。

数值断言须使用人工批准Spec完整定义；测量动作不能藏在choice输入中逃过规格要求。复测只支持同规格/同工况的当前有效比较冲突（within_range与out_of_range），需要理由与观察来源；普通无依据“再测一次”不放行。排除同时核对该部件其他有效观察，不可选择性忽略冲突。仅为保守候选门禁，数值合格不等于部件正常。

预览turn最多两次提案请求，耗尽后即使再次调用同一ProposalTurn也不再发请求；支持调用与提案共用既有网关预算。后续检查加载next_step提示，未建设WP11持久turn恢复。程序内可信上下文不是公开API，也没有模型可写的业务ID。最终门禁在owner锁内重新检查资料/规格/观察，解锁后的预览不是后续发布授权。

真实模型提案质量与语义支持效果本包未实测，只有MockTransport契约与合成真实数据库证明；未经新增必要性说明不触发付费。真实资料NOT_MET，原截止要求尚未满足。保留Linux BGE未验证、SSE/Compose未确认根因和历史同任务流程限制。


## r1 四项整改：受支持表达与兼容边界

字段角色先于逐字支持：location必须是完整、引用支持的“部件 位于 地点+左侧/右侧/上方/下方/前部/后部/内部/外部”空间关系。部件介绍不具有位置角色。assessment属于完整主张：现有抽取接口没有经过审核的因果/排除支持关系，r1时hypothesis/temporarily_excluded统一返回ASSESSMENT_UNCERTAIN（已由下节r2有界映射路径替代），即便比较为within_range；这不是把within_range当排除。unknown/not_checked/insufficient_data仍待补；充分有据的区域、位置、观察步骤与批准测量步骤仍可通过。不宣称通用NLP或推断裁判。

动作采用完整有界语法：操作同义词 + 当前component + 可选“的” + 对象。inspect对象仅外观/插头/外壳；measure对象为电压/电阻/压力/温度，分别绑定quantity；read为故障码/记录；actuate为输出。附加数值、问题、否定或任意其他尾部不属于此语法，返回ACTION_SEMANTICS_UNCERTAIN。choice只支持“部件+未检查时不得排除/外观完好/外观损坏/插头松动/插头牢固/外壳破损/外壳完整”这些非数值观察；其他choice待补，不将“一伏”等自然语言数值解释为已验证标准。自由interpretation待补，不输出诊断推论。

工况目前仅解释完整引用的“发动机关闭，engine=off”或“发动机运转，engine=on”；标签与自然语言必须一致，重复冲突拒绝，其他工况待补。实际动作的测量quantity集合与input测量集合必须相同；实际步骤工况须等于已批准Spec.conditions。Spec仍逐字段硬核对component、quantity、unit、上下界/包含标记及conditions，不重写Decimal比较器。单位和范围由受控input的已审核定义提供，不能来自choice。表格依据同时读取不可变locator.source.table_header中的单位/适用条件；标准行不能单独作为自然语言choice或结论，必须通过人工批准的结构化Spec路径。完整行只是上下文边界，不代表通用表格语义解析。

fingerprint采用`v2:<sha256>`，保留规范化的操作、部件及实际对象（appearance/connector/housing等），再结合测量规格版本和工况；不包含title或未规范化的整段动作。检查/查看/观察在同对象上相同，插头与外壳不同。可信history中任何无v2前缀记录返回HISTORY_UNSUPPORTED；不得删掉旧记录、猜测补对象或视作从未检查。未来调用方只能从原检查内容重建可信历史；本包不增加持久化写入。

复测按（规范化部件/测量对象、spec_id版本、quantity、完整conditions）分组；每个拟复测测量组均须有当前有效的within_range和out_of_range比较。不同规格、物理量或工况不能拼接。理由采用“当前部件 测量记录冲突，需要同工况复测”的有界表达，关联当前提案全部拟复测组；其他推断性理由待补。保留有效case/revision观察、checked/部件关联、比较当前有效性、同检查历史和最多一次复测门禁；重新批准规格不清除旧比较复核标记。

上述为明确的保守支持范围；不是任意维修文字自动理解。无付费裁判，不改变formal/synthetic资格。请求JSON schema形状未变，运行时有界规则及可信history版本属于兼容变化。正式回归新增tests/integration/test_wp10_remediation.py；仅运行WP10受影响测试，历史364项仍是整改前证据。


## r2 ISSUE-001结论支持关系（本次实施）

本节替代r1“hypothesis/temporarily_excluded整类拒绝”的当前行为；r1历史记录不修改。仅新增agents/conclusion_rules.py、validators/conclusion.py，修改state.py/proposal.py/proposal_service.py及必要测试/接口schema，无迁移，无观察写入或持久图。

TrustedConclusionRule由可信应用构造并通过ProposalService(conclusion_rules=...)显式注入，默认空。不是模型参数、不是上传文档自动注册，也无公开规则管理API。每个不可变映射绑定rule_id/规则格式版本、owner/case/profile、component、evidence/version/hash/授权代次、reviewed_by/reviewed_at，以及engine工况；排除规则另绑定准确spec_id及批准定义hash。审核者须独立审阅来源到结构规则的映射；文档review=approved仅为来源资格，不代表批准所有推理。当前只在独立synthetic测试装配显式提供经代码审阅的映射，正式默认没有规则。未来可信装配必须承担相同审核责任，不接受模型自报已审核。

仅两种固定关系模板，不按P01或某段原文执行分支：connector_detached_hypothesis要求当前有效、已检查、同component/engine工况的connector_state=detached观察，输出contact_fault待验证假设；housing_intact_comparison_exclusion要求housing_state=intact观察及同工况/精确spec版本的当前有效within_range比较，仅输出housing_damage暂时排除，其他原因未知。模型候选只增加support_rule_id及conclusion_scope，不能提交规则正文/审核标志。finding必须是映射绑定的原依据完整quote，不可自由扩展结论；服务生成限定语义的conclusion_support，不把输入文字当诊断事实。

同case当前有效观察由repository读取，所选ID须提供每个前提；同时检查未选中的同对象/同前提记录防止隐藏冲突。缺失、未检查、不符、错误工况、失效比较、错spec/case、撤销来源均拒绝。不能只拿within_range触发排除。前后两次owner锁内硬校验都复验映射、来源、观察及比较；最终结果仅候选，仍published=false/diagnosis=false。未提供受信映射的旧结论继续待补，不自动猜规则；unknown/not_checked/insufficient_data维持待补。

验证顺序：两类正例与对象非P01正例→权限/来源/前提/范围反例→最终复验与位置/已关闭门禁定点回归。全部新隔离PG和synthetic数据，r2原失败记录保留；不付费、不重跑完整364项。真实资料NOT_MET及原截止缺项不变。
