# WP-08 用户接受记录

记录时间：2026-09-18T23:33:05.447210+08:00（Asia/Shanghai）。
状态：**ACCEPTED（限定三项只读业务MCP技术范围）**。接受来自本次用户明确授权；不是自动接受整个P3，不启动WP-09。

## 依据与接受前基准核对

已读取适用路径（项目及上级未发现AGENTS.md）、STATUS、[契约](wp-08-contract.md)、[r1审核](wp-08-review-r1.md)、[r1整改](wp-08-remediation-r1.md)、[r2复核](wp-08-review-r2.md)。

- r2 baseline：3400项全部匹配；r2 seal：92项报告与证据全部匹配，无非预期实现差异。
- r2报告SHA256：`c2fef24552d5e9e94286adab2ee45106db561ed534c93768d835ec7755052b9f`。
- r2 seal SHA256：`cba18ec2e67318f95dbe32898eba2355cf7c35a960225e2f981ed079957351dc`；原封存文件保持原样。
- Git根E:/Work/xiutu-v5，main，无HEAD；Git index SHA256：`c451d6e78b8f29fc818002923a19fb1a888139ced20679ad545f75e9692a9ec6`，与r2一致。检查Git列出的交付文件，无基准外新增文件。
- 旧项目63项保护哈希一致。原实现、0001—0007迁移、历史报告/证据及原接受记录均保持不变。
- 接受前STATUS SHA256：`4750022d28c3af4d98356a827d5fbd1a24a84bc65165c361b7be3bab216ecdb9`。本次授权差异仅新增本记录与更新STATUS；STATUS变更后不再声称它与r2旧哈希相同，原r2基准不重写。

## 限定接受范围与问题关闭

真实SDK Streamable HTTP三工具（search_manuals、get_evidence_context、get_measurement_spec）、应用适配器与独立CLI双客户端、服务端授权及最终grant复验、应用预算/审计与无静默fallback、专用只读数据库角色和Compose只读部署。ISSUE-001依据r2关闭，Compose动态权限检查已补齐。

## 分版本证据

- 原交付的完整301通过属于当时基准，原报告和首次收集失败等日志保留。
- r1整改前完整301通过，1条既有警告；其授权缺陷及Compose失败记录不覆盖。
- 整改首轮10通过、1个夹具失败；修正共享allowlist后该项1通过，属于执行者自测。
- r2当前版本11项定点通过；Compose一次有界启动通过，67项容器源码匹配，权限与挂载实际拒绝写入。

不声称整改后完整301项重新通过，不累加重复测试为功能覆盖数。本次只做文件/哈希和状态核对，未重跑测试。

## 保留限制与停止点

- 用户知悉同任务实施、整改与复核，不属于不同任务独立审核，并接受该流程限制。
- 最终授权判定后网络发送期间不保证即时撤回。
- Compose历史启动异常底层原因未确证，成功不代表查明或修复Docker平台问题；SSE首次超时根因未确认。
- 旧receipt安全拒绝，旧比较需复核；owner粗锁、性能、监控、清理、uncertain处置及既有非阻断待办保留。
- 不代表正式Agent/UI、远程模型strict兼容、生产恢复、真实维修效果或整个P3验收。
- **E10 NOT_VERIFIED**：另行取得模型、调用范围与预算授权，最迟WP-09验证；本次不授权付费请求。
- **真实资料门槛NOT_MET**：最迟WP-10/真实效果验收前补齐。

仅新增接受记录并更新STATUS；不修改实现、历史报告/证据、旧项目、迁移或Git index，不提交推送、不付费调用。WP-09—17保持NOT_STARTED，完成记录后停止。

## 用户本次授权原文

```text
我接受 WP-08 限定技术范围交付，知悉同任务实施、整改与复核的流程限制。

工作目录：E:\Work\xiutu-v5。
本次仅记录接受，不实施WP-09，不接受整个P3阶段。

读取适用AGENTS.md、STATUS、WP-08契约，以及：
docs\implementation\phase-03\wp-08-review-r1.md
docs\implementation\phase-03\wp-08-remediation-r1.md
docs\implementation\phase-03\wp-08-review-r2.md

先核对当前交付仍匹配r2基准，报告及封存证据未变。
若有非预期实现差异，报告并停止记录，不自动重测。

基准匹配后：

1. 新增 docs\implementation\phase-03\wp-08-acceptance.md，
   记录本次用户授权原文、时间、依据、范围和保留项。
2. 更新 docs\implementation\STATUS.md：
   WP-08=ACCEPTED（限定三项只读业务MCP技术范围）；
   WP-09—17保持NOT\_STARTED。
   同步停止点，准确区分原交付、审核、整改与复核。

接受范围：
真实SDK Streamable HTTP三工具服务、
应用适配器与独立CLI双客户端、
服务端授权及最终grant复验、
应用预算/审计与无静默fallback、
专用只读数据库角色和Compose只读部署。
ISSUE-001依据r2关闭，Compose动态权限检查已补齐。

证据分别记录：

- r1整改前完整301通过，1条既有警告。
- 整改首轮10通过、1个夹具失败；修正后该项通过。
- r2当前版本11项定点通过，Compose一次有界启动验证通过，
  67项容器源码匹配，权限与挂载实际拒绝写入。
  不声称整改后完整301项重新通过，不累加重复测试为覆盖数。

保留：

- 同任务实施/整改/复核，不声称不同任务独立审核。
- 最终授权判定后网络发送期间不保证即时撤回。
- Compose历史启动异常底层原因未确证；
  本轮成功不代表已查明或修复Docker平台问题。
- SSE首次超时根因未确认。
- 旧receipt安全拒绝、旧比较需复核规则及既有非阻断待办。
- 不代表正式Agent/UI、远程模型strict兼容、
  生产恢复、真实维修效果或整个P3验收。
- E10 NOT\_VERIFIED，另行取得模型/调用范围/预算授权，
  最迟WP-09验证；本次不授权付费请求。
- 真实资料门槛NOT\_MET，最迟WP-10/真实效果验收前补齐。

仅新增接受记录并更新STATUS。
不修改实现、历史报告/证据、旧项目、迁移或Git index。
不重跑测试、不提交推送、不付费调用。
完成后停止，不启动WP-09。
```
