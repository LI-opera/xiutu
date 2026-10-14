# WP-12 RECOVERY-001 残留整改 r2（2026-09-20）

状态仍为 **IMPLEMENTED_NOT_ACCEPTED**。本报告是执行者整改与自测记录，不是审核关闭或用户接受；已关闭的 ISSUE-001 未重开，WP-13 未启动。

## 基准与触发

先核对 [STATUS](../STATUS.md)、[RECOVERY-001 复核 r1](wp-12-recovery-review-r1.md)及其中的 [HTTP 失败记录](evidence/wp-12-recovery-review-r1/quarantined-use.txt)、[先前整改](wp-12-recovery-remediation-r1.md)。祖先及目标目录未发现适用的 `AGENTS.md`。[写入前基准](evidence/wp-12-recovery-remediation-r2/baseline.json)与 r1 审核封存匹配。写后[差异核对](evidence/wp-12-recovery-remediation-r2/final-baseline-verification.json)显示，列入核对的既有文件仅 `backend/app/services/observation_service.py` 发生预期变化；`job_store.py`、公开区域激活与更正入口、原审核报告及失败证据未变。新增正式回归测试 `tests/integration/test_wp12_quarantined_observation.py`。Git index SHA-256 前后均为 `C451D6E78B8F29FC818002923A19FB1A888139CED20679AD545F75E9692A9EC6`。

r1 反例中，病例 A 的同 epoch publication/checkpoint 不一致已被持久标为 `graph_progress.phase=failed`、`CHECKPOINT_INCONSISTENT/manual_review`，但 parent run 为保留业务历史仍是 `waiting_input`。公开观察提交只校验 case、step、run 的等待状态，于是实际 HTTP 返回 202，revision 从 1 变 2，新增 observation、child run 和 job。

## 最小改动与边界

- `ObservationService.submit()` 保留原 owner advisory 锁和单事务。新提交在锁定 case、step、parent run 后，用同一连接锁定该 parent 的持久 `graph_progress`，在任何 observation、step、revision、run/job、事件或成功幂等响应写入前，比较当前 `graph_epoch`，拒绝 `phase=failed` 或当前 parent 的 `CHECKPOINT_INCONSISTENT`，返回 **409 `CHECKPOINT_QUARANTINED`**。原有 revision、owner、choice、资格及锁顺序未放宽。
- `run_service.idempotent()` 对同 key 同内容会直接返回已存 202，跳过 action。因此该返回路径也在 owner/idempotency 锁之后，按 **idempotency row → case → step → parent run → progress** 的顺序重验同一隔离状态。当前 epoch 的旧成功响应不能作为继续使用被隔离步骤的授权；拒绝不扣除或改写既有幂等记录。旧 epoch 的历史不因当前 epoch 的隔离被改成成功或自动清理。
- 公开 `diagnosis/resume` 仍拒绝直接以 observation UUID 续接；当前待答步骤的区域激活仍只是只读返回，不入队。观察更正走已保存事实的独立受控入口，既有合法更正测试通过。本轮未改变这些入口、worker、任务领取、publication、checkpoint 或数据库迁移，也未清除 A 的异常标记。

## 隔离 PostgreSQL 自测

本轮新建 `xiutu_test_wp12_quarantine_08e42266`，仅使用 `127.0.0.1:5433`、合成 fixtures、独立 `.test-runs` 目录；`alembic upgrade head` 与 `scripts/setup_graph_checkpoint.py` 退出 **0**，建库/初始化记录在[本轮证据目录](evidence/wp-12-recovery-remediation-r2/)。设置 `XIUTU_WP11_PAID=0`，未加载模型密钥。原始命令、输出和 XML 均留在该目录。测试数据库未作为业务库使用。

