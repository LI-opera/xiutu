# WP-04 ISSUE-001 整改 r1

状态：**IMPLEMENTED_NOT_ACCEPTED**。本轮仅整改wp-04-review-r1的ISSUE-001，执行者实现与自测完成，等待该问题及受影响路径的定点复核；不是审核通过或用户接受。未进入WP-05。

## 基准和范围

已读取STATUS、wp-04-contract、wp-04-review-r1、原test_audit_wp04.py、lease-lock-window.json、lease-window-events.json及失败日志，检查job_store、ingest_state与worker。检查E:\、E:\Work、项目/相关子目录，没有适用AGENTS.md。

开始核对原审核基准1135项全部匹配，原审核封存清单45项及报告哈希匹配；没有非预期差异。main，无HEAD（命令退出128）；Git根E:\Work\xiutu-v5。完整暂存、未暂存和未跟踪记录在[evidence/wp-04-remediation-r1](evidence/wp-04-remediation-r1/)的root/branch/head/status/cached/unstaged.txt及baseline.json。本轮保护1182项，包括旧审核报告/证据；旧项目63项另行保护。

Git index开始/结束均c451d6e78b8f29fc818002923a19fb1a888139ced20679ad545f75e9692a9ec6。结束仅下列四项已有文件改变，其他保护文件、历史报告/证据、接受记录、已有迁移、db_target、STATUS及旧项目保持原样，详见protection-final.json与change-manifest.json。

| 修改文件 | 最小改动 |
| --- | --- |
| backend/app/infrastructure/job_store.py:207 | 新增_finish_valid；所有finish分支在全部发布SQL之后进行最后校验，保留原lease_until快照 |
| backend/app/infrastructure/ingest_state.py:29 | 取得version行锁后立即调用有效租约复验，再写chunks/版本 |
| tests/integration/test_document_ingest.py:578 | 新增参数化正式回归：version_lock、chunk_sql、success_event_sql，包含失效回滚与新进程恢复 |
| docs/implementation/phase-02/wp-04-contract.md | 说明最终授权判定点、原截止值、事务回滚及COMMIT边界 |

没有修改worker：既有Worker.once捕获LeaseLost、等待自身心跳退出、关闭专用连接的路径已经满足回滚后的释放/恢复要求。没有改原审核反例、延长租约、放宽断言或添加循环重试。

## 根因与修复机制

原finish在取得job/run行锁后只校验一次，之后publish等待version行锁，且后续chunk/version/事件SQL也可能耗时。期间finish持有lease.mutex，心跳不能续租。原实现没有最终时钟检查，所以过期结果仍能提交。原失败样例及历史日志完整保留。

现在有三道检查：

1. 原首次_valid保持不变：同一物理连接、PID、worker/token、有效lease及run状态，获取job/run行锁，保留租约截止快照。
2. version行锁取得后重新_valid，避免等待过期后继续写入。此时原job/run行锁与advisory互斥仍持有，取消优先与预算不变。
3. **全部应用发布SQL完成后、事务COMMIT之前**调用_finish_valid，这是最终发布授权判定点。它在原连接读取当前lease_owner/token、pg_backend_pid及数据库clock_timestamp()；与初始被锁定行的lease_until快照比较。job终态/重试更新清空lease_until并不影响这个快照。

最终检查适用于成功、取消、失败及自动排队重试的共享finish路径。job/run行锁在同一事务内一直持有；本次终态变更不会释放它们，其他worker/心跳也无法改写原授权。取消在首轮run锁上的提交顺序和cancel_requested优先规则保留。没有增加attempt或改变三次总预算。

**回滚边界**：两个新增检查均在with connection.begin()内部。过期、连接失效、PID或worker/token不匹配即抛LeaseLost，SQLAlchemy先回滚整笔事务，再由Worker处理失效尝试。已插入的chunks、version解析摘要、job/run终态及run.succeeded全部回滚；原running/parsing与已过期租约保持为可回收状态。新worker须等原专用连接释放advisory锁，随后按原规则增加attempt/token并重做，不能发布迟到结果。

**时钟及提交限制**：使用clock_timestamp()，不是事务开始时间或客户端时钟。最终查询之后没有其他应用SQL，仅COMMIT；不承诺网络往返/WAL确认完成时间早于租约截止。最终授权到提交期间仍持有物理会话advisory锁及行锁，不存在此间被另一worker接管的窗口。COMMIT通信故障仍可能产生结果不明确，不把此修复写成生产恢复保证。

## 环境与实际运行

复用已确认project=xiutu-v5、service=postgres容器，127.0.0.1:5433映射正确，镜像sha256:00ba258a66dac104fd5171074a0084462a64a1369d8513f3d0a634e2f24d15bc。没有重建/停止服务、改密码、删数据库或卷。

新隔离库：xiutu_test_wp04fix_7e45d8e8ff9148ca934c；PG16.14、vector0.8.2、0004_documents。仅upgrade head准备这个新库，不修改迁移或做升降级演练。凭据静默读取本项目受保护文件，未读取旧.env或打印连接串。复用既有.venv，environment-summary.json确认导入当前backend源码。

所有命令cwd=E:\Work\xiutu-v5；起止时间、完整命令数组、退出码在同名.json，原始输出.txt、JUnit.xml独立保留。run.py拒绝复用已有日志名，REVIEW_EVIDENCE指向新整改目录，因此运行原审核测试也不会覆盖原JSON。

