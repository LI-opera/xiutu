# WP-11 免费契约对齐 r1

时间：2026-09-20（Asia/Shanghai）。**WP-11 保持 BLOCKED**。本轮没有连接 DeepSeek、没有新付费 turn、没有读取或重置真实费用账本，也没有修改 WP-10 门禁、原 DKVB 资料包或业务实现。此前报告的剩余 ¥3.052520 小于 4 次请求最坏预留 ¥3.281920，不能据此再启动原方案的付费验证；这两个金额仅引用[上轮记录](wp-11-budgeted-live-r1.md)，不是本轮账本读数或平台账单。

## 与真实失败的对应关系

按真实探针的白名单流程，在全新隔离库 `xiutu_test_wp11_align_ca55ea69dee7` 中导入封存的两份 DKVB 合成正文，分别完成解析、明确的合成演示审核、E5 初索引和本地 BGE-M3 重建，然后用服务端 [VEHICLE](../../../backend/app/dkvb_preview.py) 创建虚拟 case。两个版本都进入该 case 的冻结 manifest，索引 ID 与版本 ID 见[脱敏取证](evidence/wp-11-contract-alignment-r1/dkvb-scope-summary.json)；未从旧专题或其他资料补入内容。原文仅在受限测试过程读取，以下只列章节/行号及规则，不复制正文或先前私有模型候选。

| 已存字段 | 资料审核范围与虚拟 case 的关系 | `applicability()`/WP-10 影响 |
| --- | --- | --- |
| model | `matched` | 无冲突 |
| engine_code | `matched` | 无冲突；纯合成反例将其改为其他代码时为 `mismatch` |
| engine_family | `unknown`，双方未给可核实系列 | `missing_engine_family` |
| year_from | `unknown`，未存下界且虚拟车无精确年款 | 年款不完整 |
| year_to | `unknown`，未存上界且虚拟车无精确年款 | 年款不完整 |

因此 `applicability()` 对两份资料均返回 **`unknown`、general_reference_only**。现有会话冻结规则允许非冲突的一般参考进入 manifest，但 `HardGate.load()` 对步骤中每项已绑定证据要求 **`matched`**，所以真实 trace 中各字段的 `SCOPE_NOT_MATCHED` 有明确、可在当前数据库重建的来源。专题正文包含部分车型起始年线索，不等于虚拟车辆有精确年款，也不提供完整的年款上下界和发动机系列；本轮没有填造它们或修改授权范围。`SCOPE_NOT_MATCHED` 在这里表示**信息不足以获得精确适配**，不是已证明车型冲突。

| 真实 trace code/path | 原规则及免费核对 | 来源定位与限制 |
| --- | --- | --- |
| `LOCATION_MISSING:location` | `ProposeStep.location` 为空即产生该码；上一真实候选原文未公开，不能还原其字段内容。本轮提供真实来源位置行后得到 `LOCATION_UNCERTAIN`：有来源图/表，不等于满足“部件位于…左/右/前/后/内/外”的限定句式。 | `维修知识手册.md` §2 对象表第 21 行及 CHK-04 第 99—111 行；不能从图号编造实车方位。 |
| `CONDITIONS_UNCERTAIN:prerequisites` | `operating_conditions()` 仅认识一致的“发动机关闭/运转，engine=off/on”结构。本轮所选 CHK-04 第 101 行不合该语法；两份正文共 118 个非空段落的精确语法扫描匹配为 0。 | `维修知识手册.md` CHK-04；这说明现有表达未被程序的有界语法识别，**不是**资料没有任何工况说明。 |
| `ACTION_SEMANTICS_UNCERTAIN:actions` | `action_key()` 要求操作别名、实际检查对象及受控目标（外观/插头/外壳等）同时成立；所选 CHK-04 第 105 行没有该结构。 | CHK-04 有实际检查说明，但不能从其较长段落抽出未明示的动作对象而宣称通过。 |
| `CHOICE_SEMANTICS_UNCERTAIN:input.choices` | 只接受 `component_key` 加限定的非数值观察状态；CHK-04 第 107 行列出的观察描述不是该结构。 | 原文观察分类不应被改写为伪造的预设选项。 |
| `COMPONENT_NOT_GROUNDED:actions` | 对 location/actions 等角色还要求选定对象出现在该 claim 中；免费候选选 `G31` 与另一检查段落的动作不一致，按原规则拒绝。 | 对象表与 CHK-04 不可跨对象拼装成一条新事实。 |
| `INTERPRETATION_UNCERTAIN:interpretation` | 原门禁对非空自由解释保持待补；本轮未用模型推断或演示阈值补成诊断结论。 | 历史 trace 只有受控 code/path，无法还原被拒绝的具体解释文本。 |

