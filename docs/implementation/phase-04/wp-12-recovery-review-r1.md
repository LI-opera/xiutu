# WP-12 RECOVERY-001 定点复核 r1（2026-09-20）

**结论：RECOVERY-001 尚未完整关闭；WP-12 限定技术范围仍为 `CHANGES_REQUIRED`。** 跨病例 worker 阻断本身已修复，但隔离的病例 A 仍可通过公开观察接口推进 revision 并创建下一任务。本报告仅审 RECOVERY-001，不重开已关闭的 ISSUE-001，不是用户接受，也不进入 WP-13。

## 基准与取证范围

先读 [STATUS](../STATUS.md)、[r2 审核](wp-12-review-r2.md)、[RECOVERY-001 整改](wp-12-recovery-remediation-r1.md)、两轮[原始跨病例证据](evidence/wp-12-review-r2/)和[整改证据](evidence/wp-12-recovery-remediation-r1/)，并检查 `JobStore.reconcile_wait/reconcile_pending`、`Worker.once` 与新增正式测试。适用祖先及目标路径未发现 `AGENTS.md`。[本轮哈希记录](evidence/wp-12-recovery-review-r1/baseline.json)与整改封存逐项对照：整改列出的 12 个源码/测试路径无新增差异，新增正式测试哈希匹配；r2 报告、原探针及 XML 匹配；Git index SHA-256 仍为 `C451D6E78B8F29FC818002923A19FB1A888139CED20679AD545F75E9692A9EC6`。`job_store.py` 是声明的唯一既有实现差异。没有无法解释的基准变化。

本轮新建隔离库 `xiutu_test_wp12_recovery_audit_cf057341`，记录在 [db-name.txt](evidence/wp-12-recovery-review-r1/db-name.txt)。`docker exec ... CREATE DATABASE`、`alembic upgrade head` 和 `scripts/setup_graph_checkpoint.py` 均退出 **0**，原始输出见 `create.txt`、`migrate.txt`、`checkpoint.txt`。测试环境仅指向该 `127.0.0.1:5433` 测试库，使用合成 fixture、独立 `.test-runs` 目录、`XIUTU_WP11_PAID=0`，移除模型密钥；未调用付费服务或操作 5180/5196。审核新增反例只存于[本轮证据目录](evidence/wp-12-recovery-review-r1/)，没有改正式测试、实现或历史证据。整改前 **481 项完整回归**仅是历史版本证据，本轮未重复整包。

## 对账隔离、跨病例完成与故障边界

`job_store.py:361-462` 仍在同一物理 advisory 锁连接、owner/case/run/progress 行锁和事务中核对当前 epoch、case owner、run/step/publication 的 case、run/turn、workflow、revision 与 phase。旧 epoch 被保留为历史，正常 `evaluating` 在发布已提交后变为 `waiting_input`；同 epoch 不一致写入 `graph_progress.phase=failed`、有限的 `CHECKPOINT_INCONSISTENT`/`manual_review` 错误及一条 `checkpoint.quarantined` 事件，**不修正原 publication 或 checkpoint 引用**。直接 `reconcile_wait(A)` 仍抛 `CHECKPOINT_INCONSISTENT`。`reconcile_pending()` 只在隔离标记持久提交后继续；标记失败或其他异常不会被当成已隔离。

本轮命令与隔离库/临时目录见 [command.txt](evidence/wp-12-recovery-review-r1/command.txt)。实际执行：

| 命令/证据 | 退出码与结果 |
| --- | --- |
| `.venv/Scripts/python.exe -B -m pytest -p no:cacheprovider tests/integration/test_wp11_graph.py::test_start_publish_wait_and_replay tests/integration/test_wp11_graph.py::test_graph_interrupt_and_saved_observation_resume tests/integration/test_wp12_area_closure.py::test_old_area_end_checkpoint_rejected_after_epoch_change tests/integration/test_job_recovery.py::test_two_workers_exact_barrier tests/integration/test_wp12_recovery_isolation.py::test_bad_case_is_quarantined_and_other_case_worker_completes docs/implementation/phase-04/evidence/wp-12-recovery-review-r1/test_audit_recovery.py -q -s --tb=short --junitxml .../targeted.xml`，审核反例新增第三项之前的明确选择 | **0，7 passed**，119.84 秒；[targeted.txt](evidence/wp-12-recovery-review-r1/targeted.txt) / [XML](evidence/wp-12-recovery-review-r1/targeted.xml)。包含真实独立 worker 跨病例反例、重复启动/对账、正常待对账、旧 epoch、观察恢复、no-op worker。不能把执行者先前 8 项重复累加为覆盖数。 |
| PostgreSQL `BEFORE INSERT` 触发器只让 `checkpoint.quarantined` 事件写入报错；同组审核用例 | **0，断言通过**：该事务的 phase/error/event 全回滚，B job 仍 queued、attempt=0、revision=2、publication=0；`Worker.once(B)` 抛数据库错误，未越过失败隔离标记领取 B。触发器仅在本轮隔离库建立，测试后移除。 |
| 将 A 的 `reconcile_wait` 注入非 `CHECKPOINT_INCONSISTENT` 的有界 `DomainError`；同组审核用例 | **0，断言通过**：错误原样上抛，A 未写隔离标记，B 未领取；不把其他错误码误当作已隔离。 |