| 记录 | 实际命令/范围 | 退出码与结果 |
| --- | --- | --- |
| docker | docker --context desktop-linux inspect xiutu-v5-postgres-1（归属/端口format） | 0 |
| create | .venv/Scripts/python.exe -B scripts/probes/prepare_database.py --name xiutu_test_wp04fix_7e45d8e8ff9148ca934c | 0 |
| prepare | .venv/Scripts/python.exe -B -m alembic upgrade head | 0 |
| format / lint | uv run --frozen ruff format / check（仅本轮三个Python文件） | 均0 |
| targeted | python -B -m pytest -p no:cacheprovider（下列9个nodeid展开14项）-q -s；新basetemp与正斜杠JUnit参数见targeted.json | **0；14 passed、0 failed/error/skipped，无警告，95.41秒** |
| original-counterexample | 原审核test_audit_wp04.py，独立新basetemp | **1；1 setup error、0 passed/failed/skipped**，临时父目录遗漏，测试正文未执行 |
| original-counterexample-prepared | 补齐本轮父目录，原反例不变，以新basetemp/新XML运行一次 | **0；1 passed、0 failed/error/skipped，无警告，6.38秒** |
| environment | python -B evidence/wp-04-remediation-r1/environment.py（完整路径见environment.json） | 0，当前源码与DB环境 |

14项选择为：test_publication_deadline_after_blocking_sql[3]、test_real_http_versions_review_and_locators、test_ingest_fenced_publication_recovery[4]、test_publish_transaction_rollback_no_partial_chunks、test_two_workers_exact_barrier、test_expired_lease_old_session_lock_and_fencing、test_queued_running_cancel_and_success_order、test_transient_budget_and_explicit_retry、test_disconnected_lock_session_cannot_publish。

定点运行时间14:21:49—14:23:25 +08:00；原反例准备修正后运行14:24:43—14:24:51 +08:00。临时目录分别.test-runs/wp04-fix-targeted-20260918-r1和.test-runs/wp04fix-551e33d3e3da40a3a42b98a6ffa7bdbb/original-prepared。没有循环重跑失败直到通过：唯一再次运行源于执行者漏建父目录，原setup失败日志/XML单独保留，未修改测试与实现来规避它。

## 必要验证 A—D

### A：版本行锁等待过期

正式回归沿用原反例方式：真实HTTP上传，独立worker停在before_finish屏障，另一PG连接持有version行锁。pg_blocking_pids/pg_stat_activity记录worker确实等待transactionid锁，而非仅启动线程。数据库clock_timestamp确认过期0.3秒以上后解锁。

正式用例worker PID30340 / PG1813，阻塞PG1814；deadline=06:21:56.064803 UTC，观察时间06:21:56.369724 UTC。解锁后0 chunks、0 success events、parse_status=parsing，job原lease_until/token/attempt未被终态变更污染。

**原审核反例文件未改并实际再跑通过**：worker PID29676 / PG2215，deadline=06:24:50.336133 UTC、观察时间06:24:50.654280 UTC；解锁后chunks=0、version=parsing、run=running。原失败是chunks=2与succeeded；两份时序分别保留在原审核目录与新整改目录，不覆盖历史。

### B：后续发布SQL阻塞过期

只在本轮隔离库内安装精确绑定本次version/run的测试trigger，通过另一连接的事务级advisory锁阻塞真实SQL；没有修改生产处理器或伪造时钟。每次都观察到PG锁等待，确认DB时钟超过已提交lease_until后才释放。

- chunk_sql：worker PID13552，PG1841等待PG1842；deadline=06:22:04.280921 UTC，观察时间06:22:04.589632 UTC。
- success_event_sql：worker PID27724，PG1861等待PG1862；deadline=06:22:12.898820 UTC，观察时间06:22:13.202998 UTC。这时同一事务已经写过chunks/version、更新job终态并清空lease_until，再阻塞run.succeeded插入，专门证明最终门禁不能依赖已经清空的列。

两个窗口均整体回滚：0 chunks、0成功事件、version未成功、job仍保留原有效期值与attempt/token。trigger在finally移除，专用probe schema清理后其他schema清单未变。三窗口结构化证据见publication-windows.json；对应子进程日志的源路径/哈希见child-log-manifest.json。

### C：新合法worker恢复一次

三个正式用例均在失效进程退出/锁释放后启动新独立worker，attempt和token从1递增到2，成功发布2个合成chunks且仅1个run.succeeded。再次启动worker不增加chunk或成功事件。没有绕过总尝试预算。

### D：受影响回归

正常ingest/真实HTTP/原文与人审流程、queued/running取消与成功竞争、旧锁/旧token、finish前过期、worker中断后恢复、耗尽同步失败、第二chunk真实SQL错误整体回滚、共享no_op正常完成、自动/显式重试预算、断锁禁止重连发布均通过。共享finish最终门禁没有误把正常终态清空的lease_until判为失效。

既有D207/D209和整套169通过证据继续引用wp-04-review-r1，不把本轮14+1说成完整入口重新通过。未重跑前端、第二环境、整包审核或SSE超时专项；正常ingest回归中原有SSE等待沿用既有测试，不改其实现。

## 残余限制与停止点

本轮未发现新的必须修复问题，但上述结论是执行者自测，等待ISSUE-001及受影响路径定点复核。STATUS保持IMPLEMENTED_NOT_ACCEPTED，本轮未修改STATUS或接受记录。

SSE首次超时仍保留“首次根因未确认”，没有顺带整改。性能、监控、清理等既有非阻断待办不扩展。

E10保持NOT_VERIFIED，模型/范围/预算另行授权，最迟WP-09收口。真实资料门槛保持NOT_MET，来源/许可、精确车型/发动机及正式规格、电路、拆装/复核章节和缺图最迟WP-10/真实效果验收前补齐。没有付费模型请求，没有宣称真实维修效果或生产恢复。

原报告、失败证据和审核反例保持原样；没有提交、推送、暂存操作或修改旧项目、迁移。WP-05未开始。完成后停止，交用户安排定点复核。

记录时间：2026-09-18T14:28:09.106798+08:00
