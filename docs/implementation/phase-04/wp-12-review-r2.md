# WP-12 ISSUE-001 定点复核 r2（2026-09-20）

**结论：ISSUE-001 关闭；另发现独立的跨病例恢复阻断，WP-12 整体仍为 `CHANGES_REQUIRED`。** 本报告只复核公开区域激活整改及其相邻恢复路径，不是用户接受，不扩展到 WP-13。

## 基准与范围

已读 STATUS、[r1 审核](wp-12-review-r1.md)、[r2 整改](wp-12-remediation-r2.md)、两处整改源码、正式回归和 `JobStore.reconcile_wait/reconcile_pending`，以及整改时两项相邻测试的原始失败日志。适用祖先与目标目录未发现 `AGENTS.md`。将整改证据的 `source-diff.json` 所列 12 个源码/测试路径重新计算 SHA-256，**12/12 与整改记录相同**；正式新增测试 SHA-256 为 `8426444B942E748D38CEDB201C9547586A76FEFBF157CBD5E7C4596BFC7AFD53`。整改报告及 `verified.xml` 只读哈希分别为 `2514C378D88B84D0F54F06A0B422194F05A21074B5523E700EA88C9B348044CB`、`5071B64064C6570BBD004DD2F93885188D6F3DD15D19B2DF49858AD9B5C48566`。Git index SHA-256 前后均为 `C451D6E78B8F29FC818002923A19FB1A888139CED20679AD545F75E9692A9EC6`；未发现无法解释的整改后实现差异。原 r1 反例、500 与历史失败日志未覆盖。

本轮使用三个全新 `xiutu_test_wp12_review_r2_*` PostgreSQL 数据库，分别迁移至当前 head 并初始化 graph checkpoint；库名、创建、迁移、checkpoint、pytest XML/日志均在 [本轮证据目录](evidence/wp-12-review-r2/)。`TEST_DATABASE_URL`/`DATABASE_URL` 仅指这些隔离库，测试目录各自独立；移除付费模型密钥且设置免费测试模式。没有操作 5180/5196、旧项目、原资料或历史证据。**整改前 481 项完整回归仅是历史版本证据，本轮未全仓重跑。**

命令、实际隔离库名及临时目录另见 [command-inventory.txt](evidence/wp-12-review-r2/command-inventory.txt)；未记录连接密码或令牌。

## ISSUE-001：关闭

- 原审核的真实 HTTP 反例保持原断言运行：旧区域 `unavailable`、case `needs_review`、另一 pending 区域时，`activate` 返回 **409**，未因不存在的 `runs.created_at` 返回 500；未新增 activation run、卡、事件或 revision。`area_service.py:77-191` 不再按时间/UUID 猜续接 run，而以当前 revision 唯一 `area_close` publication，核对 run、workflow、turn、epoch、graph_progress、原保守卡与当前来源。缺失、重复、状态不一致均安全拒绝。实际 HTTP 缺失/重复/状态不一致三项新增审计探针均为 **409** 且无新任务。
- `area_lifecycle.py:40,71-151` 的同一 `completion_basis` 被自动收尾与公开激活复用。正式回归覆盖旧区域未完成、同组冲突、来源失效、活动 run、旧 epoch；均没有越过旧区域。目标须为本 epoch 最早合格 pending、没有仍 active 的区域或未审计 retired 区域；冻结资料资格也重验。
- 真正已提交收尾且尚无自动 activation 的合成正例，HTTP 返回 **202**，只创建一条下一任务；同 key 重放原响应，异请求拒绝。任务发布了来源支持的 Q02 检查，旧步骤、观察和区域卡仍可读。隔离库关系 SQL 记录为 `activation_total=3, linked_correctly=3`，核对 activation run 的 parent、workflow、input_revision、target area、graph epoch 与已提交 `area_close` 对应；3 条中含被取消的自动 activation，故只有 2 条当时处于 queued/running/completed，不把取消误记为丢失。自动收尾已入队目标，即使其任务随后取消，公开入口也不重复入队。

本轮命令：`python -B -m alembic upgrade head`、`python -B scripts/setup_graph_checkpoint.py` 均退出 **0**；`.venv/Scripts/python.exe -B -m pytest -p no:cacheprovider tests/integration/test_wp12_area_activation.py tests/integration/test_wp12_area_closure.py docs/implementation/phase-04/evidence/wp-12-review-r1/test_audit_wp12.py -q --tb=short --basetemp <独立目录> --junitxml <本轮目录>/regressions.xml` 退出 **0，17 passed**，见 `regressions.txt/xml`。这 17 项包括原 r1 两项审计脚本实例；不能与历史或下述实例相加作为新功能覆盖数。

