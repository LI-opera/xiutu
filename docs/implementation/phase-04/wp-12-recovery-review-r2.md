# WP-12 RECOVERY-001 残留定点复核 r2（2026-09-20）

**结论：RECOVERY-001 在本次限定技术范围内关闭；结合 r1 未变的通过部分，建议 WP-12 限定合成技术范围 `REVIEW_PASS`。** 这不是用户接受，不扩大到真实模型发布、真实维修效果或生产恢复；WP-12 的 STATUS 仍为 `IMPLEMENTED_NOT_ACCEPTED`，WP-13 未启动。本任务曾参与 WP-12 的实施、整改与此前复核，**不是不同任务独立审核**。

## 固定基准和审核范围

已读 [STATUS](../STATUS.md)、[原复核及失败反例](wp-12-recovery-review-r1.md)、[r2 整改](wp-12-recovery-remediation-r2.md)及两轮原始证据。祖先和目标目录未发现适用 `AGENTS.md`。[本轮基准](evidence/wp-12-recovery-review-r2/baseline.json)逐项记录源码、正式测试、原反例、审核报告和 r2 整改 XML 的 SHA-256；`observation_service.py` 与新增正式测试完全匹配 r2 [封存哈希](evidence/wp-12-recovery-remediation-r2/final-baseline-verification.json)，未发现未解释的实现变化。[写后核对](evidence/wp-12-recovery-review-r2/final-hashes.json)显示基准文件差异 **0**，Git index 前后 SHA-256 均为 `C451D6E78B8F29FC818002923A19FB1A888139CED20679AD545F75E9692A9EC6`。原审核 `quarantined-use.txt` 中的 **HTTP 202、revision 1→2** 失败记录未覆盖或改写。

复核仅针对隔离 parent 被公开观察续接的残留。r1 已验证的跨病例 worker 隔离、直接对账显式报错、隔离事件去重及失败写标记不放行，作为未变基准引用；本轮再运行直接相关的跨病例用例。整改前 **481 项完整回归**只属于历史版本，不是当前版本完整入口结果。

## 代码和事务边界

- 新请求在 `backend/app/services/observation_service.py:75-102` 的原 owner advisory 锁及同一 `UnitOfWork` 中，依次锁定 case、当前 step、parent run，再用同一连接锁定该 run 的持久 `graph_progress`。`_reject_quarantined_parent()`（第 66—73 行）仅针对当前 case epoch 的 `phase=failed` 或 `CHECKPOINT_INCONSISTENT` 拒绝，返回 HTTP **409 `CHECKPOINT_QUARANTINED`**；判定发生在 observation、step、revision、child run/job、事件与成功幂等响应写入之前。对账同样锁 case、run、progress，不能在该判定后并发把同一 parent 隔离而让旧事务继续提交。
- `run_service.idempotent()` 的已提交同 key 路径会跳过 action 并返回原响应；因此 `observation_service.py:135-152` 对重放再次按 case→step→parent→progress 锁序检查。当前 epoch 的旧 202 receipt 不再等于当前可用授权。隔离拒绝不删除原成功 receipt，也不重做原观察。
- 公共 `/diagnosis/resume` 仍明确拒绝直接 UUID 续接；有本区待答步骤时，`AreaService.activate` 只返回 `read_only`，`conclude` 返回 `ACTIVE_STEP`，均不能从被隔离 parent 入队。合法观察更正与旧 epoch 历史路径仍按原独立规则处理。本轮未发现需要改变 worker、publication、checkpoint 或已关闭 ISSUE-001 的依据。

## 全新隔离 PostgreSQL 验证

本轮新建 `xiutu_test_wp12_rec_r2_48747bd8`，只用于合成技术测试；建库、`alembic upgrade head`、`scripts/setup_graph_checkpoint.py` 均退出 **0**，命令及脱敏环境见[初始化命令](evidence/wp-12-recovery-review-r2/commands-setup.txt)，原始输出见 [建库](evidence/wp-12-recovery-review-r2/create.txt)、[迁移](evidence/wp-12-recovery-review-r2/migrate.txt)、[checkpoint](evidence/wp-12-recovery-review-r2/checkpoint.txt)。连接只指向 `127.0.0.1:5433/xiutu_test_*`，独立 storage 和 `.test-runs` 临时目录；禁用付费探针并移除模型密钥。未操作 5180/5196。

