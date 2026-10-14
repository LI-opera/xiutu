# WP-04 用户接受记录

状态：**ACCEPTED（限定资料导入与人工审核范围）**。
记录时间：2026-09-18T14:46:14.788356+08:00（Asia/Shanghai）。依据当前任务用户本次明确接受指令记录；本次没有运行测试或实施WP-05。

## 接受依据与范围

依据[wp-04-review-r2.md](wp-04-review-r2.md)及其引用的[r1审核](wp-04-review-r1.md)、[r1整改](wp-04-remediation-r1.md)和原始证据。ISSUE-001依据r2为RESOLVED，结合r1未变部分达到限定范围REVIEW_PASS；本次用户明确接受。

接受本地Markdown/PDF上传、版本保留、原文定位、解析切块、人工审核历史，以及取消/租约/事务回滚下的发布保护。不是后续工作包、正式索引检索或维修效果的接受。

## 证据版本与保留限制

- **r1整改前完整测试169通过；r2定点15通过。整改后没有重新运行完整入口**。r1发现的租约窗口失败和整改过程的临时目录准备错误均保留。初始执行曾168通过/1次SSE超时，后续定点及r1全量未复现，首次根因未确认。
- 用户知悉同任务参与实现、整改及复核，不声称不同任务独立审核；该流程限制不被本次接受记录隐藏。
- 扫描/缺文本页仍needs_ocr；approved仅index_pending，index_implemented=false、formal_usable=false。合成测试资料不成为正式维修证据。
- 本次不代表OCR、embedding、索引、检索、正式诊断、真实维修效果或生产恢复验收通过，也不代表整阶段无条件完成。
- E10仍NOT_VERIFIED，模型/调用范围/预算另行授权后验证，最迟WP-09收口。
- 真实资料门槛仍NOT_MET，来源/许可、精确车型及发动机适配、正式规格、电路、拆装/复核章节和缺图，最迟WP-10/真实效果验收前补齐。
- 既有非阻断待办继续保留：性能、监控（含不泄露内容的SSE时序观测）、清理/孤儿巡检、上传时长及并发配额、复杂PDF资源隔离等。没有把待办标为已解决。

## 接受前基准核对与本次文档变更

工作根E:\Work\xiutu-v5；main，无HEAD（rev-parse退出128）。适用AGENTS检查未发现文件。

接受前核对r2 baseline.json的1281项全部匹配；r2 review-evidence-hashes.json封存的83项全部匹配，r2报告哈希匹配final-protection.json；受版本控制/未忽略的文件清单无额外交付路径。旧项目63项保护文件全部匹配，未读取旧.env。没有非预期实现差异，因此依据用户指令记录接受，未重新开测试。

- r2报告SHA256：2fcc1074bb6c1a8543f9e55a57405db4d62fa86827a43ac8b3b5e6e43111a0b3。
- Git index SHA256：c451d6e78b8f29fc818002923a19fb1a888139ced20679ad545f75e9692a9ec6；本次不调整暂存区。
- STATUS变更前SHA256：d7b7d44acc4f9b09e743c5e7aa500bb526c79735647830a577f542d464ce5720。
- STATUS变更后SHA256：bbaa4f0410b4da35a3ba99da11e436860b63410d76aa92a2589551fbf296c475。

本次授权差异仅新增本接受记录、更新STATUS。r2基准中的STATUS旧哈希此后与当前不同是本次接受的预期文档差异；其余基准文件、审核/整改报告及证据不变。原审核结论不重写，已有接受记录不覆盖。WP-05—17保持NOT_STARTED。

## 用户本次授权原文

```text
我接受 WP-04 限定范围交付，并知悉同任务实施、整改与复核的流程限制。

工作目录：E:\Work\xiutu-v5。
本次仅记录接受，不实施 WP-05。

先读取适用 AGENTS.md、STATUS，以及：
docs\implementation\phase-02\wp-04-review-r1.md
docs\implementation\phase-02\wp-04-remediation-r1.md
docs\implementation\phase-02\wp-04-review-r2.md
并核对当前交付仍匹配 r2 审核基准。
若出现非预期实现差异，停止记录接受并报告差异，不自动重开测试。

基准匹配后：

1. 新增 docs\implementation\phase-02\wp-04-acceptance.md，
   记录本次用户授权原文、时间、依据和限定接受范围。
2. 更新 docs\implementation\STATUS.md：
   WP-04 为 ACCEPTED（限定资料导入与人工审核范围）；
   WP-05—17 保持 NOT\_STARTED。
   同步当前停止点，保留原测试历史，避免混淆证据版本。

接受范围：
本地 Markdown/PDF 上传、版本保留、原文定位、解析切块、
人工审核历史，以及取消/租约/事务回滚下的发布保护。
ISSUE-001 依据 r2 关闭。
准确记录：r1 整改前完整测试169通过，r2定点15通过；
不得写成整改后完整入口重新通过。

保留：

- 同任务参与实现、整改及复核的流程限制。
- SSE 首次超时根因未确认。
- 扫描页 needs\_ocr；approved 仅 index\_pending，
  index\_implemented=false、formal\_usable=false。
- 不代表 OCR、embedding、索引、检索、正式诊断、
  真实维修效果或生产恢复验收通过。
- E10 NOT\_VERIFIED，授权后验证，最迟 WP-09。
- 真实资料门槛 NOT\_MET，最迟 WP-10/真实效果验收前补齐。
- 既有非阻断待办。

仅新增接受记录并更新 STATUS，不修改实现、历史报告、
原证据、旧项目、迁移或 Git index。
无需重跑测试，不提交、推送或调用付费模型。
完成后停止，不启动 WP-05。
```

## 停止点

本次仅记录接受。未修改实现、迁移、旧项目、历史报告或证据、Git index；未提交推送、未付费调用。WP-05未启动，后续实施须另行授权。
