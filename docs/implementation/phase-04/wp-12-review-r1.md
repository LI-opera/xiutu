# WP-12 最终交付集中审核 r1（2026-09-20）

结论：**CHANGES_REQUIRED**。A410、A412—A414 在隔离合成技术范围内有足够支持；A411 的自动保守收尾与发布事务有通过证据，但公开区域激活入口存在一个可复现的核心故障，当前不能给 WP-12 限定范围 `REVIEW_PASS`。本文仅审核，不是整改或用户接受。

## 基准、范围与证据版本

- 读取了 `STATUS.md`、WP-12 契约、原结果和 A411 整改、WP-11 限定接受记录及 P4 的 A410—A414 清单。适用路径及仓库内未发现 `AGENTS.md`。
- 当前关键源码/测试与整改封存 `evidence/wp-12-remediation-r1/final-r2-source-hashes.json` 的 **10/10 个 SHA-256 相同**；另对观察、更正、区域、发布、checkpoint、迁移和测试共 12 个文件及报告/日志建立本轮只读[基准](evidence/wp-12-review-r1/baseline.json)。没有发现未解释的实现版本差异。Git index SHA-256 为 `C451D6E78B8F29FC818002923A19FB1A888139CED20679AD545F75E9692A9EC6`，与最终自测前后记录一致；仓库本来无 HEAD、存在大量既有暂存/未跟踪交付，本轮未调整 index。
- 执行者最终源码的 `./scripts/test.ps1` 日志：**退出码 0，481 passed、1 条既有 Starlette/anyio 弃用警告**，见 `evidence/wp-12-remediation-r1/full-standard-final.txt`。最终受影响组 **25 passed**，见 `affected-final-clean.txt/xml`。这是执行者旧证据，本轮没有重跑完整入口。
- 早期 472 通过/1 失败、479 通过、夹具导入/段落/退休区错误，以及 25 失败、23 通过/2 失败的旧 epoch 对账窗口均保留在各自原日志。它们属于不同源码或夹具状态，不能与 481 项累加。最终修正后 25 项与 481 项分别引用。
- 本轮新建 `xiutu_test_wp12_review_*` 隔离 PostgreSQL 库，迁移至 `0011_area_closure` 并执行 graph checkpoint setup；仅使用合成资料、原 WP-10 门禁和无付费模型配置。本轮未操作 5180/5196、旧项目、原资料包、历史证据或真实费用账本。

## A410—A414

| 项目 | 审核结论 | 代码与证据 |
| --- | --- | --- |
| **A410 观察事务** | **PASS（合成技术范围）** | `ObservationService.submit` 先持有 owner/case/step/run 锁，校验 revision、epoch、choice、工况、受审规格及 Decimal 比较，再于同一 UOW 写观察、完成步骤、revision、下一个 run/job、事件和幂等 202。跨 owner、错 step、异 key 重答、旧 revision 被拒；公开 `/diagnosis/resume` 固定返回 `OBSERVATION_SUBMIT_REQUIRED`。本轮选中幂等/并发用例通过；输入错误与事务回滚其余覆盖引用最终 481 项和 25 项。 |
| **A411 区域摘要与切换** | **FAIL** | `close_before_next_area` 逐步核对有效观察、来源、比较、冲突和其他活跃任务；跨区发布或明确 `conclude_area(unknown)` 的卡、事件、区域状态和 publication 在一笔 fenced 事务，旧测试覆盖重放/崩溃后不重复。`unavailable`、失效来源、同组冲突及无审计 retired 均不收尾，unknown 不等于确诊。**但公开 `activate` 的必要路径实测 500，且缺少旧活跃区域已收尾的检查；见 ISSUE-001。** 自动 `area_close` 入队 pending 的测试只证明入队，不能代替公开激活入口的验证。 |
| **A412 事实更正与隔离** | **PASS（无 WP-13 报告状态）** | 更正先拒绝活跃 run，追加 `supersedes_id` 与原因，0010 触发器阻止旧观察 UPDATE/DELETE；case epoch+1、旧步骤/区域卡失效并入队新 run 同事务。发布与 checkpoint 重新核对 epoch。最终 `reconcile_wait` 只跳过旧 epoch；本轮针对**同 epoch**损坏 publication 的反例仍得到 `CHECKPOINT_INCONSISTENT`，退出码 0。WP-13 报告尚不存在，不能声称报告失效链已验收。 |
| **A413 两组观察的后续差异** | **PASS（确定性夹具）** | 本轮运行 `test_two_saved_choices_drive_distinct_source_backed_checks` 通过：同一合成问题的两种已存观察对应不同来源支持的下一检查动作，并非仅改文字。候选由测试夹具确定，**不证明 DeepSeek 自主决策**。 |
| **A414 未知与冲突** | **PASS（保守门禁）** | `unavailable` 保存 `checked=false`，不当作正常；未检查和 `need_input` 不使区域完成。最终 25 项含失效来源、未回答/无法测量和同规格同工况 within/out_of_range 冲突阻断，旧事实不能借 epoch 跳过当前授权。由于 ISSUE-001，整体 WP-12 仍不得接受。 |

