# WP-11 集中只读审核 r1

时间：2026-09-20（Asia/Shanghai）。结论：**限定核心技术范围 REVIEW_PASS**，建议用户仅考虑接受“合成、资料精确适配的持久图发布/等待/恢复技术能力”。**真实 DeepSeek→DKVB 当前检查发布 NOT_VERIFIED**；DKVB 本轮观察到的是符合既有门禁的拒绝，不在通过范围。此报告不是用户接受记录，`STATUS` 中的 WP-11 `BLOCKED` 未修改。

本任务曾参与 WP-11 实施及免费契约对齐；本轮切换审核角色，不能称为由不同任务完成的独立审核。审核没有修改业务实现、测试原文件、迁移、STATUS、接受记录、旧项目或 Git index；没有访问真实模型费用账本、发起付费请求或操作 5180/5196。

## 基准与证据版本

审核前固定的[当前哈希清单](evidence/wp-11-review-r1/baseline.json)覆盖历史 449 项完整入口所封存的 176 个源码/测试/迁移/脚本文件及本轮相关新测试、状态与报告。与[449 项运行前清单](evidence/wp-11-remediation-r1/full-pre-code-hashes.json)相比，现有 `graph.py`、`runner.py`、`model_gateway.py`、`worker.py`、`tests/live/test_wp11_dkvb.py` 五个文件字节不同；其余历史清单文件（含 `0009_graph` 迁移）相同。本轮另有后加的契约对齐、调用上限和诊断测试，不属于历史 449 项集合。仓库没有 HEAD，审核前已有 101 行 Git porcelain 状态；Git index SHA256 始终为 `c451d6e78b8f29fc818002923a19fb1a888139ced20679ad545f75e9692a9ec6`。审核结束再次核对，封存范围内实现、测试、迁移和受保护报告均无变化。

历史执行者[整改报告](wp-11-remediation-r1.md)记录其当时源码的标准入口退出 0、449 passed/1 warning；**不是当前字节版本的全量回归**。后来的[四次上限记录](wp-11-budgeted-live-r1.md)有 39 项免费单元及 4 项集成通过，真实 DKVB turn 经四次请求后 publication=0；[免费契约对齐](wp-11-contract-alignment-r1.md)有首次测试断言错误及后续定点通过。本轮重新验证的结果只见以下新证据，不累加为不重复的功能覆盖数。没有出现要求扩大到约 33 分钟完整入口的定点失败或新的跨模块风险，因此没有重跑完整入口。

本轮新建 `xiutu_test_wp11_review_404fb6fe9830` 隔离 PostgreSQL 库，迁移至 head 并建立独立 checkpoint schema；没有复用用户实例数据库或历史审核库。`run-targeted.ps1` 的数据库创建、`alembic upgrade head`、`setup_graph_checkpoint.py` 和定点 pytest 均退出 0；[运行记录](evidence/wp-11-review-r1/run-404fb6fe98304cd39476a481ff9f9880.json)、[16 项 JUnit](evidence/wp-11-review-r1/targeted.xml)。原始日志在该记录标明的 `.test-runs` 受限目录，不进入公开报告。另运行[持久工具预算脚本](evidence/wp-11-review-r1/run-tool-budget.ps1)，退出 0、[3 个参数化实例通过](evidence/wp-11-review-r1/tool-budget.xml)。测试环境移除付费模型凭据及启用开关，付费请求 0。

## A406—A409

