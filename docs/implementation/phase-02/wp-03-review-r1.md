# WP-03 r1审核报告

**结论：REVIEW_PASS（仅WP-03后台任务范围）。建议用户接受本包已验证交付，保留E10与资料门槛；本报告不代替用户接受。**

**角色披露：本任务参与了WP-03实现，本轮切换为审核角色；不是不同任务独立审核。** 本轮重新运行测试、演示及补充探针，结果独立生成，但不以此冒充审核角色独立性。未修改实现、STATUS、接受记录、旧项目或Git index，未进入WP-04。

审核开始：2026-09-18T12:36:18.093813+08:00；报告记录：2026-09-18T12:42:08.552456+08:00。

## 1. 依据、基准和改动范围

读取适用AGENTS（项目、上级及相关目录未发现）、wp-03-result/contract、wp-02-acceptance、P2实施/验收清单、总指南第6/7节及WP-03。契约本身作为被审对象，未把其自述或执行者统计直接转写结论。

- Git根E:/Work/xiutu-v5，main，无HEAD；root/branch/head/status/cached/unstaged.txt保存本轮开始状态，HEAD退出128。Git仅命令级safe.directory，不add/commit/reset/push。
- 原交付delivery-hashes的922项、封存报告/manifest/index均匹配；223份原进程证据逐项哈希匹配。原baseline与changes.json比较仅声明的11份既有文件有变化，新增内容属于本包代码/测试/文档/证据。未发现越包实现。
- 本轮baseline.json固定924项Git可见交付及历史工件；结束protection-final.json确认全部未变。旧项目63项、0001/0002、db_target、WP-00/01/02接受记录和全部历史报告/证据保持不变。Git index SHA256仍为`c451d6e78b8f29fc818002923a19fb1a888139ced20679ad545f75e9692a9ec6`。
- 0003只新增runs.owner_id及领取/事件索引；case_service/DTO衔接真实active_run，main/OpenAPI挂载四个run接口，health统一0003。未复审未变化的WP-02设计；只核对哈希并执行用户要求完整入口所覆盖的受影响回归。

## 2. 本轮实际运行与引用边界

只读Docker检查确认Server29.4.0、xiutu-v5/postgres标签、running、127.0.0.1:5433以及镜像sha256:00ba258a66dac104fd5171074a0084462a64a1369d8513f3d0a634e2f24d15bc。环境与当前源码确认见environment-commands.json、loaded-source.txt。

复用既有工具环境和隔离库xiutu_test_wp03_9946ac2ee08747d9acd2bc62；所有新增任务使用本轮UUID owner/key。完整入口自身迁移测试新建xiutu_test_wp02mig_6c707562e64947bfae14d0a7，仅该新库演练迁移。未改实际密码、重建容器、删除库/卷或停止未知进程。没有建立两套venv、前端重建或性能压测。

实际argv、cwd、起止时间、退出码记录于environment-commands.json及full/demo/targeted-review-command.json。cwd均E:/Work/xiutu-v5；输出全部是本轮新目录。审核运行器来自原run-check.py复制件，按__file__定位新输出；未执行会覆盖历史证据的原脚本。PYTHONPATH与导入路径断言确认当前backend源码。

| 本轮命令 | 退出码 | 实际结果 |
| --- | --- | --- |
| docker version / 定向inspect / 当前源码导入断言 | 0 | 当前服务与源码匹配 |
| powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/test.ps1 | 0 | **147 passed，0 failed/errors/skipped，89.08秒，1条既有警告** |
| 复用Python -B evidence/wp-03-review-r1/targeted_review.py | 0 | 两种并发retry、Worker断锁停止路径、207条跨批SSE/资源检查通过 |
| 复用Python -B scripts/demo_tasks.py | 0 | 真HTTP查询→取消→SSE→cancelled，事件ID464—467 |

full.xml和test-statistics.json独立解析统计；完整入口只运行一次，包括新增断锁用例，未转抄执行者146项结果。1条警告为既有Starlette/AnyIO BlockingPortal弃用提示。没有把补充脚本4项检查伪计为pytest新增通过数。

本轮full.txt、JUnit和process-traces/保存独立worker/API PID、屏障文件、时序及日志，来源哈希见process-traces.json。检查测试实际代码：双worker由同gate放行，赢家在after_claim停住，另一个明确idle；事件顺序用独立连接并观察pg_stat_activity Lock等待，不是只启动线程便宣称竞争成功。前后提交中断仅终止测试自己启动的worker。

原WP-02接受/旧迁移/错误分类作为未变化前置引用，原WP-03证据只用于来源与基准核对；本轮D204—D206结论主要基于当前源码审查、本轮完整入口和补充实测。

## 3. 核心审核结论