## 本轮命令与原始结果

- 隔离库准备：`docker exec xiutu-v5-postgres-1 psql -U xiutu -d postgres ... CREATE DATABASE xiutu_test_wp12_review_*`；`python -B -m alembic upgrade head`、`python -B scripts/setup_graph_checkpoint.py`：均退出 **0**。库名、迁移及 checkpoint 输出分别见 `evidence/wp-12-review-r1/db-name.txt`、`migration.txt`、`checkpoint.txt`；没有清理既有库或卷。
- 定点命令：`.venv/Scripts/python.exe -B -m pytest -p no:cacheprovider <选中4项 test_wp12_turns + 4个 test_wp12_area_closure 实例 + 本轮反例> -q --tb=short --basetemp <新目录> --junitxml ...`。首次 **退出 1：8 passed、1 个审核夹具 setup error**（本轮脚本未导入 `docrig`），见 `targeted.txt/xml`。只修审核夹具；随后单项仍因本轮脚本未显式加载根 `database_url` 夹具而 **退出 1、1 setup error**，见 `counterexample.txt/xml`。两次均未进入被审业务断言，不记作产品失败。
- 正确加载审核夹具后，只运行 `test_unfinished_area_cannot_be_bypassed_by_explicit_activation`：**退出 1，1 个业务断言失败**；期望拒绝未完成旧区域的 409，实际 HTTP **500 INTERNAL_ERROR**，见 `counterexample-final.txt/xml` 与该次隔离 API traceback。数据库事后只读核对为 `revision=2, case=needs_review, pending area=pending, area card=0, area_activation run=0`，见 `activation-db-state.txt`；此次 500 未产生假卡或新 run。
- 单独运行 `test_same_epoch_broken_publication_is_not_silently_skipped`：**退出 0，1 passed**，见 `same-epoch.txt/xml`。它在隔离库故障注入同 epoch 的错误 workflow ID，确认仍抛 `CHECKPOINT_INCONSISTENT`，没有把真实不一致误当成可跳过的旧 epoch。
- 本轮没有因一个核心反例失败而重复 481 项、前端或旧模型评测，也没有现场修实现。审核脚本仅存于本轮 evidence 目录；上述 setup 失败与业务失败均原样保留。

## 必须整改

**ISSUE-001（P1，A411 区域激活入口不可用且收尾门禁不完整）**：`backend/app/services/area_service.py:102` 对 `runs.c.created_at` 排序，但 `backend/app/infrastructure/orm.py:149-185` 的 runs 表无此字段。触发：在隔离合成会话中回答当前步骤为 `unavailable`，取消其后续 run，使旧区域保持 active、case 为 needs_review；准备另一 pending 区域，调用 `POST /api/v2/cases/{case}/diagnosis/areas/{pending}/activate`。实际返回 500，API traceback 为 `AttributeError: created_at`；没有产生新 run。即使只修排序，`area_service.py:86-105` 仍只检查待答 step 和 `case.status=analyzing`，未证明旧活跃区域真的完成；在上述状态下可能直接越过待补区域。后者是**代码审查推断的后续风险**，当前 500 使其尚未动态发生。

最小修复：用实际存在的持久字段/关系确定本 case 的最新合法 workflow；在激活 pending 区域前与自动收尾使用一致的当前区域完成/待补判断，并检查活动 run，未完成返回明确 409，不造新 run 或覆盖旧待答步骤。定点复核需在真实 PostgreSQL/API 下同时证明：上述 unavailable/冲突/缺来源旧区域不能激活 pending；真正收尾后的合法 pending 可激活并生成一项有据检查；重放不重复任务，旧区域步骤和卡保持可追溯。无需扩建自动确诊或 WP-13。

## 非阻断边界、流程披露与停止点

- 当前自动卡仅为 `unknown`，没有可信 retired 合并入口；无审计 retirement 一律拒绝。正式观察前端、WP-13 报告、真实维修效果不在本包通过范围。真实资料仍 `NOT_MET`，DKVB 精确适配不足且真实 DeepSeek→DKVB 两次 turn 未发布当前检查；Linux BGE、旧 worker 首发及历史启动/SSE/Compose 未确认原因保留。
- 本审核任务所在同一任务链此前参与 WP-12 实施与整改。这里是角色切换的集中审核，**不声称不同任务独立审核**。
- 建议只整改 ISSUE-001 并做上述定点复核；A410、A412—A414 未发现必须整改项，不重开这些部分。WP-12 继续 `IMPLEMENTED_NOT_ACCEPTED`，本报告不改变 STATUS 或接受记录，不进入 WP-13。
