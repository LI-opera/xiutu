# WP-12 ISSUE-001 区域激活定点整改（2026-09-20）

状态：**IMPLEMENTED_NOT_ACCEPTED，等待 ISSUE-001 定点复核**。本文只记录执行者整改与自测，不是审核通过或用户接受；WP-13 未启动。

## 基准与根因

整改前核对 `wp-12-review-r1.md`、`wp-12-remediation-r1.md`、A411 代码、ORM 和审核真实 HTTP 反例。原反例的 HTTP 500、两次审核夹具 setup 失败、旧完整入口 481 通过及 25 项受影响组证据均原样保留。审核基准中的 `runs` 表没有 `created_at`；公开 `AreaService.activate()` 却据此排序，先触发 `AttributeError`。即便改用任意时间或 UUID 排序，原入口也没有证明旧活跃区域已完成，可能越过 `unavailable`、冲突或失效来源。

本轮与审核基准的源码哈希对照见 [source-diff.json](evidence/wp-12-remediation-r2/source-diff.json)：12 个受保护源码/测试路径中，仅 `area_service.py`、`area_lifecycle.py` 改变；另新增正式回归 `test_wp12_area_activation.py` 和本轮报告/证据。`publish_service.py`、`job_store.py`、checkpoint、旧迁移、旧测试及 STATUS 未改。Git index SHA-256 前后均为 `C451D6E78B8F29FC818002923A19FB1A888139CED20679AD545F75E9692A9EC6`；项目既有未跟踪/暂存状态未调整。

## 最小改动

- 将自动 `area_close` 现有的步骤全部完成、有效观察、`checked`、非 `unavailable`、来源/比较当前有效、同组无冲突、无其他活跃任务判定抽为 `completion_basis()`。自动收尾继续在原 fenced 发布事务内调用；公开激活以 `expected_status=completed` 只读重验同一事实，不额外写卡。
- 公开激活先锁定 owner/case 与当前 epoch 的区域，保留 owner、revision、graph_epoch、CSRF/Idempotency-Key、待答步骤和活跃任务保护。仅允许 case 为 `needs_review`、目标是最早合格 pending、没有 active/未经审计 retired 区域。旧区域必须有当前 revision **唯一**的已提交 `area_close` publication，并核对其 run、workflow、turn、graph_progress、output_revision、响应关系、原保守卡及当前观察/来源。缺失、重复或不一致均返回 409；不猜“最新 run”。冻结 manifest 的当前资格也重新检查。
- `area_close` 已自动入队目标时，publication 中的 `next_run_id` 与现有 activation run 均阻止再入队；即使自动任务后来终止也不会重造。合法请求仍由原 `enqueue` 写 run/job、graph_progress、事件和 case 状态；同 key 同内容沿用幂等历史响应，异请求受活跃任务/已激活规则拒绝。原观察、步骤与卡不改写。
- 不变更 WP-11 的领取、租约、advisory 锁、fencing 或 checkpoint 逻辑；未触及共用发布路径。

## 隔离验证与真实结果

使用三个全新 `xiutu_test_wp12_activation_*` PostgreSQL 库，分别迁移至当前 head 并运行 `scripts/setup_graph_checkpoint.py`；库名、迁移日志、checkpoint 日志在 [本轮证据目录](evidence/wp-12-remediation-r2/)。所有 HTTP 请求由真实测试 API、数据库及本地 worker 执行，使用合成资料，未设置付费模型凭据。原审核脚本保持原样；所有新输出另存。

| 版本与命令 | 退出码、结果与证据 |
| --- | --- |
| 首轮：`python -B -m pytest -p no:cacheprovider tests/integration/test_wp12_area_activation.py docs/.../test_audit_wp12.py::test_unfinished_area_cannot_be_bypassed_by_explicit_activation -q --tb=short --junitxml ...` | **0，6 passed**，见 `first.txt/xml`。原 500 反例现在 HTTP 409，且无 activation run。此轮在后续关系加固与扩充测试前，不是最终版本全量证明。 |
| 最终代码：`python -B -m pytest -p no:cacheprovider tests/integration/test_wp12_area_activation.py tests/integration/test_wp12_area_closure.py docs/.../test_audit_wp12.py tests/integration/test_wp12_turns.py::test_observation_atomic_idempotent_and_public_resume_closed tests/integration/test_wp11_graph.py::test_graph_interrupt_and_saved_observation_resume -q --tb=short --junitxml ...` | **1，17 passed、2 failed**，见 `verified.txt/xml`。17 项涵盖原 HTTP 反例、合法续接并发布 Q02 有据检查、同 key/异 key、自动入队去重、取消后仍不重入、`unavailable`、同组冲突、来源撤销、旧 epoch 与同 epoch 损坏 publication。后两项在业务断言前，其隔离 worker 启动全局对账被本命令前面的“同 epoch 损坏 publication”故障注入记录阻断；原始 traceback 见 `adjacent-worker-failure-*.log`。这不是把失败改写为通过，也不放宽对账。 |
| 最终代码、另一全新库：只运行上述观察幂等和跨进程图恢复两项，故障注入不在该库执行 | **0，2 passed**，见 `adjacent.txt/xml`。与前一条 17 项按环境和目的分别记录，不相加为新的功能覆盖数。 |

新正式测试直接断言被拒前后的 case revision、卡、事件、旧步骤、activation run；合法路径断言只产生一个 activation run，旧观察/卡仍在且 Q02 当前步骤已通过既有提案校验发布。最终隔离库的聚合只读状态在 `db-final-state.txt`（17 个测试 case、3 条 activation run、7 张区域卡、6 条 `area_close` publication）；单个反例的前后不变量由测试断言提供，不能用跨测试聚合数字代替。旧完整 481 项与原 25 项属于整改前版本，本轮没有声称重新跑过完整入口。

## 边界

此整改只修公开区域激活，不增加真实资料、自动确诊、可信 retired 合并或 WP-13 报告。合法人工激活正例通过隔离夹具在原区域已提交 `area_close` 且未有 pending 时，再准备同 workflow 的 pending 区域；它证明接口的事务与门禁，不声称生产已具备独立的区域提议管理 UI。真实资料仍 `NOT_MET`；DKVB 精确适配不足、真实 DeepSeek→DKVB 尚未发布当前检查、旧 worker 首次失败根因未确证以及历史未确认事项继续保留。没有调用付费模型、操作 5180/5196、改动原资料包或提交推送。等待只针对 ISSUE-001 及受影响路径的定点复核。
