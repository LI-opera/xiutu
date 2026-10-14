# WP-13 报告服务实施契约

依据：总指南 WP-13、§5.2 ReportPolicy 六项条件、§11 报告图；WP-12 和诊断切片的限定接受范围。此包不自动生成报告、不修改诊断图或 WP-14 页面。

## 数据及入口

接续 `0011_area_closure` 增加 `0012_reports`：`reports` 保存 owner/case/run、kind、请求时 revision/graph_epoch、冻结 manifest 与结论 ID、报告正文、状态、失效原因；`diagnosis_area_conclusions` 的 assessment 约束扩充 `supported/ruled_out`，但不提供本包公共结论写入入口。现有 `unknown` 卡不转换。已有 `runs/jobs/run_events/idempotency_keys` 承载异步任务、租约、事件和同键响应。

`GET /api/v2/cases/{id}/reports/gate` 返回最终报告 `allowed` 和六项结构化 `blocking_items`；`POST /api/v2/cases/{id}/reports` 请求 `kind=progress|final`、`expected_revision`，要求登录、同源、CSRF、Idempotency-Key。最终未满足返回 409 `FINAL_NOT_READY`；不创建任务。`GET /api/v2/cases/{id}/reports` 和 `GET /api/v2/cases/{id}/reports/{report_id}` 只对 owner 返回历史与当前有效性；旧报告不可伪装为新任务结果。

进度报告可在 `unknown` 病例请求，冻结当时事实并列已保存步骤/观察、待复核区域及资料/适配缺项、尚不能判断之处；`repair_actions=[]`，不声称最终结论。最终报告请求时及发布前须同时满足：非 retired 区域存在；所有有效区域 supported/ruled_out；每区 current 卡的观察和来源有效；无诊断活动任务；无未解决冲突或车型专属资料适配缺口；无撤销来源。模型不得自行提高权限或改变六项门禁。最终报告只能使用已审核的结构化卡与当前有效引用/规格，不由自然语言单独授权换件。

独立 LangGraph 为 `load_frozen_snapshot → collect_conclusions → detect_conflicts → synthesize_plan → validate_claims`；随后原 JobStore 的 `finish → publish_report` 持租约在单事务发布。节点增量只含冻结引用和候选报告，不覆盖数据库事实；已持久草稿可在同一逻辑 run 恢复。`ReportDraft` 字段固定 `scope/confirmed_facts/diagnostic_findings/unresolved_items/repair_actions/verification_actions/limitations`；动作含 `target/reason/prerequisites/instructions/evidence_ids/observation_ids/depends_on_action_ids/completion_criteria`。每个来源用既有 evidence/Spec 有效性服务核对；动作按对象/语义去重、依赖不存在或成环拒绝，动作字段须与当前可信卡一致，`ruled_out` 卡不授权维修动作。缺维修程序或规格则列缺项，不编造扭矩、针脚。

发布持 case/owner 锁、原 worker advisory lock 及 lease/fencing，复查 revision、epoch、manifest、卡及来源；一事务写正文/状态、run/job 终态和事件。revision 或资料变化留下 draft/stale，旧有效报告不被新失败覆盖。观察更正后读取时以当前 revision/epoch/来源重算有效性，历史仍可读。报告 worker 使用现有任务队列；模型路径仅可在受控网关上调用，本包自测只用免费 MockTransport/确定性合成候选，不发送付费请求。

验证顺序：迁移和六项门禁定点；进度 unknown、最终有效合成卡、幂等/owner/CSRF、引用和规格、去重/环、撤销/过期/更正及事务失败反例；随后对最终实现运行一次 `scripts/test.ps1` 标准完整入口。所有测试使用独立 `xiutu_test_*` PostgreSQL；历史证据和用户 5180/5196 不动。
