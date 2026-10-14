# WP-07 r1 集中审核报告

结论：**CHANGES_REQUIRED**。完成时间：2026-09-18T18:11:49.090647+08:00。当前不建议接受WP-07；须先定点修复ISSUE-001和ISSUE-002。性能、监控和清理建议不阻断。本轮不是重新实施，不接受整个P3，不授权WP-08。

**流程披露：本任务参与过WP-07实施；本轮在同一任务切换为审核角色，不属于不同任务/窗口的独立审核。** 本轮只读取交付、运行隔离验证并新增审核证据/报告，没有现场修业务代码，没有修改STATUS或接受记录。

## 1. 依据与审核基准

读取适用AGENTS检查（E:/、E:/Work及项目树未发现适用文件）、STATUS、WP06接受、WP07契约/结果/工具API、依赖矩阵、旧项目P3说明/验收清单与总指南9.1、预算/重放及WP07条款。契约自身也是被审对象，不将执行者自测总结直接转为审核结论。

- delivery-hashes.json **2498项全部匹配**，清单本身与protection-final/final-check封存一致；2099项历史保护文件匹配。
- 执行者完整回归full-code-hashes **119项**：仅tests/README.md为报告说明的后续文档差异；其余实现、测试代码、迁移、依赖未变。STATUS/CHANGELOG/报告等最终文档匹配交付清单。没有完整260项后未验证实现变更。
- 本轮开始固定**2501项**交付/原证据文件（包括原封存文件），结束再次全部一致；baseline.json与本轮protection-final.json可复核。
- Git根E:/Work/xiutu-v5，main，无HEAD（verify退出128为无提交的预期情况）；暂存/未暂存diff及未跟踪列表见baseline.json/git-final.json。只用命令级safe.directory和--no-optional-locks；没有add/commit/reset/push。
- Git index SHA256 `c451d6e78b8f29fc818002923a19fb1a888139ced20679ad545f75e9692a9ec6`，前后相同；旧项目63项、0001—0007迁移、WP00—06接受记录、历史报告与执行证据均未改变。审核新增工件独立于该基准。
- 本轮实际导入当前backend/app/tools/executor.py，SHA256 `05a27683cd78ad823dbe6eaa3c0d8ac74180f9dfe703eadf2445c9a4d2ea35a2`，见import-verification.json。

## 2. 本轮实际运行与证据区分

复用已确认的xiutu-v5-postgres-1（project=xiutu-v5/service=postgres、running、127.0.0.1:5433，镜像标签digest见environment.txt）；未重建/删除容器或卷。新审核库`xiutu_test_wp07r1_8f69b13326134f139695`，从空库迁移head；每fixture新owner、审核专用临时目录/存储。只结束本轮子进程和清理本轮probe schema，不读取旧.env，不改变实际密码或旧8014服务。

| 本轮运行 | 结果 | 原始证据 |
| --- | --- | --- |
| 标准完整scripts/test.ps1，恰好一次 | **260 passed，0 failed/errors/skipped，1 warning，exit0，578.64秒** | full.json/txt/xml |
| 代码审查后补充11项定点用例，恰好一次 | **6 passed、5 failed、0 errors/skipped，exit1，101.13秒** | audit-targeted.json/txt/xml、test_audit_tools.py |

执行者原260通过/CLI1通过属于旧证据，未转抄为本轮结果。当前完整入口已经实际运行五工具HTTP准备/E5/独立worker/LangChain演示，不再重复CLI同等链路。两轮测试不合并为独立覆盖数。完整回归通过不消除新增反例证明的权限与重放缺陷。

本轮保留同一条Starlette/AnyIO BlockingPortal弃用警告。SSE心跳/认证过期本轮通过，首次历史超时未复现，**首次根因仍未确认**，没有顺带修复。M306—M311正式业务MCP不在本包；完整入口中的旧echo探针只算基础回归。

