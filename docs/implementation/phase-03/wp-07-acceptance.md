# WP-07 用户限定接受记录

状态：**ACCEPTED（限定五业务工具与执行器技术范围）**。
记录时间：2026-09-18T21:17:56.638003+08:00（Asia/Shanghai，UTC+08:00）。用户在本任务明确授权接受；本次仅记录，不实施WP-08，不接受整个P3阶段。

## 接受依据与基准核对

- [WP-07 r2定点复核](wp-07-review-r2.md)：限定范围REVIEW_PASS，ISSUE-001、ISSUE-002均RESOLVED，依据本次用户指令记录关闭。
- 保留[r1集中审核](wp-07-review-r1.md)、[r1整改记录](wp-07-remediation-r1.md)及其原始失败/通过证据；不修改原结论。
- [现行契约](wp-07-contract.md)与当前交付匹配r2基准。接受前逐项核对r2 baseline的2932项原文件及protection-final的147项封存工件，均一致；r2报告与封存文件哈希匹配。当前Git状态只多出r2结束封存时的4项已知审核工件，无非预期实现或其他交付差异。
- Git根E:/Work/xiutu-v5，main，无HEAD（verify退出128，未提交仓库）；索引SHA256保持 `c451d6e78b8f29fc818002923a19fb1a888139ced20679ad545f75e9692a9ec6`。旧项目63项保护文件亦匹配。
- r2报告SHA256：`13dc389defe874724d64117088c0539dbcfeba64f0e6c5f3375145283a480b1a`。
- r2 protection-final.json SHA256：`7376fbc9c7964cc07b99b732cf29980600e521161ad16796ee350a03761b8633`；final-check.json SHA256：`349a7b34fb33d7670c70cb185a4edac31df4f4bbe74051d5ce48ad61f11c6a01`。
- 本次允许的接受后差异仅本记录和STATUS。STATUS写入前SHA256：`e116e93194d90271d1d9e33923d28e0cbb9cdb4f96f25b7e60c921db22bd4084`；拟写入内容SHA256：`66abf8f42b35b82afc17003baa391f62c829b03a4ba4c2440cb123c6304c3174`。未重跑测试、修改实现/迁移/历史证据，未提交推送或调整Git index。

## 限定接受范围

五业务工具（search_manuals、get_evidence_context、get_measurement_spec、compare_measurement、get_case_observations）、可信上下文和权限收窄、持久预算与调用审计、本地LangChain适配、比较幂等及超时/取消事务保护、观察只读查询、receipt v2安全重放和旧比较有效性检查。

ISSUE-001、ISSUE-002依据r2关闭。用户明确知悉并接受同任务实施、整改与复核的流程限制，不声称不同任务独立审核；技术复核结论与本次用户接受是两个不同事件。

## 测试证据版本

| 来源 | 已有结果 | 边界 |
| --- | --- | --- |
| r1整改前审核 | 完整260通过（1条已知警告）；补充6通过、5失败 | 原版本证据，失败记录保留 |
| 整改执行者自测 | 首轮33通过、1个测试记录错误；随后5通过 | UUID序列化测试记录修正，不抹去首轮失败 |
| r2当前版本定点复核 | 37项定点＋2项补充通过 | 非整改后完整入口重跑；不与旧轮次累加为功能覆盖数 |

本次仅核对文件/封存证据并记录接受，无新增测试或审核。

## 保留限制与未完成项

- 同任务实施/整改/复核，不声称不同任务独立审核。
- 旧无版本receipt返回RECEIPT_UNSUPPORTED；保留审计及历史读取，不自动重做副作用或扣预算。
- 旧比较需复核时返回COMPARISON_INVALID；规格重新批准不清除旧结果复核标记。
- 尚无业务MCP、正式Agent、观察写入或远程模型strict兼容验收。
- 不代表生产恢复、真实维修效果或整个P3完成。
- owner粗锁、性能、监控、清理、uncertain处置及观察接入待办保留。
- E10 NOT_VERIFIED，另行取得模型、调用范围与预算授权后验证，最迟WP-09；本次未授权付费调用。
- 真实资料门槛NOT_MET：来源/许可、精确车型及发动机适配、正式规格/电路/拆装/复核章节及缺图等仍待补齐，最迟WP-10/真实效果验收前。
- SSE首次超时根因未确认。

## 用户本次授权原文

以下保留本次指令文本（换行统一为LF）：

```text
我接受 WP-07 限定技术范围交付，并知悉同任务实施、整改与复核的流程限制。

工作目录：E:\Work\xiutu-v5。
本次仅记录接受，不实施 WP-08，不接受整个P3阶段。

读取适用 AGENTS.md、STATUS，以及：
docs\implementation\phase-03\wp-07-contract.md
docs\implementation\phase-03\wp-07-review-r1.md
docs\implementation\phase-03\wp-07-remediation-r1.md
docs\implementation\phase-03\wp-07-review-r2.md

先核对当前交付仍匹配r2基准，报告和封存证据未变。
若出现非预期实现差异，报告差异并停止记录，不自动重测。

基准匹配后：

1. 新增 docs\implementation\phase-03\wp-07-acceptance.md，
   记录本次用户授权原文、时间、依据、接受范围和保留项。
2. 更新 docs\implementation\STATUS.md：
   WP-07=ACCEPTED（限定五业务工具与执行器技术范围）；
   WP-08—17保持NOT\_STARTED。
   同步当前停止点，纠正原“只有执行者自测”的过时描述。

接受范围：
五业务工具、可信上下文和权限收窄、
持久预算与调用审计、本地LangChain适配、
比较幂等及超时/取消事务保护、观察只读查询、
receipt v2安全重放和旧比较有效性检查。
ISSUE-001、ISSUE-002依据r2关闭。

准确区分证据：

- r1整改前完整260通过，补充6通过、5失败。
- 整改自测首轮33通过、1个测试记录错误，随后5通过。
- r2当前版本37项定点＋2项补充通过。
  不写成整改后完整入口重新通过，也不累加重复测试为覆盖数。

保留：

- 同任务实施/整改/复核，不声称不同任务独立审核。
- 旧无版本receipt返回RECEIPT\_UNSUPPORTED；
  保留审计及历史读取，不自动重做副作用或扣预算。
- 旧比较需复核时返回COMPARISON\_INVALID；
  规格重新批准不清除旧结果复核标记。
- 尚无业务MCP、正式Agent、观察写入或远程模型strict兼容验收。
- 不代表生产恢复、真实维修效果或整个P3完成。
- owner粗锁、性能、监控、清理、uncertain处置及观察接入待办。
- E10 NOT\_VERIFIED，另行授权后验证，最迟WP-09。
- 真实资料门槛NOT\_MET，最迟WP-10/真实效果验收前补齐。
- SSE首次超时根因未确认。

仅新增接受记录并更新STATUS。
不修改实现、历史报告/证据、旧项目、已有迁移或Git index。
无需重跑测试，不提交推送、不付费调用。
完成后停止，不启动WP-08。
```

## 停止点

WP-07=ACCEPTED（上述限定范围）；WP-08—17仍为NOT_STARTED。仅新增本记录并同步STATUS的当前状态、停止点与分版本证据描述；其他交付、历史报告/证据、接受记录、旧项目、已有迁移及Git index保留不变。完成记录后停止，不启动WP-08。