| 命令和版本 | 退出码、结果与原始证据 |
| --- | --- |
| [定点命令](evidence/wp-12-recovery-review-r2/command.txt)：`.venv/Scripts/python.exe -B -m pytest -p no:cacheprovider`，选择原审核 HTTP 反例、r2 正式 3 项、同库 B worker、正常观察幂等、合法更正、旧 epoch，以及本轮审核 2 项；`-q --tb=short --basetemp <本轮唯一目录> --junitxml .../targeted.xml` | **1：8 passed、2 errors**，[原始日志](evidence/wp-12-recovery-review-r2/targeted.txt) / [XML](evidence/wp-12-recovery-review-r2/targeted.xml)。两项错误仅在本轮新增审核探针的 fixture 准备阶段：漏接既有 `database_url` fixture，未执行其业务断言；原记录保留。其余 8 项（含未改动原审核反例）实际通过。 |
| [夹具补正后命令](evidence/wp-12-recovery-review-r2/command-followup.txt)：仅运行上述两项本轮审核探针，不重复前 8 项 | **0：2 passed**，[原始日志](evidence/wp-12-recovery-review-r2/followup.txt) / [XML](evidence/wp-12-recovery-review-r2/followup.xml)。补正只在本轮证据探针中加入 `database_url` fixture，没有修改实现或业务断言。 |
| 本轮隔离库[只读 SQL](evidence/wp-12-recovery-review-r2/db-query.sql)：查询隔离 progress、错误、revision、step、观察、child run、隔离事件及原 publication；并统计 B 的已完成重试 job | **0**，[原始输出](evidence/wp-12-recovery-review-r2/db-state.txt)。未先提交观察的隔离 A 均为 revision 1、待答 step、0 observation/child run、各一条隔离事件及原 publication；先提交后才注入隔离的历史 receipt 夹具仍保留原 revision 2、观察及 child run。B 的独立 worker 完成记录存在。 |

原审核反例**原文件和断言不变**，当前代码下 HTTP 返回 409、revision 不推进。正式 r2 用例逐次比较 A 的 revision/status、step、observation 数、run/job/event ID、成功幂等记录数、progress/checkpoint 引用及 publication hash：新 key、重复新 key 均为 409，前后相同。隔离前已成功的同 key 重放为 409；本轮审核探针进一步逐字段比较原 `idempotency_keys` 行和原 observation 行，二者未删除或改写，历史 GET 仍可读。GET diagnosis 返回原步骤，GET run 明确暴露 `CHECKPOINT_INCONSISTENT/manual_review`。这区分了历史可读与当前可继续使用。

同库 B 由独立进程 worker 完成自己的任务，正式用例断言只发布一套结果；A 的异常和原 publication 不被改成成功。正常未隔离观察和同 key 重放、合法更正、旧 epoch 相邻测试均通过。本轮额外 HTTP 探针确认隔离 A 的 `conclude` 返回 409 `ACTIVE_STEP` 且业务快照不变；正式用例确认 `activate` 是只读、公开 `resume` 返回 409，二者没有入队。只读 SQL 是对断言的补充，不用不同夹具的汇总行数冒充单一病例前后因果。

## 限定结论与未验证项

本轮没有发现 RECOVERY-001 残留的重复观察、越过人工隔离、跨病例阻断或公开续接入队；因此该项可关闭。建议接受的范围限于**合成且精确适配资料下**，WP-12 观察原子提交、保守区域收尾、更正与持久图恢复的核心技术链路；依据包括原整包审核中 A410、A412—A414 的限定通过证据、[ISSUE-001 定点复核](wp-12-review-r2.md)对 A411 的关闭结论，以及本轮 RECOVERY-001 复核。最终用户接受仍需另行决定。

注入的同 epoch 不一致不证明生产中自然触发的概率或人工处置流程已完成；生产恢复未验证。真实 DeepSeek→DKVB 当前检查仍未发布，真实资料门槛仍 `NOT_MET`，旧 worker 首次失败、Linux BGE 及其他历史根因未确证；本轮结果不能称为真实维修效果、自动确诊、正式观察前端或 WP-13 报告通过。

本轮只新增本报告与审核证据；未修改实现、STATUS、接受记录、历史报告/证据、旧项目、迁移或 Git index，未付费调用、提交或推送。等待用户决定。