所有cwd=E:/Work/xiutu-v5，命令、起止、退出码如下；连接凭据只在环境中静默注入，不进入命令日志：

| 标签 | 实际命令 | exit | 起止 |
| --- | --- | --- | --- |
| environment | `docker inspect xiutu-v5-postgres-1 --format {{json .Config.Labels}} {{json .State.Status}} {{json .NetworkSettings.Ports}}` | 0 | 2026-09-18T17:55:36.817992+08:00 — 2026-09-18T17:55:36.982331+08:00 |
| create | `E:\Work\xiutu-v5\.venv\Scripts\python.exe -B scripts/probes/prepare_database.py --name xiutu_test_wp07r1_8f69b13326134f139695` | 0 | 2026-09-18T17:55:37.063176+08:00 — 2026-09-18T17:55:37.768470+08:00 |
| migrate | `E:\Work\xiutu-v5\.venv\Scripts\python.exe -B -m alembic upgrade head` | 0 | 2026-09-18T17:55:37.843850+08:00 — 2026-09-18T17:55:38.953080+08:00 |
| full | `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/test.ps1` | 0 | 2026-09-18T17:55:39.035733+08:00 — 2026-09-18T18:05:20.508077+08:00 |
| audit-targeted | `E:\Work\xiutu-v5\.venv\Scripts\python.exe -B -m pytest docs/implementation/phase-03/evidence/wp-07-review-r1/test_audit_tools.py -q -s -p no:cacheprovider --basetemp E:/Work/xiutu-v5/.test-runs/wp07-review-targeted-78dfc824 --junitxml=E:/Work/xiutu-v5/docs/implementation/phase-03/evidence/wp-07-review-r1/audit-targeted.xml` | 1 | 2026-09-18T18:05:41.687289+08:00 — 2026-09-18T18:07:24.607133+08:00 |

完整入口临时目录：`E:\Work\xiutu-v5\.test-runs\run-bbb037c4bcb34496a1205ea239024037`；定点目录：`E:\Work\xiutu-v5\.test-runs\wp07-review-targeted-78dfc824`。224份本轮子进程日志另存child-logs，映射与SHA见child-log-manifest.json。早期执行者失败原样保留；本轮5个断言失败也原样保留，没有改断言或循环重跑。

## 3. M301—M305逐项结论

| 项 | 结论 | 审查与实际证据 |
| --- | --- | --- |
| M301 五工具与schema/服务 | **FAIL** | 五工具正常真实调用、Pydantic extra/限额、LangChain invoke/ToolCall/ToolMessage、DB观察revision/supersedes/area和空结果已通过本轮完整入口；但合法工况键在规格/比较重放时丢失或触发INTERNAL_ERROR，ISSUE-001。schema导出保留实际args_schema，未声称远程模型strict或MCP完成 |
| M302 上下文与授权 | **FAIL** | 正常入口capability/hash、owner/case/manifest/profile/revision/allowlist及scope冲突、注销、源撤销均有检查；未知字段补充只收窄的额外用例通过。然而模型参数中的恢复标记可以在重放中读取另一owner且不在manifest的chunk；旧比较复核状态也未检查，见两项ISSUE |
| M303 空/错误/限额 | **PASS（错误分类与普通失败路径）** | 本轮完整入口验证空、配置缺失不fallback、拒绝、超时、取消、预算和输出schema错误；额外真实DB超大观察返回RESULT_TOO_LARGE且扣1次。预留前工具/allowlist/上下文/结构参数拒绝不写tool_calls，业务执行后的scope等拒绝消耗尝试；与契约具体阶段一致。常规错误/审计无cookie/capability泄漏；不包含对ISSUE-001越权重放的豁免 |
| M304 比较与事务 | **FAIL（旧比较有效性重放）** | 调用WP06完整service、精确边界一致、原HTTP外层UOW回归通过；同key/并发只有1比较。取消两个固定顺序、后续SQL错误、deadline及receipt提交保护通过。但重新批准规格后旧比较仍需复核，工具把其作为无失效标记成功重放，ISSUE-002 |
| M305 预算/恢复/重放 | **FAIL（响应恢复完整性）** | 持久原子预算、最后名额真实锁等待、搜索双预算/受限重试、超时计数、冲突/进行中、预留进程退出uncertain、新进程成功receipt重放均通过；原预算不清零，不盲重做。合法结果摘要恢复失败/篡改响应破坏同一逻辑调用重放契约，ISSUE-001；不是要求重构已明示的非实时deadline边界 |