| 运行 | 实际命令与退出码 | 证据和结果 |
| --- | --- | --- |
| 首轮定点 | `.venv/Scripts/python.exe -B -m pytest -p no:cacheprovider tests/integration/test_wp12_quarantined_observation.py tests/integration/test_wp12_recovery_isolation.py::test_bad_case_is_quarantined_and_other_case_worker_completes tests/integration/test_wp12_turns.py::test_observation_atomic_idempotent_and_public_resume_closed tests/integration/test_wp12_turns.py::test_unavailable_correction_new_epoch_and_area_card tests/integration/test_wp12_area_closure.py::test_old_area_end_checkpoint_rejected_after_epoch_change -q --tb=short --basetemp .test-runs/wp12-quarantine-first-3baa96addd3a42db8c986b31489c387f --junitxml docs/implementation/phase-04/evidence/wp-12-recovery-remediation-r2/first.xml`；**0** | [first.txt](evidence/wp-12-recovery-remediation-r2/first.txt) / [first.xml](evidence/wp-12-recovery-remediation-r2/first.xml)：**7 passed**，100.78 秒。新 HTTP 测试覆盖新 key、重复 key、旧成功 key、只读激活/公开 resume；同库 B 独立 worker 仍完成。正常观察幂等、更正和旧 epoch 相邻测试通过。 |
| 原审核反例第一次收集 | 原文件 `test_audit_recovery.py::test_quarantined_case_cannot_advance_via_public_observation`，输出 `original.txt/xml`；**4** | 测试模块未加入 `tests` 导入路径，收集阶段报 `ModuleNotFoundError: conftest`，业务断言未执行；原样保留。 |
| 原审核反例第二次启动 | 同一原文件，补齐测试导入路径，输出 `original-corrected.txt/xml`；**1** | 隔离配置未完整注入，`Settings` 拒绝 synthetic profile，失败于 fixture 准备，业务断言仍未执行；原样保留。 |
| 原审核反例实际执行 | 同一原文件、同一隔离库，补齐 `APP_MODE=test`、`DATABASE_URL=TEST_DATABASE_URL`、`RETRIEVAL_PROFILE=synthetic`；**0** | [original-env.txt](evidence/wp-12-recovery-remediation-r2/original-env.txt) / [XML](evidence/wp-12-recovery-remediation-r2/original-env.xml)：**1 passed**，14.92 秒。保留原审核断言，HTTP 返回其预期 409；未改写历史测试。 |
| 只读 SQL 状态 | 容器内 `psql` 查询本轮隔离库的 failed progress、run 错误、revision、step、observation、child run 与隔离事件；**0** | [db-state.txt](evidence/wp-12-recovery-remediation-r2/db-state.txt)：未提交观察的隔离 A 均保留 `failed/CHECKPOINT_INCONSISTENT/manual_review`、revision 1、等待步骤、0 observation、0 child run、各 1 条隔离事件；已提交后才隔离的历史 key 夹具保留原 revision 2 和旧观察，不被本次重放改写。其他旧 epoch 测试记录与这些当前 A 记录分列，不据汇总行数推断跨测试因果。 |

正式反例在每个 HTTP 请求前后分别比较 revision、step、观察数、run/job/event ID、成功幂等记录数、progress 与 publication hash；返回 409 后这些项目一致。GET diagnosis 仍返回原当前步骤，GET run 明确显示 `CHECKPOINT_INCONSISTENT` 和 `manual_review`。B 的同库独立 worker 完成及仅一套 publication 由相邻正式用例断言。旧成功 key 的重放也返回 409，既有观察及原响应记录不被删除或重写。

## 保留限制与停止点

本轮使用注入的同 epoch 不一致证明公开观察不会绕过隔离，未证明该异常在生产中会自然发生，也未实现人工修复/解隔离或生产恢复。旧 epoch 历史、原 publication 和步骤可读，但不可将隔离的当前步骤当成已恢复成功。执行者不自行关闭 RECOVERY-001；请仅对本次差异定点复核。旧 worker 首次失败根因仍未确证，真实 DeepSeek→DKVB 检查发布、真实资料 `NOT_MET` 和其他既有限制不变。

整改前 **481 项完整回归**只是历史证据，本轮没有重跑整包，也不把不同版本与旧审核测试数量相加。未调用付费模型；未操作 5180/5196；未修改 STATUS、接受记录、原报告/证据、旧项目、旧迁移或 Git index；未提交或推送。