## 两项相邻测试及跨病例隔离

整改执行者曾在同一库先运行故障注入的 `test_same_epoch_broken_publication_is_not_silently_skipped`，随后观察提交与图恢复两个 worker 在业务断言前退出 1；其原始 traceback 指向 `Worker.once -> reconcile_pending -> reconcile_wait -> CHECKPOINT_INCONSISTENT`。本轮在**另一干净库**只运行 `test_observation_atomic_idempotent_and_public_resume_closed`、`test_graph_interrupt_and_saved_observation_resume`：退出 **0，2 passed**，见 `adjacent.txt/xml`。这证明两项自身在当前代码和干净库可通过，**不证明异常库中的跨病例问题只属夹具污染**。

为区分两者，本轮新增只存于审核证据目录的故障探针。在隔离库先准备各自正常的病例 A、B；B 提交观察后有 queued 续接任务；仅将 A 已提交 `publish` 对应的 graph_progress 留在 `evaluating` 并改为不匹配 workflow，保持 A 的异常记录。调用 `reconcile_pending()` 得 `CHECKPOINT_INCONSISTENT`；随后显式 `Worker.once(run_id=B)` 在**领取 B 前**仍抛相同错误，B run/job 均保持 queued。审核脚本输出 `cross_case_blocked=true`，独立 SQL 核查为 **1 条同 epoch workflow 不匹配待对账记录、1 条 queued diagnosis job**，见 `probes-after-fixture.txt/xml`、`cross-case-db-state.txt`。因此这不是仅由 pytest 顺序造成的表面失败：同库存在真实跨病例故障传播。

本轮审核探针首跑退出 **1、4 个 setup error**，原因是新脚本漏导入测试库 fixture，**没有执行任何业务断言**；保留 `probes.txt/xml`。只修本轮审核脚本的 fixture 导入，不修改实现或原测试断言；同一尚未写业务数据的隔离库重跑退出 **0，4 passed**（3 个区域关系反例、1 个跨病例隔离反例）。上述故障注入的病例 A 记录留在该隔离库，未删改以换取通过。

## 新发现：RECOVERY-001（P2，必须整改后再认定整体 WP-12 恢复隔离）

**触发**：同一数据库某病例保留一条 `runs.status=waiting_input`、`graph_progress.phase=evaluating`、但 `graph_progress.workflow_id` 与已提交 `publish.workflow_id` 不一致的同 epoch 待对账记录。当前可通过隔离库故障注入稳定复现；尚未证明正常公开 API 或常规崩溃会自行制造该具体不一致。

**影响**：`backend/app/infrastructure/job_store.py:411-423` 的全局 `reconcile_pending()` 在 worker 领取任何指定 run 前运行（`backend/app/worker.py:53`）。A 的 `reconcile_wait()` 在 `job_store.py:397-402` 抛出的不一致直接向外传播，使无关病例 B 的 queued 任务也不能被该 worker 领取。不能把它归为“仅测试夹具污染”；异常数据是注入的，但跨病例阻断是生产代码的实际行为。原同 epoch 一致性异常应继续报错，不能以全局跳过或改为成功掩盖。

**最小整改建议**：按 run/case 隔离恢复错误；对异常 A 持久记录可诊断的恢复失败/隔离状态并阻止 A 被错误推进，同时允许 B 的领取继续。定义有界重试或人工处置边界，避免每次 worker 启动重复命中 A；保留 owner/epoch/publication 一致性检查。定点复核在同一隔离库保留 A 异常，验证 B worker 可领取/完成自己的任务而 A 仍明确失败，并验证同 epoch 不一致没有被静默修正。本轮**未修改**这些代码。

## 结论与停止点

ISSUE-001 的公开激活 500、未完成旧区域越区风险和重复入队要求，在当前合成技术范围内已由代码审查、真实 HTTP、隔离 PostgreSQL 和最终 17 项定点证据支持，**建议关闭 ISSUE-001**。两项相邻测试在干净库通过，但新发现 RECOVERY-001 是恢复路径的跨病例可用性阻断，故 **WP-12 整体暂不建议 `REVIEW_PASS`，结论 `CHANGES_REQUIRED`**；后续只需处理该独立问题并定点复核，不重新打开 ISSUE-001 或整包。

没有真实 DeepSeek→DKVB 当前检查发布、真实维修资料门槛、自动确诊、正式观察前端、生产恢复或 WP-13 报告验收。旧 worker 首次失败根因、Linux BGE 与历史启动/SSE/Compose 未确认项继续保留。本任务与先前实施/整改位于同一任务链，**不是不同任务独立审核**。未修改业务实现、STATUS、接受记录、原证据、Git index；未付费、提交、推送或操作用户实例。等待用户决定。