### 已补齐的事务顺序与恢复证据

- `cancel-order-cancel_first.json`：在measurement_comparisons INSERT后的真实PG触发器上等待advisory锁；观察等待后cancel先提交，再放行。结果TOOL_CANCELLED、receipt failed、比较0、幂等0、used=1。
- `cancel-order-success_first.json`：成功receipt UPDATE后持有call行锁，再在触发器等待；cancel实际等待该发布事务。释放后成功先提交、cancel返回false；receipt succeeded、比较1、幂等1、used=1。两段wait PID/DB时间可核对，不靠随机线程启动判定顺序。
- `later-sql-error.json`：成功receipt后续真实SQL触发23514，比较/幂等/成功receipt整体回滚；超期同key转uncertain，不重做，used=1。
- `lost-commit-ack.json`：在真实数据库commit完成后注入“确认丢失”异常，首次返回CALL_UNCERTAIN；另一个实际Python进程重建认证/可信context，读取持久成功receipt，返回同一比较，used=1/比较1/幂等1。它是受控确认丢失模拟，不声称真的拔断了网络，也不是生产恢复保证。
- 本轮完整入口已有预留子进程退出后uncertain、比较超时/取消/后续receipt SQL延迟回滚与旧WP04租约三窗口，无需重复同等证明用例。

## 4. 必须整改

### ISSUE-001 — P1：重放内部标记与业务字段混用，导致跨owner读取及合法结果损坏

对应M301/M302/M305。位置：`backend/app/tools/manual_tools.py:201` summarize，`:212` hydrate（尤其`:218`按前缀删键、`:220`起恢复chunk）；调用入口`backend/app/tools/executor.py:89`成功receipt重放分支。

**触发和本轮复现：**

1. 使用真实HTTP为owner A建立已批准合成规格；owner B另上传并由真实worker解析合成Markdown。A普通GET该版本为404，A工具get_evidence_context拒绝该版本（CORPUS_NOT_ALLOWED）。B文档不在A冻结manifest，也未审核/索引。
2. 审核者已知合成B chunk的UUID、version UUID和text_hash（这些定位元数据不构成授权），将其作为A合法compare_measurement的conditions字符串字段，附`_restore_text="true"`。首次比较成功；同逻辑key重放时，hydrate把模型提供的标记当作内部引用，只按chunk/version/hash查询，未重新校验owner/manifest/资格。
3. 第二次响应的`data.input.conditions.text`包含B的合成正文。`marker-cross-owner.json`明确记录`foreign_text_in_replay=true`。这不是只读数据库审计直接取回的返回值，而是实际ToolExecutor重放输出。
4. 不含攻击意图的合法工况键`text`、`payload`也被summarize删除，重放触发INTERNAL_ERROR；`_restore_note`被静默删除且仍ok=true。规格查询重放有同样问题。三个`condition-key-*.json`及对应失败JUnit证明首响应/重放不一致；比较仍只入库一次，但响应无法无损重放。

**影响：** 持有合法A上下文并知晓B定位元数据的调用者可借模型参数绕过资料权限/冻结范围。正常动态工况键也会破坏幂等响应完整性。UUID/hash不能代替owner与corpus授权。

