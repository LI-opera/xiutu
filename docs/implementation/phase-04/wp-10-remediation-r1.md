# WP-10 r1 四项整改记录

时间：2026-09-19T02:42:54.991437+08:00。状态仍为 **IMPLEMENTED_NOT_ACCEPTED**。这是执行者整改与自测，不是审核关闭、REVIEW_PASS或用户接受。仅处理ISSUE-001—004，等待一次针对差异的定点复核；不进入WP-11。

## 基准与保护

开始逐项核对r1 baseline、seal、报告及证据，共3,970个受保护文件匹配，无未解释差异。main，无HEAD；Git index SHA256为`c451d6e78b8f29fc818002923a19fb1a888139ced20679ad545f75e9692a9ec6`。见[evidence/wp-10-remediation-r1/baseline.json](evidence/wp-10-remediation-r1/baseline.json)及git输出。

只修改四个直接实现文件：`validators/proposal.py`、`validators/support.py`、`validators/repetition.py`、`services/proposal_service.py`；新增正式集成回归`tests/integration/test_wp10_remediation.py`与单元回归`tests/unit/test_wp10_role_grammar.py`。同步WP10契约/API说明，仅修正STATUS首段过时的“WP10—17未开始”。未改schema字段、WP06比较器、模型网关、预算、迁移或持久化流程。JSON schema与Pydantic导出完全相同，见schema-check.json。

原审核反例与历史失败日志保持原样。正式回归从原反例提升，原业务断言AST一致（promoted-assertions.json）；后来仅给表格实例追加更强的STRUCTURED_SPEC_REQUIRED断言，不修改原断言。原7个失败实例均已纳入正式回归，不通过放宽预期结果消除失败。

## ISSUE-001：字段及完整结论

根因：原逐字支持只校验claim.text与quote相等，没有考虑location角色或assessment的诊断含义。

修改：HardGate增加源支持的显式空间关系语法；普通部件介绍返回LOCATION_UNCERTAIN。assessment的hypothesis/temporarily_excluded不能仅靠抽取文字或within_range授权，缺少显式已审核因果/排除关系时返回ASSESSMENT_UNCERTAIN。观察有效性及冲突检查仍运行，未检查与资料不足不改成排除。

现有接口没有表达已审核排除关系的结构，因此本次不伪造可通过的诊断结论。此限制明确写入契约；不是通用NLP实现。合法区域、实际位置、观察步骤和批准测量步骤均有真实PG正例通过，没有将所有提案拒绝。对应：business_boundaries[location_role/within_exclusion/valid]、原WP10正例与CLI。

## ISSUE-002：使用处数值与工况

根因：阿拉伯数字检测漏掉表头语义和中文数词；原硬校验只验证asserted定义等于数据库，没有将定义绑定实际动作及工况。

修改：动作必须匹配完整有界操作/部件/对象语法，inspect不能包含“一伏”等附加判断；choice只允许契约列明的非数值观察，自由interpretation待补。测量动作quantity集合须等于input测量集合，实际步骤engine工况必须等于人工批准Spec.conditions。component、quantity、unit、上下界/包含标记仍逐字段匹配已审核定义，保留Decimal路径。

表格依据读取不可变`locator.source.table_header`的单位和适用条件，标准行不能独立作为choice或判断。无法可靠解释的载体返回待补，不承诺任意自然语言数值解析。批准结构化Spec是数值判断的唯一入口；其额外引用可保留原表格来源，不将表头作为模型可改配置。

三个原反例table_numeric/chinese_number/condition_conflict均拒绝；批准1—2V、engine=off步骤正例通过。旧规格字段篡改测试继续通过。

首轮53项后检查原始locator时发现表头读取层级错误：反例已被choice门禁拒绝，但不能据此证明表头校验。修正source层级后追加真实表格错误码断言及3个单元例。记录见post-targeted-correction.txt；最终4项通过。没有扩大测试到旧工作包。

## ISSUE-003：检查对象与历史

根因：fingerprint只存操作类别，丢失插头/外壳等对象。

修改：有界动作解析得到操作、规范化部件、规范化对象（connector/housing/appearance等），加入`v2:<sha256>`指纹；title不参与，检查/查看/观察同义词归一。不加入未经规范化的整段措辞。测量规格版本/工况继续参与。

旧无版本history返回HISTORY_UNSUPPORTED；不能视为从未检查，不能直接添加v2前缀、删历史或猜对象。可信调用方须从原始检查内容重建；不新增后续包持久化。接口文档已同步，请求schema形状未变。

