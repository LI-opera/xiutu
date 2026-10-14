# WORKBENCH-ADAPT-C06：受控操作提案契约与 C05 离线重放

状态：`IMPLEMENTED_NOT_ACCEPTED`，2026-09-24。**本轮真实模型调用数为 0**；当前 5215 分析配置仍为 `stub`，真实调用授权保持关闭。本轮没有修改病例答案、C05 失败状态或有效建议，也没有发布离线副本。

## 契约修改

新快照明确冻结 `case-advice-proposal-c06-v1` / `dkvb-c06-v1`。提案步骤按 `type` 区分：

- `controlled` 只能提交 `type`、冻结清单中的 `action_id`、`basis_observation_ids`。`kind`、正文、前提、来源、复检与停止条件都由服务端从**该次快照**的 `action_catalog` 组装；多余字段明确结构报错，不被忽略。服务端核对允许范围、当前有效观察及必要选项、本次冻结的本地手册摘录与受控摘录正文，然后对组装后的完整建议再次校验。
- `free` 必须提交 `type`、`kind=check|handoff`、完整说明/条件/复检/停止文字和事实/摘录引用。所有引用与清单外操作仍经最终校验；不能借此分支提出任意技术步骤。

发送给模型的 JSON schema 与提示词同步按新分支生成。旧 C04 快照继续走原解析和组装分支，旧 `CaseAdviceDraft` 发布结果按原结构读取，不回写旧结果。C05 一次调用保护继续计入既有 `dkvb-c04-v1` 真实尝试；版本提升不会把那次额度重置。未来真实体验需重新明确授权和限定窗口，本轮没有启用该窗口。

## C05 原响应核对

通过隔离 `APP_MODE=test`、本地登录及病例归属校验读取受限诊断响应；冻结快照只读查询也同时约束病例及操作员归属。分析 `68b6ee08-4ff3-47cc-8331-5deaca8add5c` 仍为 `failed`，revision 42，旧契约 `case-advice-proposal-c04-v1`，范围 `supplement_or_handoff`。原响应 1,928 字符 / 3,474 UTF-8 字节，未截断，原文 SHA-256 为 `f3094c5b164a5d478392e27c5c93ff08fb9a7efc2dfbaa4b76176557657b60a0`，本次重新计算吻合。原响应仍仅保存在受限 `case_analyses.diagnostic_json`，保留期依原 C04 规则；本文不复制原文。

实际旧解析器能解析四步、空 `supported_directions`，符合补充/交接范围的结构。旧组装器重放的第一个拒绝点仍是 `steps[0].source_ids` / `action.source`：模型给出来源登记 ID `SRC-CHARGE-AIR` 和 `EDITORIAL_DEMO`，而受控操作要求本次冻结的手册摘录 `C01-SRC-CHARGE-AIR-P1`。独立核对显示：唯一受控 `action_id=CHECK_CHARGE_AIR_HOSE_SEATING_LEAK` 存在、属于本范围；第一步的三个事实 ID 均为有效观察且含满足该操作条件的选项；模型没有自写这一步的受控正文。其余三步的事实 ID 也都属于本次有效观察。**这些局部通过不代表整份建议通过发布校验。**

首个错误以外，还发现：

1. 三个自由交接步骤均缺 `action`、`prerequisites`、`retest`、`stop_condition`。旧结构将其设为可选，但旧组装器随后要求存在；新 `free` 分支在解析时即要求完整。缺失正文不能靠机械转换补造。
2. 四步的来源引用含 `SRC-CHARGE-AIR`、`EDITORIAL_DEMO`、`SAFETY_BOUNDARY`、`SRC-TURBO`、`SRC-WIRING-DKVB-70` 等登记/边界 ID，不是本次仅有的两段摘录 `C01-SRC-CHARGE-AIR-P1/P5`。第一步来源由服务端受控组装可解决；自由步骤的错误引用仍须由模型重新给出有效摘录或明确无摘录，不能静默换成别的来源。
3. 以实际最终校验器逐字段做**隔离诊断探针**，概述和不确定性触发 `text.unsupported_certainty`，未确认方向、复检计划和安全说明触发 `text.unsupported_operation`。其中有“非实车确诊”“缺少检漏响应证据”、已记录压力数值及禁止性安全表述，部分命中可能属于现有词法校验误报；复检计划也包含具体再测安排。因为原提案没有通过自由步骤结构校验，完整最终发布校验未执行，不能宣称上述文本已被确认为实质越界或已全部合格。正式校验未放宽。

## 透明转换副本与结果

仅在内存构造离线副本，未写回诊断记录或病例。`steps[0].kind="check"` 改由冻结 action 清单决定而移除，加入分支标识 `type="controlled"`；`steps[0].source_ids=["SRC-CHARGE-AIR","EDITORIAL_DEMO"]` 从新提案移除，原错误来源仍在上述诊断事实中，不当作正确引用。该步原本没有模型自写受控正文。`steps[1..3]` 仅加入 `type="free"`；概述、方向、事实、来源、说明、复检及安全文字都未改写，未补入原响应没有的动作或结论。

以**原冻结快照**和 C06 解析/组装路径重放时，转换副本在 `steps[1..3].{action,prerequisites,retest,stop_condition}` 的 12 处必填字段处报结构错误，未进入完整最终发布校验。结果标识：**“C05 原响应的离线契约转换预览，非新模型生成，未发布为有效建议”**；因未通过，不提供貌似有效的建议正文。此次离线失败不是新模型质量验证。后续除新契约真实验证外，仍需决定自由步骤正文/引用与词法误报的实质修正，不能仅靠字段归属变更宣布可发布。

定点验证：`tests/unit/test_case_analysis_c06.py` 与 C04 定点共 18 passed。覆盖受控提案无需模型写来源/正文、冻结清单组装、未知 ID/无效事实/摘录缺失或正文变更拒绝、自由步骤错误引用和清单外操作拒绝、受控分支多余字段明确拒绝、旧 C04 分支兼容。以当前代码只读预检原病例仍为 revision 42、41 条观察、`supplement_or_handoff`，新快照 33,702 字符、两段摘录和唯一受控 action；没有请求模型。受限 API 再读确认 C05 仍 `failed` 且无内容，旧替身成功结果仍可读；未重启已运行的服务，现有页面行为未改。无需数据库迁移。
