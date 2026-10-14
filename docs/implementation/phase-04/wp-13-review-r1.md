# WP-13 集中限定审核 r1

审核时间：2026-09-21（Asia/Shanghai）  
结论：**REVIEW_PASS（限定报告基础设施与合成技术范围）**。

本轮只读审核 WP-13 报告服务；未修改实现、`STATUS.md`、接受记录、既有证据或 Git index，未操作 5180/5196，未调用付费模型。本任务链此前参与过实施和相邻工作包的整改/复核，**不声称是不同任务的独立审核**。

## 基准与证据版本

- 未找到适用的 `AGENTS.md`（仅核对项目及其父目录）。
- 最终完整入口封存的 17 个受影响源码/迁移/测试文件逐项 SHA-256 与当前工作区一致，差异 **0**；基准为 `evidence/wp-13/final-full-7d4a328f77fd43cb9f89f39f80d85529/source-hashes.json`。
- 当前 `.git/index` 文件 SHA-256 为 `C451D6E78B8F29FC818002923A19FB1A888139CED20679AD545F75E9692A9EC6`，与 WP-12 接受及 WP-13 交付记录中的基准一致。仓库尚无 HEAD，且存在历史暂存/未跟踪交付；本轮未清理、暂存或提交它们。
- 执行者最终标准入口 `scripts/test.ps1` 的结果是 **514 passed、1 warning、1 failed，退出 1，41:23**。唯一失败为 `test_stale_before_publication_and_cross_owner` 的 Windows `httpx.ReadError [WinError 10053]`，发生在测试 HTTP 读取前，没有业务断言失败。相同源码、隔离库的该唯一实例随后定点通过：**1 passed，14.46s**。这两份结果分别保留，不能把完整入口写成全绿。
- 与 WP-13 直接相关的执行者定点证据为：报告 API/发布 **5 passed（68.29s）**、报告图 **5 passed（69.02s）**、观察更正相邻路径 **1 passed**；均为隔离 PostgreSQL、真实 HTTP/worker 和免费 MockTransport。没有在本轮重复运行约 41 分钟的完整入口，也没有新增测试，因为现有最终源码证据已覆盖本次发现的高风险边界。

## 审核结果

| 项目 | 结论 | 代码与证据 |
| --- | --- | --- |
| 最终报告六项门禁 | PASS | `report_policy.final_gate()` 对有效区域、最终卡、有效观察、活动诊断任务、适配/来源、规格及冲突逐次读取当前数据库；请求处和发布处均重新调用。`unknown`、`needs_input`、冲突、未回答/不可测观察、资料适配 unknown、撤销/失效来源、旧 revision/epoch 都不能成为有效最终报告。`test_unknown_progress_final_gate_and_idempotent_worker`、`test_final_source_revoked_after_request_cannot_publish` 证明未收敛和请求后撤销都不发布。 |
| 进度报告边界 | PASS | `report_graph.progress_draft()` 只从已保存观察、步骤、区域卡和 gate 缺项生成正文，固定输出 `repair_actions=[]`、`verification_actions=[]`，并声明不是最终维修报告。`validators.report.validate_draft()` 额外拒绝任何进度 `repair_actions`。unknown 病例的真实 HTTP/worker 定点报告保留缺项而非 supported、ruled_out、确诊、排除或换件建议。 |
| 主动请求、认证、幂等与无副作用拒绝 | PASS | `api/reports.py` 的 POST 使用现有 `writing` 依赖（会话、同源 Origin、CSRF）；`ReportService.request()` 在 owner/case 锁、`expected_revision` 和最终门禁成功后才 `enqueue` 和插入 `reports`。未满足门禁在同一事务内返回 `409 FINAL_NOT_READY` 和结构化 `blocking_items`，不会创建 run/job/report。`run_service.idempotent()` 对同键同内容返回原响应、异内容冲突；跨 owner 读取/创建返回 404。 |
| 冻结快照、图恢复与发布事务 | PASS | 请求冻结 `input_revision`、`graph_epoch`、`manifest_json`、当前 `conclusion_ids`。独立图在每个阶段重新取受限快照；发现变化转为 `_stale`。`report_publish.publish_report()` 在同一事务内持 owner/case 锁、job/run/report 行锁与既有 lease/fencing，再检查 run 关系、revision/epoch/manifest、卡、来源、规格和最终门禁，之后才写报告状态、事件、run/job 终态与 output revision。失租约、取消、旧 worker 或慢 SQL 不能迟到提交。 |
| 历史、stale 与失败隔离 | PASS | 发布前 revision/资料/卡变化生成 `draft/stale`，不覆盖既有 current；新的同 kind current 才会使旧报告 `superseded`。GET 按 owner 返回历史正文及实时 `current_validity`，不会把旧正文伪装成新结果。更正后旧 progress 报告仍可读、状态为 stale；请求后撤销的 final 报告为 stale 且正文为空。 |
| ReportDraft 硬校验 | PASS | `InputModel(extra=forbid)`、固定数量/大小限制和 100 KiB 正文上限生效。最终 claim/action 必须是当前可信卡的原句/结构化动作及其引用、观察、规格的子集；`supported` 才能授权 repair action，`ruled_out` 不能授权换件。重复动作、未知依赖、环、伪造规格/扭矩/针脚、无出处结论均由 `validate_draft()` 拒绝。定点反例覆盖重复、环、编造扭矩/条件、伪造 finding 及 ruled-out 动作。缺维修程序会保留在 `limitations`/`unresolved_items`，不会补造数值。 |
| 迁移与历史迁移保护 | PASS | `0012_reports` 仅接续 `0011_area_closure`：新建带状态/类型/JSON shape/唯一 run 的 `reports` 表，扩充 assessment 检查约束；`downgrade()` 删除新表后恢复原约束。迁移清单定点已覆盖，未修改 `0001`—`0011`。 |

## 审核发现

没有发现必须整改项。以下不是本包通过范围，也不是缺陷修复要求：

- 最终报告模型路径只由免费 MockTransport 验证；没有实际付费报告调用，不能据此证明真实模型的结构化语义质量。
- 当前生产诊断流只形成保守 `unknown` 卡，尚无已审核的真实 `supported`/`ruled_out` 结论写入流程；最终报告完整路径仅以明确标识的合成可信卡夹具验证。
- 已接受的诊断切片只证明合成资料下真实模型首项检查、保存观察和保守 unknown 收尾；观察后的第二项当前检查未发布。真实 DKVB 资料仍 `NOT_MET`，不能把本报告基础设施写成真实维修效果、自动确诊或正式报告闭环。
- 生产恢复、Linux BGE、历史 SSE/Compose/旧 worker 首次失败根因等既有未确认项继续保留；WP-14 前端与后续工作包不在本审核范围。

## 建议接受范围

建议用户仅在下列限定范围内接受：用户主动请求的进度/最终报告服务、服务端六项 `ReportPolicy` 门禁、请求时冻结与发布前重验、受租约/fencing 保护的报告任务及事务发布、报告草稿引用/规格/动作硬校验、历史读取与 stale 表达，以及合成夹具下的最终报告技术路径。

该建议不接受真实资料资格、真实 DeepSeek 报告语义、真实维修效果、正式诊断网页或整个 P4；`unknown` 进度报告不构成 supported、ruled_out、确诊、排除或换件建议。