插头与外壳正例、同检查改标题/同义词重复、不同部件及工况键、旧history安全拒绝均通过。

## ISSUE-004：同组冲突与复测

根因：原全局outcomes集合可用电压within_range和电阻out_of_range拼出虚假冲突。

修改：按规范化部件/测量对象、spec_id版本、quantity和完整conditions分组，每个拟复测组都必须有有效within_range与out_of_range。只支持当前有界“本部件测量记录冲突，需要同工况复测”理由，并关联拟复测的全部组。不同规格或不同工况不能混合。保留case/revision有效观察、checked/部件关联、比较当前有效性、原检查历史和最多一次复测；重新批准规格不清除旧比较needs_review。

跨规格伪冲突拒绝；同规格同工况真实冲突通过；单记录、错case观察、撤销后重新批准但比较仍失效、第二次复测、错动作quantity、不相关理由和旧history全部拒绝。测试只用隔离观察fixture，不建立观察写入API。

## 本轮实际命令与结果

cwd均为`E:/Work/xiutu-v5`。命令前缀：`.venv/Scripts/python.exe -B docs/implementation/phase-04/evidence/wp-10-remediation-r1/run.py`。每个label的json记录完整command、cwd、起止时间、退出码；txt为原始输出，XML记录统计。run.py静默读取本项目受保护数据库凭据，只连全新`xiutu_test_wp10fix_da4f33700e98`，未读取私有.env或真实费用账本。

| label / 实际操作 | 退出码 | 结果 |
| --- | --- | --- |
| create：prepare_database.py --name xiutu_test_wp10fix_da4f33700e98 | 0 | 新库，不覆盖历史 |
| migrate：python -B -m alembic upgrade head | 0 | 仅新库执行现有迁移 |
| targeted：pytest unit/test_wp10_schema.py + integration/test_wp10_proposals.py + test_wp10_context.py + test_wp10_remediation.py | 0 | 53 passed，0失败/错误/跳过，无警告，172.58秒 |
| demo：python -B scripts/demo_proposals.py | 0 | 免费CLI 1 passed，11.42秒；合成HTTP/索引/引用/候选与待补输出 |
| header-targeted：新增单元表头3例+真实表格反例 | 2 | 单元/集成文件同名导致收集错误，业务用例未执行；原日志/XML保留 |
| header-corrected：单元文件改名test_wp10_role_grammar.py，同4例 | 0 | 4 passed，0失败/错误/跳过，无警告，9.41秒 |
| lint-final：ruff check四实现及两新增测试 | 0 | All checks passed |

完整pytest命令、唯一basetemp与正斜杠JUnit路径见targeted.json/header-corrected.json。所有账本均为既有网关测试的隔离MockTransport临时账本，无付费请求。Docker29.4.0及xiutu-v5-postgres-1项目标签/loopback5433归属见环境json；没有停止数据库、删除既有库卷或改实际密码。测试结束仅清理fixture创建的进程，测试库保留。

53项是最后表头层级补正前的定点版本；最终层级修改只重跑受影响4项，CLI也是该补正前执行，未虚称最终字节版本全量重跑。演示表头是部件/位置描述而非单位/工况标准；补正的实际标准表路径已由4项覆盖，未重复同等CLI。各轮不累加为不同功能覆盖数。

历史完整364项、收尾35项及r1审核反例属于各自历史基准，本次未重跑364、前端、第二环境、BGE质量或E10。初次编辑因默认GBK解码失败且未写文件，随后显式UTF8；初次提升测试的lint格式问题经格式化解决，见tooling-notes.txt。唯一运行失败为上述收集错误，未削弱断言。

## 封存、影响与停止点

结束核对见protection-final.json：历史报告/原反例/失败日志、接受记录、旧迁移、旧项目63项及原虚构资料不变，Git index不变。当前改动清单及SHA256见delivery-hashes.json；报告与本次证据另由seal.json封存，不含.env/真实账本。

仍保留同任务实施/整改/审核的流程限制；本报告只自测，不自行关闭审核问题。WP10仍IMPLEMENTED_NOT_ACCEPTED，等待四项差异定点复核，不进入WP11。

真实资料NOT_MET，原WP10/真实效果前门槛未满足，未顺延或以合成资料替代；E10沿用WP09 deepseek-flash限定证据，Linux BGE部署未验证，历史SSE/Compose根因未确认，其他非阻断待办保留。未建设通用语义理解、诊断图、观察写入、正式报告或网页，不代表真实维修效果。