本轮用原文第 21、101、105、107 行对应的完整表格行/段落绑定真实 chunk、版本与 BGE 冻结索引，保留原文边界，`ProposalService.validate()` 返回 `needs_input`，包含 `SCOPE_NOT_MATCHED` 及上述有界规则码；没有发布。另对两份正文的 118 个非空段落和列出的专题对象做有界句式扫描，工况、位置、inspect 动作、choice 的精确匹配均为 0，见[扫描计数](evidence/wp-11-contract-alignment-r1/source-rule-scan.json)。扫描不等于通用语义裁判；更关键的是当前已存 scope 为 `unknown`，足以阻断 WP-10 的步骤引用。**本轮未找到无需编造适配字段、方位、工况或选项即可从现有 DKVB 正文发布的完整非数值检查。** 保留拒绝/待补，不改资料与门禁。

## 通用持久图的独立免费正例

用已有 `tests/fixtures/wp10/extra-synthetic.md` 的完整适配字段和直接支持原语法的合成内容，运行同一 `ProposalService.validate()` 得到 accepted candidate；在隔离 PostgreSQL 中创建诊断 run、领取 job、暂存候选并经原 `JobStore.finish()` **一次事务**发布。验证 case revision=1、当前步骤 `waiting_input`、该 run 恰好一条 publication。随后由**另一个 Python 进程**执行 `reconcile_pending()`，读回相同 step ID/revision/status；graph_progress 进入 `waiting_input`。这证明通用免费发布与崩溃后对账路径可运行，**不能替代 DKVB 的精确适配或说明本次真实模型已发布成功**。

## 命令、失败与证据版本

- `.venv/Scripts/python.exe -B -m ruff check --no-cache tests/integration/test_wp11_contract_alignment.py`：最终退出 0。
- `run-free.ps1`：新库创建、`alembic upgrade head`、checkpoint 初始化均退出 0；首次两项测试 **1 passed / 1 failed**，整体退出 1。DKVB 项通过；通用项失败于新测试错误地要求已发布 `validation_json` 保留临时 `accepted` 字段，原发布契约只保存空 issue 列表和来源。保留[首次 XML](evidence/wp-11-contract-alignment-r1/targeted.xml)和私有原日志，没有改业务实现或放宽校验。
- 修正该**测试断言**后仅运行通用项，退出 0、1 passed，见[首轮修正记录](evidence/wp-11-contract-alignment-r1/generic-run.json)及 `generic.xml`。随后增加跨进程 checkpoint 对账断言，仅再运行同一通用项，退出 0、1 passed，见[最终定点记录](evidence/wp-11-contract-alignment-r1/generic-run-efcee05b844b427f8efbb0af97552e8b.json)及对应 XML。最后仅做 import 格式整理，AST 行为不变；没有把首次失败抹成通过，也没有声称最终文件重跑两项完整集合。

测试脚本见 [test_wp11_contract_alignment.py](../../../tests/integration/test_wp11_contract_alignment.py)，原始运行命令见[免费运行脚本](evidence/wp-11-contract-alignment-r1/run-free.ps1)与[通用复跑脚本](evidence/wp-11-contract-alignment-r1/run-generic.ps1)。受限原始输出留在 `.test-runs/wp11-align-ca55ea69dee74ab0afc467403b9b2db3`；公开 JSON 只含 ID、字段状态、规则码与计数。本轮没有执行历史完整 449 项，也没有读取旧费用账本或操作 5180/5196。

## 下一步边界

没有发现“已有且已核实的字段被接入层传错”的证据，因此不作生产字段修复。若要让 DKVB 资料支持检查，需先决定如何核实并表达精确适配信息；若考虑扩展 WP-10 有界语法，应另列对应原文位置、有限可接受表达和误放行反例，由下一轮明确授权后实施。当前不把“句式不被识别”误报为“资料没有依据”，也不把 DS 模拟阈值当正式规格。真实资料 `NOT_MET`、旧 worker 首次失败根因未确证及历史其他限制继续保留；WP-11 未审核、未接受，WP-12 未启动。