**最小修复要求：** 按工具输出类型和受信路径保存/恢复引用，内部receipt元数据与任意用户字典严格分离；不要在conditions等任意嵌套数据里解释`_restore_*`或删`text/payload`。恢复chunk必须复用当前owner、manifest、version/index/epoch/资格门禁。正常业务键应无损保存，不以笼统禁用这些键掩盖问题。既有有问题receipt要安全拒绝或从已授权不可变记录恢复，不能默默扩大授权。

**复核：** 原跨owner反例不得返回B正文；普通上下文仍拒绝。text/payload/_restore_note工况及规格首次/重放一致，比较/预算各不重复；正常chunk和观察payload摘要恢复仍有效，注销/撤销/跨corpus仍拒绝。保留本轮失败证据。

### ISSUE-002 — P2：规格重新批准后，重放忽略旧比较的需复核状态

对应M302/M304。位置：`backend/app/tools/executor.py:47` check_use及`:89`重放分支；`backend/app/tools/manual_tools.py:45` approved只看当前规格/证据。应衔接的既有语义见`backend/app/services/evidence_service.py:372` get_comparison，`:380`会检查comparison自身needs_review。

**触发和本轮复现：** 创建有效比较→人工撤销其规格（原比较被标needs_review）→同key重放被拒绝→重新批准同规格→实际GET `/api/v2/measurement-comparisons/{id}`仍返回`current_validity.valid=false`和`spec_or_result_requires_review`，但工具同key重放返回`ok=true/outcome=within_range`，没有当前失效标记。另用新key产生的当前比较正常成功，说明问题是旧结果门禁遗漏，而非应禁止所有新比较。见`comparison-review-history.json`与失败用例。

**影响：** 用户或后续Agent收到看似当前有效的旧比较，绕过WP06保留的复核要求。历史内容可读不等于现时可用；重新批准不能静默消除旧复核状态。

**最小修复要求：** 重放时按保存comparison_id复用WP06比较读取/有效性门禁，同时校验所属case/spec与当前授权。旧结果需复核时明确拒绝新使用，或以严格输出契约清晰标记其不可授权状态；不得清除数据库复核标记、重做旧逻辑调用或新增重复比较。新key的新合法比较仍允许。

**复核：** 按相同撤销/重新批准顺序，旧同key不能获得无失效说明的within_range成功；GET历史仍可读且invalid，新key可成功，次数/比较/幂等数据不重复。正常未撤销重放和首次比较继续通过。

## 5. 非阻断建议与未验证边界

- owner粗锁、观察/审计查询索引、大集合性能、监控/清理、uncertain运维处置，作为待办；没有本轮阻断证据，不要求在本次整改扩建框架。
- 观察当前只有最小真实只读存储。生产暂无写入，area/step尚无正式实体；后续写入接入须重验revision/supersedes/并发，不在本轮增加API。
- deadline从成功预留开始，入口锁等待不算处理期限；同步CPU推理不保证硬抢占。已验证过期不能发布成功，不把上述明确非实时限制列为必须重构。
- 未重建第二环境、未重跑未变前端或模型选型/检索留出评测。未验证远程模型strict兼容、业务MCP、Agent turn、生产故障恢复和维修效果。
- E10 **NOT_VERIFIED**：另行授权后最迟WP-09；真实资料门槛 **NOT_MET**：最迟WP-10/真实效果验收前。合成作者数据不是真实维修标准；within_range不等于部件正常。SSE首次根因未确认及同任务审核历史限制保留。

## 6. 结论与下一步最小范围

当前结论**CHANGES_REQUIRED**，不建议接受WP-07。仅需围绕两个重放问题整改并定点验证，保留本轮260项当前完整回归及正向事务证据；除非改动产生新影响依据，不默认重开整包或其他阶段审核。

本轮未修改实现、STATUS、接受记录、旧项目、历史证据、迁移或Git index，没有提交/推送/付费调用。正式报告与证据封存后停止，由用户决定整改，不进入WP-08。