正式新增测试在同库先留下 A 的同 epoch workflow mismatch、B 的 queued 续接任务，再由**另一 Python 进程**调用 B worker：B 只产生一条 publication、job completed/attempt=2、revision=3；A 的 workflow mismatch、publication hash/revision、step、原 checkpoint 引用和原 job 保持，错误码及一条隔离事件持久存在。第二次 worker 启动和重复全局对账未追加事件或再发布。与 r2 原反例使用同一种故障注入；原 r2 审核脚本的“必须阻断 B”旧断言已不适用，**没有改写该脚本或宣称它在整改后通过**。整改执行者保留的只读 SQL 显示两条 A 异常记录各一条隔离事件与原 publication、B 一条 publication；本轮正式测试独立复核了对应逐行断言。病例 A 的 `run.status=waiting_input` 保留已提交历史；隔离由 `graph_progress.phase=failed` 和有限错误/事件表达，不能把该状态误报为 checkpoint 成功。

## 未关闭的残留：公开观察可越过 A 隔离（P1）

代码检查发现 `job_store.py:419-424` 只隔离该 run 的 checkpoint，未阻断该病例继续使用原待答步骤。`observation_service.py:76-113` 仅检查 case/step/parent run 为 `waiting_input` 和 revision 相符，**不检查 parent `graph_progress.phase=failed` 或 `runs.error_json.code=CHECKPOINT_INCONSISTENT`**，随后提交观察、完成旧步骤、revision+1 并建立下一 run/job。

为验证这一具体风险，在原审核库运行[新增单项反例](evidence/wp-12-recovery-review-r1/test_audit_recovery.py)：先创建合成 case 与已发布步骤，注入同 epoch workflow mismatch，调用全局对账确认 `phase=failed`，再通过公开 HTTP 观察接口提交当前步骤的有效选择。命令和临时目录见 [commands-extra.txt](evidence/wp-12-recovery-review-r1/commands-extra.txt)；退出 **1**，原因是安全断言预期 409、实际 **202**。原始 [失败日志](evidence/wp-12-recovery-review-r1/quarantined-use.txt) / [XML](evidence/wp-12-recovery-review-r1/quarantined-use.xml) 保留。HTTP 前后 revision **1→2**；[独立只读 SQL](evidence/wp-12-recovery-review-r1/quarantined-use-db.txt) 退出 **0**，确认该隔离病例保留旧 `phase=failed` 与错误码的同时，新增 **1 条观察、1 条 child run、1 条 queued job**。其他三条隔离病例未被此请求推进。这不是只看 UI/错误文案，而是同一隔离库的实际业务写入。

**影响**：A 的恢复一致性已被判定需要人工处置，但其原步骤仍可作为“正常可答”继续推进同一 case；`manual_review` 不是有效的业务隔离。继续执行的新任务可能建立在损坏的 workflow/step 关系上。跨病例 B 的可用性已经恢复，但 RECOVERY-001 要求的 A 安全隔离尚不完整。

**最小整改要求与定点复核**：在公开观察提交的原 owner/case/parent 事务锁内，使用当前 parent run 的持久 `graph_progress` 与错误码拒绝被隔离的步骤（明确 409），在写 observation、step、revision、run/job、事件与幂等成功响应之前判定；必要时核对其他公开续接入口不能使用同一被隔离 parent。保留已提交 publication/历史与 A 的错误标记，不通过清除异常或改判成功让反例通过。复核应断言：A 仍可读且明确异常，观察请求 409、case revision/step/observation/child run/job 均不变；同库 B 继续完成；正常未隔离观察和旧 epoch 恢复仍通过。此整改与已关闭的公开区域激活 ISSUE-001 无关。

## 结论与限制

跨病例 worker 启动、持久失败标记、重复启动去重、SQL 写标记失败回滚及其他错误不吞掉，**在本轮合成隔离数据库中通过**。但上述公开观察反例使 A 能越过隔离继续业务写入，因此 **RECOVERY-001 暂不关闭，WP-12 目前不达到限定范围 `REVIEW_PASS`，结论 `CHANGES_REQUIRED`**。本轮没有证明生产故障自然生成该被注入的具体不一致，也没有完成生产人工处置/恢复、真实 DeepSeek→DKVB 检查发布、真实资料门槛或真实维修效果。

本任务参与过先前实施/整改，**不是不同任务独立审核**。未修改实现、STATUS、接受记录、旧项目、历史证据或 Git index；未付费、提交、推送或操作用户实例。等待用户决定，仅针对上述残留做后续定点整改与复核。