| 验收点 | 本轮判断 | 实际依据与边界 |
| --- | --- | --- |
| A406 幂等发布与提交后 checkpoint 前崩溃 | **PASS（合成技术范围）** | `publish_waiting()` 在原锁连接事务中检查 `(workflow_id, turn_id, node)` 的 publication/hash；同内容先回原响应，异内容报 `PUBLICATION_CONFLICT`，未发布的新内容才检查原 revision。步骤、case/run 状态与 revision、事件和 publication 同事务写入；[graph 定点](evidence/wp-11-review-r1/targeted.xml)验证同键重放没有第二步/事件，异内容拒绝。业务提交后 progress 留在 evaluating 的窗口由 `reconcile_pending()`/`reconcile_wait()`依据已提交 publication 和 step 对账；本轮通用正例另一进程读回原 step/revision、无重复发布。 |
| A407 interrupt、已存观察和跨进程恢复 | **PASS（合成技术范围）** | `DiagnosisGraph.wait()` 只 interrupt；resume API 按 owner、case、当前 step、revision 和未被 supersede 的数据库 observation ID 校验，不接受观察 JSON 充当事实。原图测试验证等待、保存观察及下一步；本轮又用[审核专用跨进程探针](evidence/wp-11-review-r1/test_a407_process_observation.py)在原尝试失租约后由替代 worker 进程读取已存观察、恢复到 revision=2，最终两步状态依次为 completed/waiting_input、publication 恰好两条，见[最终 JUnit](evidence/wp-11-review-r1/a407-final.xml)。WP-12 用户观察提交界面/事务尚不存在；这里的观察由隔离测试 fixture 直接保存。 |
| A408 advisory 锁、租约与 fencing | **PASS（合成技术范围）** | `JobStore.claim()` 在专用 NullPool 物理连接先取稳定 SHA256 派生的会话锁，再以 `FOR UPDATE SKIP LOCKED` 领取；竞争不消耗 attempt。`publish_waiting()` 获得可能阻塞的 owner/case/job/run 锁后核验，所有发布 SQL 后以数据库 `clock_timestamp()` 和原租约截止快照复验；`JobStore.finish()` 在提交前同连接复验 PID/worker/token/期限，失效整笔回滚。checkpoint saver 的 get/put/put_writes 也在同连接、同 token/期限保护下前后复验。[本轮 graph 定点](evidence/wp-11-review-r1/targeted.xml)实际观察 `pg_blocking_pids` 与数据库时钟跨租约，旧尝试无步骤/事件/进度发布、释放旧锁后新 token 恢复；取消后成功发布和旧 checkpoint 均被拒，慢发布 SQL 与 turn 超时回滚。 |
| A409 工具、模型、一次修复与费用累计 | **PASS（离线预算契约）** | runner 按同 workflow/turn 汇总持久 `tool_executions` 的总/搜索额度，`ToolExecutor` 在数据库事务内原子预留并持久记录尝试；本轮[3 个工具预算实例](evidence/wp-11-review-r1/tool-budget.xml)覆盖搜索重试持久扣额和进程重启时 uncertain 调用不盲目重做。模型网关以同一 turn ID 从隔离账本恢复调用次数，WP-11 服务端上限 4、含 429/5xx 重试，第 5 次在预留/发送前拒绝；[5 项调用上限测试](evidence/wp-11-review-r1/targeted.xml)覆盖重启、余额不足与 WP-09 默认行为。一次业务修复在请求前写入 run budget，第二次拒绝；120 秒按进度创建时间累计，发布后另用 DB 时钟复验。**本轮没有读取真实共享账本或验证平台实际账单**，只验证隔离账本及代码门禁。 |

上述独立通用正例使用明确标记的 `tests/fixtures/wp10/extra-synthetic.md`，通过原 `ProposalService.validate()` 后暂存候选、事务发布，得到 `run=waiting_input`、revision=1、一条 publication；另一个 Python 进程执行对账并读回同一个 step ID/revision，见[本轮 JUnit](evidence/wp-11-review-r1/targeted.xml)。补充 A407 探针首次执行**1 个 fixture 装载错误**：审核证据目录未自动加载 `tests/conftest.py` 的 `database_url`，业务测试未开始；原[失败 XML](evidence/wp-11-review-r1/a407.xml)保留。只修正审核探针的 fixture 导入后另用新输出目录运行，退出 0、1 passed，见[最终运行记录](evidence/wp-11-review-r1/a407-final-run.json)。这不是产品缺陷，也没有改写首次失败证据。

## DKVB 条件、未验证项及建议范围

本轮在同一隔离库重建两份白名单合成正文的审核、BGE 索引和冻结 manifest，实际字段/规则摘要见[本轮 DKVB 证据](evidence/wp-11-review-r1/dkvb-scope-summary.json)。model 与 engine_code 为 matched，但 engine_family 及年款上下界均为 unknown；`applicability()` 只给 general reference，未授予步骤所需的精确 matched。原文定位到的行在既有有界位置、工况、动作和选项规则下仍分别得到 `LOCATION_UNCERTAIN`、`CONDITIONS_UNCERTAIN`、`ACTION_SEMANTICS_UNCERTAIN`、`CHOICE_SEMANTICS_UNCERTAIN` 等；候选 `accepted=false`、`needs_input`，**没有发布**。这说明当前元数据/表达不足以通过原门禁，不能据此称原文完全没有维修信息，也不能填造年款/发动机系列或放宽 WP-10 校验。

**NOT_VERIFIED：真实模型→当前检查发布。**先前唯一有界真实 DKVB turn 的脱敏记录显示四次 DeepSeek 请求、一次修复后 `DIAGNOSIS_PROPOSAL_NEEDS_INPUT`、publication=0；本轮没有付费重试。合成正例只证明通用持久图技术链路，不代表 DeepSeek 对 DKVB 资料能给出可发布检查，更不代表真实维修效果。真实资料门槛仍 `NOT_MET`、原截止要求未满足；旧 worker 首次失败根因仍未确证。WP-12 正式观察写入、后续交互、报告和生产恢复不在本次建议接受范围。

本轮未发现 A406—A409 的必须整改项。建议保留历史 worker 异常的受控观测、checkpoint 对账监控和真实资料/精确适配补齐作为后续事项；不得以这些未到期项否决已证明的**限定核心技术范围**，也不得据本报告自行将 WP-11 标记 ACCEPTED 或进入 WP-12。用户可决定是否接受该限定范围；若要求真实 DKVB 发布，则须另行解决资料/适配与现有规则之间的明确缺口，并重新验证该独立目标。
