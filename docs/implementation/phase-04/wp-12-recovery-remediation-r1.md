# WP-12 RECOVERY-001 定点整改（2026-09-20）

状态：**IMPLEMENTED_NOT_ACCEPTED，等待仅针对 RECOVERY-001 的定点复核**。这是执行者整改与自测记录，不是审核通过或用户接受；已关闭的 ISSUE-001 未重开，WP-13 未启动。

## 基准、触发与差异

先核对 [STATUS](../STATUS.md)、[r2 审核](wp-12-review-r2.md)及其[跨病例原始证据](evidence/wp-12-review-r2/)、`JobStore.reconcile_wait/reconcile_pending`、`Worker.once`、区域与恢复测试。祖先及目标路径未发现适用 `AGENTS.md`。r2 原始反例中，病例 A 的同 epoch 已提交 publication 与 `graph_progress.workflow_id` 不一致；全局 `reconcile_pending()` 在任何任务领取之前抛出 `CHECKPOINT_INCONSISTENT`，使同库无关病例 B 的 queued worker 无法启动。A 的错误不能改为成功，也不能丢弃一致性检查。

[最终基准记录](evidence/wp-12-recovery-remediation-r1/baseline-final.json)逐一核对 r2 的 12 个源码/测试路径：仅 `backend/app/infrastructure/job_store.py` 改变；新增 `tests/integration/test_wp12_recovery_isolation.py` 和本报告/证据。`backend/app/worker.py`、区域服务、发布服务、旧迁移、原反例及历史报告未改。Git index SHA-256 前后均为 `C451D6E78B8F29FC818002923A19FB1A888139CED20679AD545F75E9692A9EC6`。r2 报告、原跨病例探针和 XML 的当前哈希另见该基准记录，未覆盖原证据。最终源码及新增测试哈希见 [final-source-hashes.json](evidence/wp-12-recovery-remediation-r1/final-source-hashes.json)。

## 最小修改与隔离条件

- `reconcile_wait()` 仍使用原物理 advisory 锁连接、owner 锁与 case/run/progress 行锁，并在同一事务核对当前 case epoch、病例 owner、run/case、publication/case、step/case/run/turn、workflow/turn、revision 与 phase。病例任务的 `runs.owner_id` 按既有写入契约为空，owner 以受锁保护的 `cases.owner_id` 为准。旧 epoch 在这些同 epoch 对账前返回，不被错误隔离。
- 同 epoch 不一致时，在原数据库事务内把该 run 的 `graph_progress.phase` 标为 `failed`，写入只含 `CHECKPOINT_INCONSISTENT`、`retryable=false`、`recovery=manual_review` 的 `runs.error_json`，并追加仅含错误代码的 `checkpoint.quarantined` 事件。事务提交后，直接对账仍抛原错误；**publication、step、checkpoint 引用、case revision、原 job 与业务结果不被修正或推进**。
- 全局 `reconcile_pending()` 只隔离已确认持久提交上述标记的 `CHECKPOINT_INCONSISTENT`。写标记或事件失败、标记缺失、其他错误均继续上抛，不让 B 在无法确认 A 状态时假装恢复成功。标记后的 A 不再进入自动扫描；重复启动不会追加第二事件或重新发布。自动重试次数为 **0**。操作者须先核实 publication、workflow/turn、step、owner/epoch 与根因，并经另行授权的受控修复流程处置；本包没有自动解隔离或修复接口，不能凭重启重试 A。
- `Worker.once()` 未改。它仍在领取任务前对账，但 A 的持久隔离不再阻断 B。现有发布、锁、租约、fencing 和幂等路径未改。

## 隔离 PostgreSQL 验证

所有数据库均为本轮新建的 `xiutu_test_wp12_recovery_*`，在 `127.0.0.1:5433`，独立执行 `alembic upgrade head` 和 `scripts/setup_graph_checkpoint.py`（退出 0）；测试设置 `XIUTU_WP11_PAID=0`，移除模型密钥。库名及初始化日志在[本轮证据目录](evidence/wp-12-recovery-remediation-r1/)。无业务库、5180/5196 或旧项目操作。下面命令均从项目根目录执行，输出分别重定向到本轮目录；`--basetemp` 使用各自独立的 `.test-runs/wp12-recovery-*` 路径。

