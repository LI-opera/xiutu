# DKVB/P0299 可信诊断协议与引导闭环 r1 结果

- 日期：2026-09-22（Asia/Shanghai）
- 状态：`IMPLEMENTED_NOT_ACCEPTED`
- 范围：WP-15 后的 synthetic 产品纠偏切片；WP-16、WP-17 未启动
- 契约：[dkvb-trusted-protocol-contract-r1.md](dkvb-trusted-protocol-contract-r1.md)
- 证据：[verification-summary.md](evidence/dkvb-trusted-protocol-r1/verification-summary.md)

## 原问题与修正

原体验只有 CHK-05 的有限文字。三个观察结果均没有经应用登记的可信“观察→下一检查”关系，因此续轮只能让模型自由生成候选；候选随后被原 ProposalService 以 `AREA_NEEDS_INPUT` 安全拒绝。增加提示词、重试模型或放宽校验都不能补上这条事实关系。

本轮增加版本化 `dkvb-p0299-guided-demo@1.0.0` 协议及病例/epoch 冻结绑定。调用顺序为：有效数据库观察 → 冻结协议/版本 → 当前检查及观察 schema → 唯一 transition → 有界下一候选或 need_input → ProposalService 原门禁 → 既有 fenced 事务发布。协议字段由服务端产生；模型和浏览器不能提交 `transition_id`。

## 实现

- `0013_trusted_diagnosis_protocols.py` 与 ORM 表保存 owner/case/epoch、协议版本、manifest hash、车辆 profile 及经验证候选。
- `trusted_protocol.py` 定义小型 schema 和应用显式注册表；没有自动批准 `knowledge.json` 或 REL-01—07。
- `ProtocolService` 在注册时和每次路由时复查 profile、manifest、来源有效性及 ProposalService 门禁，并只接受当前有效观察。
- 观察事务只接受当前步骤公布的 `protocol_fields`；未知、缺失、错误枚举在任何观察写入前返回 422。
- 更正观察会复制冻结绑定到新 graph epoch，并从 replacement observation 重新路由；旧后续步骤保持 stale。
- runner 在协议唯一命中时使用确定性受限候选，不再要求模型发明下一检查。发布仍经过既有 lease/fencing/事务路径。
- 正式工作台为绑定协议的 DKVB DEMO 显示引导卡、一个主操作、具体 need_input 和来源；内部 ID、revision、epoch、错误码及原始 JSON 默认折叠。

## 已登记关系

- `PROTOCOL_START_CHK05`：初始发布 CHK-05。
- `CHK05_LOCALIZED_TO_CHK06`：完整对象、位置和合法定位依据后进入 CHK-06。
- `CHK05_NOT_FOUND_TO_CHK08`：仅表达“本项未发现局部漏点”，进入 CHK-08。
- `CHK05_INCONCLUSIVE_NEEDS_INPUT`：进入 CHK-05-SUPPLEMENT，明确补充对象、位置和依据。
- `CHK05_SUPPLEMENT_LOCALIZED_TO_CHK06` / `CHK05_SUPPLEMENT_STILL_NEEDS_INPUT`：补充后继续或保持待补。
- `CHK06_COMPLETED_TO_CHK07` / `CHK06_DAMAGED_TO_CHK07`：CHK-06 完成后进入 CHK-07，证明不是静态替换第二张卡。

尚未登记 CHK-07、CHK-08 之后的关系，CHK-01—04、CHK-09—11，以及任何确诊、排除、换件、handoff 或最终完成关系。生产默认不会从上传手册或 `knowledge.json` 自动生成可信协议。

## 验证结果

最终免费验证：隔离 PostgreSQL 集成 1 passed（聚合覆盖三分支及直接反例）；受影响前端 20 passed；typecheck、OpenAPI 漂移检查、Ruff、独立 production build 均通过。实际隔离实例使用本机 BGE-M3 建立 1024 维 ready 索引。

浏览器从用户视角验证：

- A：localized 完整定位 → CHK-06；再保存一项 CHK-06 观察 → CHK-07。
- B：not_found → CHK-08，页面没有把它显示为正常、排除或已修复。
- C：inconclusive → 可继续填写的 CHK-05-SUPPLEMENT；刷新后观察和当前步骤保持。
- 来源抽屉能够打开冻结 synthetic 文本版本；页面不要求用户理解 UUID、revision 或内部 code。

没有运行真实 DeepSeek。三条免费分支已通过，但唯一下一检查完全由可信协议确定，模型只剩可选的说明组织作用；本轮没有为润色产生付费调用。模型/工具调用数为 0，持续计量账本未读取或改变。

## 体验实例

- 直接网址：`http://127.0.0.1:5225/workbench/e8851e26-da1f-4872-a16b-093a66fb0e0c`
- 令牌文件：`E:\Work\xiutu-v5\.local-data\dkvb-trusted-protocol-r1-final\access.txt`
- 停止命令：`E:\Work\xiutu-v5\.venv\Scripts\python.exe -B E:\Work\xiutu-v5\scripts\dkvb_trusted_protocol.py stop`

用户体验病例未被浏览器验证改动，仍停在 CHK-05。5225/8225 及必要 worker 保持运行；5180、5196、5215 均未操作。

## 限制

全部资料和车辆都是 `synthetic=true`、`DEMO`、`formal_usable=false`，不是厂家诊断树、真实 DKVB 车型适配或维修效果验证。真实资料继续 `NOT_MET`。本切片没有确诊、排除、维修完成、真实最终报告、生产规则管理、OCR、部署或生产恢复能力。既有 WP-00—15 接受范围未改变，本切片尚未审核或接受。

