# WP-12 用户限定接受记录

记录时间：2026-09-20T22:02:38+08:00（Asia/Shanghai）。状态：**ACCEPTED（仅合成且精确适配资料下的观察提交、保守区域收尾、事实更正与持久图恢复技术范围）**。这不是整个 P4、正式诊断网页、生产恢复或真实维修效果的接受。

## 用户授权与写入前核对

用户本次明确表示：“我决定按 wp-12-recovery-review-r2.md 的范围，接受 WP-12‘合成且精确适配资料下的观察提交、保守区域收尾、事实更正和持久图恢复’限定技术交付。”并授权在记录接受后实施一项 WP-13 前的可体验诊断闭环切片；WP-13—17 不得标为已开始或已接受。该切片是独立交付，不能预先写成已成功。

依据为[实施契约](wp-12-contract.md)、[实施结果](wp-12-result.md)、[A411 整改](wp-12-remediation-r1.md)、[集中审核 r1](wp-12-review-r1.md)、[ISSUE-001 定点复核 r2](wp-12-review-r2.md)、[RECOVERY-001 首轮整改](wp-12-recovery-remediation-r1.md)与[复核 r1](wp-12-recovery-review-r1.md)、[残留整改 r2](wp-12-recovery-remediation-r2.md)与[最终定点复核 r2](wp-12-recovery-review-r2.md)。原失败和整改历史不改写。

写入前将 RECOVERY-001 r2 [基准](evidence/wp-12-recovery-review-r2/baseline.json)所列源码、测试、原反例、历史报告及测试 XML 逐一核对，**0 项不匹配**；[最终哈希记录](evidence/wp-12-recovery-review-r2/final-hashes.json)显示基准文件差异 0。r2 报告 SHA-256 为 `0CD386CA40AFC184F32BAF7C6B1559B815B470513DE046FE1C61587AE85A527B`；Git index SHA-256 为 `C451D6E78B8F29FC818002923A19FB1A888139CED20679AD545F75E9692A9EC6`，与 r2 相同。无未解释实现差异。仓库无 HEAD 且有大量既有未提交交付，本次授权不代表清理或提交。

## 接受范围和证据版本

接受 A410 的观察事务及幂等/所有权/输入校验；A411 的保守区域自动收尾、唯一 `unknown` 卡与合格待生成区域衔接；A412 的不可变观察更正、epoch 失效与旧 worker 隔离；A413 的**确定性合成资料**两组不同已保存观察引向不同有据后续检查；A414 的无法测量、未检查、冲突与资料不足不假完成。ISSUE-001 依据[公开区域激活 r2](wp-12-review-r2.md)关闭；RECOVERY-001 依据[隔离残留 r2](wp-12-recovery-review-r2.md)关闭。区域卡目前仅作 `unknown` 保守摘要，不是 supported/ruled_out 或正式报告依据。

测试证据分开记录，不累加重复路径为不同功能覆盖数：

- 执行者旧版标准完整入口 **481 passed、1 条既有警告、退出 0**，在后续 RECOVERY-001 差异前运行；不是当前版本重新全量通过。
- RECOVERY-001 r2 当前代码定点首轮 **8 passed、2 个审核探针 fixture 错误、退出 1**；补正仅审核探针的 fixture 接线后单独 **2 passed、退出 0**。原 HTTP 失败反例在首轮 8 项中通过。原始命令、XML、日志和隔离库状态见[r2 证据](evidence/wp-12-recovery-review-r2/)。
- r1 的 A410、A412—A414 限定通过和 A411 失败、ISSUE-001 r2 关闭、RECOVERY-001 r1 未关闭均保留为各自版本结论。当前限定 `REVIEW_PASS` 仅来自 RECOVERY-001 r2 与未变部分的合并判断。本任务参与过实施、整改和复核，**不声称不同任务独立审核**。

## 保留与停止点

- 两次真实 DeepSeek→DKVB turn 都未发布当前检查。DKVB 缺精确适配字段，已有资料尚不能与有界步骤规则形成合法检查；安全拒绝不是模型成功。真实模型发布不在 WP-12 本次接受范围。
- 真实资料门槛仍 `NOT_MET`，原 WP-10/真实效果验收前的截止要求已未满足，不顺延或写成通过。合成 fixtures 不是维修标准或真实维修效果。
- 生产恢复与隔离病例人工处置未验证，旧 worker 首次失败根因未确证；Linux BGE 部署、历史启动/SSE/Compose 未确认事项及其他性能、监控、清理待办继续保留。
- `unknown` 区域卡不得转成 `supported`/`ruled_out`。WP-13 报告门槛未完成；正式诊断网页与进度报告也未接受。本次切片不生成最终报告。
- 原共享人民币 5 元总授权不重置；本次接受记录不读取账本或进行付费调用。WP-13—17 保持 `NOT_STARTED`，不接受整个 P4。

本次接受先于独立闭环切片实施记录。接受本身只新增此文件并更新 `STATUS.md`；后续切片的代码、验证、成败及证据另行记录，不反写为 WP-12 接受证据。