| 运行 | 命令与退出码 | 结果、版本边界 |
| --- | --- | --- |
| 首轮跨病例反例 | `python -B -m pytest -p no:cacheprovider tests/integration/test_wp12_recovery_isolation.py -q --tb=short --junitxml evidence/wp-12-recovery-remediation-r1/first.xml`；**0** | **1 passed**，A 异常保留、B 新进程 worker 完成。此时尚未增加重复启动断言及最终关系核对，见 `first.txt/xml`。 |
| 相邻组命令错误 | 同一隔离库中选择 6 项 WP-11/12、no-op、ingest 恢复；**1** | 6 个 setup error，测试库 URL 错用了仓库不允许的 `postgresql+psycopg`，业务未执行；保留 `targeted.txt/xml`。 |
| 相邻组重跑 | 改用契约要求的 `postgresql://`，原 6 项选择不变；**0** | **6 passed**，涵盖正常待对账、已存观察恢复、旧 epoch、观察事务幂等、双 worker 与 ingest 故障恢复；见 `targeted-corrected.txt/xml`。 |
| 新增断言首轮 | 新跨病例反例加原审核同 epoch 反例；**1** | **1 failed、1 passed**。测试把已完成 B 的第二次 `Worker.once()` 正常返回“无任务”误断言为“必须再完成一项”；未修改生产逻辑，原记录在 `final.txt/xml`。 |
| 扩展关系校验首轮 | 最终 8 项定点选择；**1** | **5 failed、3 passed**。新加的 `runs.owner_id == actor` 与现有病例任务 `owner_id=NULL` 契约冲突，误隔离正常发布；保留 `verified.txt/xml`。移除此错误比较，保留 case owner 与其他真实关联校验。 |
| **最终代码，全新隔离库** | `python -B -m pytest -p no:cacheprovider tests/integration/test_wp12_recovery_isolation.py::test_bad_case_is_quarantined_and_other_case_worker_completes docs/implementation/phase-04/evidence/wp-12-review-r1/test_audit_wp12.py::test_same_epoch_broken_publication_is_not_silently_skipped tests/integration/test_wp11_graph.py::test_start_publish_wait_and_replay tests/integration/test_wp11_graph.py::test_graph_interrupt_and_saved_observation_resume tests/integration/test_wp12_area_closure.py::test_old_area_end_checkpoint_rejected_after_epoch_change tests/integration/test_wp12_turns.py::test_observation_atomic_idempotent_and_public_resume_closed tests/integration/test_job_recovery.py::test_two_workers_exact_barrier 'tests/integration/test_document_ingest.py::test_ingest_fenced_publication_recovery[crash]' -q --tb=short --junitxml evidence/wp-12-recovery-remediation-r1/final-current.xml`；**0** | **8 passed**，112.60 秒。数据库 `xiutu_test_wp12_recovery_c4919d617ff5`，对应最终代码哈希见上述封存；日志/XML 为 `final-current.txt/xml`。 |

最终反例在**同一数据库**内先留 A 异常，再由另一 Python 进程运行 B 的真实 `Worker.once(run_id=B)`。测试在注入前核对 A 已提交 publication、B revision=2；注入后断言 A 的 mismatch、publication hash/revision、checkpoint 引用、step/job 不变，B 进入 `waiting_input`、job completed/attempt=2、revision=3、只发布一条当前检查。再次启动 worker 和两次全局对账均不重写 A 或 B。原审核反例也仍能直接得到 `CHECKPOINT_INCONSISTENT`。[最终只读 SQL 状态](evidence/wp-12-recovery-remediation-r1/db-state-final.txt)显示两条 A 异常记录（新反例及原审核反例）均为 `phase=failed`、`manual_review`、workflow mismatch 保留、各一条隔离事件与原 publication；B 为 completed、attempt=2、revision=3、publication=1。这里的 A `run.status=waiting_input` 保留已提交业务历史，**不能将它解释成 checkpoint 成功**；隔离判定看 `graph_progress.phase`、错误码和事件。

整改前 **481 项完整回归**仅为历史证据，本轮没有重跑整包，也不把不同版本/库的结果相加为功能覆盖数。最终代码只改变 diagnosis 的异常待对账分支；针对共用 worker 入口另外选了 no-op 与 ingest 恢复，未扩展公共任务领取、发布或租约语义。

## 保留限制与停止点

本轮证明的是被注入的同 epoch 不一致可被持久隔离且无关 B 可继续；没有证明该异常能由正常公开 API 自发生成，也未演练人工修复或数据库持久化失败后的故障恢复。标记写入失败时按原 fail-closed 行为阻断当次 worker，不把失败伪装成隔离成功。生产异常处置仍需操作者核查及单独授权；没有自动重试、清理或成功修复 A。真实 DeepSeek→DKVB 当前检查发布、真实资料门槛 `NOT_MET`、旧 worker 首次失败根因未确证及其他既有限制均不因本整改改变。

WP-12 保持 **IMPLEMENTED_NOT_ACCEPTED**；本报告不是 RECOVERY-001 的审核关闭结论。未付费调用、提交、推送、修改 STATUS、接受记录、原报告/证据、旧迁移或 Git index；等待定点复核。