| 对象 | 结论 | 依据及边界 |
| --- | --- | --- |
| 入队/owner | PASS | RunService同一UnitOfWork写幂等占位、run/job/queued事件；异常回滚。case先查并锁cases.owner_id、核对revision；无case持久owner_id，历史NULL归属统一404。HTTP不暴露通用入队伪诊断接口 |
| D204领取互斥 | PASS | JobStore.claim先拿稳定SHA256派生case/run会话锁，再短事务SKIP LOCKED锁job、run，复核due并增加attempt/token；失竞争物理连接finally关闭且不增加attempt。本轮两进程竞争只有一个started/succeeded |
| D205租约/锁/fencing | PASS | NullPool专用连接整个attempt保留；独立心跳线程不被no_op等待阻塞。_valid核对lost/closed/invalidated、backend PID、worker/token/有效lease及run状态；不静默重连后发布。旧锁存活时过期lease不被绕过；释放后token递增，旧token拒绝；提交前后崩溃恢复通过 |
| 取消与死亡回收 | PASS | job→run行锁串行裁决，状态与事件同事务；queued直接取消、running先请求；迟到finish在cancel_requested时只能取消。重复key重放、异key终态200、不重复事件；case revision不变。死亡worker失锁/过期后回收取消通过 |
| 自动/显式预算 | PASS | 三次总attempt，2/8秒持久available_at及抖动；30秒档不使用的解释符合三次总预算。明确瞬态自动重试，永久/未知/未实现不重试；retry继承累计attempt及turn/workflow、保留parent关联。并发retry下旧job/run行锁及superseded阻止分叉 |
| D206 SSE/事件 | PASS | append_event在分配identity前锁run至提交；同run写入提交顺序可核对，不把全局identity当全局提交时序。游标校验run归属；循环短查询无历史/实时切换窗口。真实重连、终态、15秒注释、注销/过期关闭、跨owner404通过；多批/资源检查见下 |
| active_run/迁移/health | PASS | case get/list真实查询活跃摘要；历史创建幂等快照不回写。0003冻结迁移只加owner及索引、downgrade仅移除本包对象；full含0002↔0003健康与旧版本拒绝、外部sentinel保护。0001/0002未变 |
| 处理器/接口边界 | PASS | 仅no_op等待测试处理器成功；ingest/未知明确失败。没有start/reassess假诊断、资料导入或后续Agent；GET/SSE鉴权、写接口Origin/CSRF/幂等沿用既有规则 |

### 证据不足部分的本轮补查

1. **并发retry防分叉，分别覆盖case与无case。** 在父job上持有真实行锁，两线程独立事务同时请求不同幂等key；观察到两条数据库Lock等待后释放屏障。两组均得到202/409，各只有1个parent关联子run、继承attempt=1，父run为superseded。原job、input_payload、parent关系、事件未删除，历史可追溯。
2. **停止信号后的finish。** 审核观察包装仅捕获实际claim返回连接，handler关闭该attempt自己创建的物理socket，未替换验证/发布逻辑。实际Worker心跳检测断锁并置stopped；handler返回后Worker仍进入finish，但_valid拒绝，run无成功事件，连接最终关闭。证明停止信号不会因no_op提前返回而被当作成功。原完整测试还验证之后新token恢复。
3. **207条事件、多批终态与资源。** 仅隔离数据追加review.synthetic事件用于批量夹具（非生产worker业务事件）；实际Uvicorn HTTP读取三批，ID与DB完整序列严格一致、无重复遗漏，终态关闭。审核启动器增加只读pool计数观察路由，未改产品文件或数据库行为；SSE等待及客户端断连后checkedout均为0。原完整入口另实测会话17秒到期、15秒注释和注销关闭。

补充脚本、结果及API日志分别为targeted_review.py、targeted-results.json、targeted-review.txt和review-api.log。报告区分审核夹具事件/观察路由与真实交付接口，不将其宣称产品功能。

## A. 必须整改

**无。** 本轮未发现核心功能、权限、数据一致性或明确契约失败；因此没有必须整改ISSUE，也不因下述建议拒绝本包。未现场修改实现或扩大后续工作包。

## B. 非阻断建议

- **B01：队列规模与公平性。** job_store.py候选查询限制100、未拿锁即跳过；本轮验证本包故障场景，不做规模压测。后续实际并发增长时评估候选窗口、轮询和积压公平性，再按证据决定分页/调度策略；不将未测大规模性能当作当前核心失败。
- **B02：运行观测与清理。** 后续部署阶段补充任务滞留/尝试耗尽告警、退出监控与事件保留策略。当前不自动清理事件符合契约，不要求本包现场扩展。

## 4. 保护、剩余项与接受建议

protection-final.json确认本轮924项交付/历史文件开始结束一致，原223份进程证据及旧63项保护不变；Git index未变。实际数据库密码在本轮证据扫描零匹配；审核HTTP探针检查token不在SSE响应/服务日志。只在已隔离测试库新增合成数据，未读取旧.env、改实际凭据或付费调用。没有把全部部署日志安全/生产恢复作为本包已验证保证。

**建议接受WP-03限定后台任务交付。** 技术结论为REVIEW_PASS，仍由用户决定接受；当前STATUS仍IMPLEMENTED_NOT_ACCEPTED。本任务参与实现的流程限制已明确披露，不声称独立审核，也不默认要求重做整包。

E10仍NOT_VERIFIED，模型、范围、预算另行授权，最迟WP-09；资料门槛仍NOT_MET，来源/许可、精确车型/发动机适配、规格、电路、拆装/复核章节及缺图最迟WP-10/真实效果验收前补齐。本结论不代表资料检索、正式诊断、生产恢复或真实维修效果完成。

**停止：仅新增本报告与审核证据，未修改STATUS或生成用户接受记录，未进入WP-04。**
