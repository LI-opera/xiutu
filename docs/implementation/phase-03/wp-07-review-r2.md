# WP-07 r2 ISSUE-001/002 定点复核

结论：**REVIEW_PASS（WP-07限定五业务工具与执行器技术范围）**。ISSUE-001、ISSUE-002均为**RESOLVED**。建议用户在知悉旧receipt兼容限制及下列保留项后接受该限定范围；本报告不代表用户已经接受，也不接受整个P3。

完成时间：2026-09-18T21:13:20.113886+08:00。

**流程披露：本任务曾参与WP-07实施、r1审核及本次整改。本轮在同一任务切换为复核角色，不属于不同任务/窗口的独立审核。新测试库和本轮实际测试不能替代流程独立性。** 本轮只读检查实现、运行隔离验证、新增本报告和审核证据；没有现场修复实现或改STATUS/接受记录。

## 1. 基准、实际差异及保护

已检查项目及上级适用AGENTS（未发现），读取r1审核、r1整改、现行契约、对应原始反例/失败日志/JUnit及封存证据。整改delivery-hashes、protection-final、final-check和报告SHA256全部匹配。开始固定**2932项**当前交付及历史文件，结束再次全部一致；Git index和旧项目63项保护文件也一致。

Git根E:/Work/xiutu-v5，main，无HEAD；verify退出128是无首次提交的预期情况。Git只用命令级safe.directory与--no-optional-locks，未add/commit/reset/push或改全局配置。index SHA256：`c451d6e78b8f29fc818002923a19fb1a888139ced20679ad545f75e9692a9ec6`。完整暂存/未暂存/未跟踪状态见baseline.json和git-final.json。

整改相对r1仅三份实现（manual_tools.py、executor.py、evidence_service.py）、新正式测试和契约/工具说明变化。本轮逐段检查并将声明改动反向还原，与r1原SHA256匹配：

- manual_tools：仅导入与summarize/hydrate变化，execute/approved未变；manual_tools.diff、manual-scope-check.json。
- executor：成功receipt重放分支及summarize参数变化；原预算预留、attempts、重试、deadline、取消、发布SQL事务及最后clock_timestamp检查未额外修改；executor.diff、transaction-scope-check.json。
- WP06 EvidenceService：get_comparison仅增加可选connection及传递给UOW；有效性规则本身未改。外部连接仍由调用者持有/提交，原HTTP路径仍独立UOW；evidence_service.diff。
- 上述以外实现、依赖、0001—0007迁移、STATUS、接受记录和历史证据保持原基准。未重审未变旧工作包。

整改首轮UUID错误已核对原失败XML与test_tool_receipts.initial.py.txt：对应修正只是在审计快照json.dumps增加default=str，不改变业务输入/输出或断言。后续差异另有加强COMPARISON_INVALID/计数断言及3个新增门禁实例，均不是放宽断言。具体差异保存在test-recording-change.diff。

## 2. 本轮实际运行与历史证据分开

当前docker inspect确认xiutu-v5-postgres-1属于compose项目xiutu-v5/service postgres、running、127.0.0.1:5433；标签含原镜像digest，见environment.txt。未重建容器/卷或停止未知服务。

新审核库：`xiutu_test_wp07r2_7ffcf54a77464630af`。先确保.test-runs父目录，再使用全新临时/存储目录与新owner/call key。迁移仅为新库准备，应用现有head；未重做迁移验收。凭据只在本地环境静默加载，未读取旧.env或打印连接串。实际导入当前工作区executor路径及SHA见import-verification.json；不是旧editable副本。

| 证据层次 | 结果与适用范围 |
| --- | --- |
| **本轮targeted** | **37通过，0失败/错误/跳过，exit0，236.53秒**。复用整改定点选择，最终测试文件全部18实例、比较事务/并发/精确边界及SDK契约、原审核事务/恢复4实例；每个只运行一次 |
| **本轮reference-guards** | **2通过，0失败/错误/跳过，exit0，20.53秒**。只补固定引用和原调用关联检查缺口，每个只运行一次 |
| **本轮合计** | 39个不同实例，无重复实例，无警告摘要。未运行完整入口、前端、第二环境或模型评测 |
| 整改者旧证据 | 首轮33通过/1测试记录错误，随后5通过；这是执行者自测，本轮没有直接转抄为复核结果 |
| r1整改前旧证据 | 完整260通过/1已知警告、补充6通过5失败。260仅支持未变部分；**不能说整改后全量260重新通过**，也不与39相加为覆盖总数 |

原审核test_audit_tools.py及replay_process.py逐字复制到本轮目录，内容与原hash相同，仅选择其中事务/恢复用例；其新输出写本轮目录。原五个失败实例在已发布正式回归中按原语义复现，并保留更严格的新断言；没有修改原反例文件。用户数据全为隔离合成fixture，实际HTTP/PG/worker/固定本地E5与LangChain SDK均真实使用，无LLM或付费请求。

全部命令cwd为E:/Work/xiutu-v5；原始命令、时间、退出码、日志与JUnit如下：

| 标签 | 命令 | exit | 起止 |
| --- | --- | --- | --- |
| environment | `docker inspect xiutu-v5-postgres-1 --format {{json .Config.Labels}} {{json .State.Status}} {{json .NetworkSettings.Ports}}` | 0 | 2026-09-18T21:05:04.746620+08:00 — 2026-09-18T21:05:04.909458+08:00 |
| create | `E:\Work\xiutu-v5\.venv\Scripts\python.exe -B scripts/probes/prepare_database.py --name xiutu_test_wp07r2_7ffcf54a77464630af` | 0 | 2026-09-18T21:05:04.982941+08:00 — 2026-09-18T21:05:06.422839+08:00 |
| migrate | `E:\Work\xiutu-v5\.venv\Scripts\python.exe -B -m alembic upgrade head` | 0 | 2026-09-18T21:05:06.502135+08:00 — 2026-09-18T21:05:08.027749+08:00 |
| targeted | `E:\Work\xiutu-v5\.venv\Scripts\python.exe -B -m pytest tests/integration/test_tool_receipts.py tests/integration/test_business_tools.py::test_comparison_publication_is_atomic tests/integration/test_business_tools.py::test_concurrent_comparison_identity tests/integration/test_business_tools.py::test_tool_comparison_matches_wp06 tests/contract/test_tools.py docs/implementation/phase-03/evidence/wp-07-review-r2/test_audit_tools.py::test_committed_receipt_survives_lost_commit_ack docs/implementation/phase-03/evidence/wp-07-review-r2/test_audit_tools.py::test_cancel_commit_orders_with_real_pg_wait docs/implementation/phase-03/evidence/wp-07-review-r2/test_audit_tools.py::test_later_sql_error_rolls_back_comparison_and_receipt -q -p no:cacheprovider --basetemp E:/Work/xiutu-v5/.test-runs/wp07r2-targeted-77d8ac94 --junitxml=E:/Work/xiutu-v5/docs/implementation/phase-03/evidence/wp-07-review-r2/targeted.xml` | 0 | 2026-09-18T21:05:08.102803+08:00 — 2026-09-18T21:09:06.961813+08:00 |
| reference-guards | `E:\Work\xiutu-v5\.venv\Scripts\python.exe -B -m pytest docs/implementation/phase-03/evidence/wp-07-review-r2/test_reference_guards.py -q -p no:cacheprovider --basetemp E:/Work/xiutu-v5/.test-runs/wp07r2-guards-13b9d478 --junitxml=E:/Work/xiutu-v5/docs/implementation/phase-03/evidence/wp-07-review-r2/reference-guards.xml` | 0 | 2026-09-18T21:09:59.912482+08:00 — 2026-09-18T21:10:21.936389+08:00 |

本轮证据：`docs/implementation/phase-03/evidence/wp-07-review-r2/`。targeted.txt/xml、reference-guards.txt/xml、test-summary.json保存原始统计，child-logs及映射保留本轮子进程输出。没有循环重跑、放宽断言或现场改实现。

## 3. ISSUE-001 — RESOLVED

代码：manual_tools.py:210 summarize、:222 hydrate；executor.py:89成功receipt分支。v2内部元数据位于独立顶层，工具名来自可信执行器。只有schema固定位置chunks[*].text与observations[*].payload省略/恢复，不遍历业务字典、不读取任意_restore_*。旧版本没有回退递归hydrate。conditions仍是既有字符串映射；嵌套结构通过观察payload验证，不为测试扩大输入契约。

本轮实际证据：

- 原跨owner输入标记反例：`marker-cross-owner-*.json`记录foreign_text_in_replay=false；普通外部版本HTTP404/上下文拒绝仍有效。首次及重放合法比较正常，模型提供的chunk/version/hash只是普通conditions数据。
- `condition-key-*.json`覆盖text、payload、_restore_note、_restore_text；首次/重放完全一致。`v2-five-replay-*.json`覆盖五工具及实际ToolCall/ToolMessage，嵌套观察payload不被解释，审计未复制chunk/观察全文，5个调用/used5/比较1。
- 固定引用位置本身改成外部owner ID也被拒绝，见saved-chunk-authorization-*.json；不信任已保存receipt或文本hash作为授权。
- 新补充`fixed-reference-guards.json`：合成Markdown真实解析并以E5建立多chunk索引；实际依次验证不在manifest的index、neighbors=0却换成远端同版本chunk、错hash、缺失真实index成员均被拒绝。scope在case缺engine_code时补充冲突代码，正常为空；把有效chunk塞入该空receipt仍因收窄范围返回SOURCE_INVALID。authorization_epoch变化和当前资格撤销后重放也拒绝。
- 上述白盒故障仅作用于本轮隔离库的receipt/index成员/epoch，index缺项使用真实已生成向量保存后恢复，不以随机向量替代真实服务。代码调用WP06 source验证owner/manifest/version/index/profile/epoch/当前资格，另检查成员/hash/locator及原中心邻域；没有换用active索引。
- `observation-scope-*.json`分别拒绝错case、area、revision；恢复通过原请求的ObservationRepository筛选（含supersedes规则），不会因保存ID绕过范围。五工具组合还验证active索引切换后保持冻结旧index，撤销/注销不再允许历史重放。
- 重放继续过输出schema/整个信封大小限制，见replay-limit-schema/size证据（OUTPUT_INVALID/RESULT_TOO_LARGE），不是只检查首响应。

**旧格式限制已明确且实测符合**：无版本receipt返回不可重试RECEIPT_UNSUPPORTED，保留原succeeded状态及摘要/比较/幂等记录。连续重放仍used1/比较1/幂等1，不重做、不删除、不自动扣预算。历史比较HTTP仍可读。这是安全兼容限制，不视为必须恢复不安全旧格式的缺陷；业务如要新比较，必须明确是新逻辑调用。

## 4. ISSUE-002 — RESOLVED

代码：manual_tools.py比较恢复分支及EvidenceService.get_comparison（:372），同一owner锁/连接/事务内复用WP06当前有效性；不是只检查spec当前approved。

本轮真实HTTP顺序为合法比较→撤销规格→重新批准。`comparison-review-history-*.json`显示旧同key明确COMPARISON_INVALID，历史GET仍current_validity.valid=false，新key比较成功。comparison-review-counts记录最终2条比较、2个幂等响应、used2、每call attempts1。旧needs_review/outcome没有被清除或改写，历史保留并与新比较区分。

关联检查包含当前actor/owner、case/spec、tool-call UUID对应的幂等key/route scope、规范化请求hash、响应comparison ID及不可变结果。`comparison-association-*.json`覆盖替换另一条比较、错spec及改input；新`comparison-call-association.json`分别破坏原幂等请求hash和响应ID，均SOURCE_INVALID，恢复后原响应完全一致，比较/幂等/used均仍1。

`concurrent-replay-*.json`先持owner锁，观察两个请求真实PG等待后放行，响应均等于首响应；calls/attempts/used/比较/幂等记录不增加。没有把线程启动本身当作并发证明。

## 5. 受影响事务/SDK及结合r1的结论

本轮定点实测再次覆盖：比较与receipt同事务、超时/取消/后续receipt SQL延迟完整回滚、并发同身份一条比较、WP06边界经工具与HTTP一致；LangChain输入schema及五工具实际ToolMessage可消费。

原审核4个事务/恢复实例在本轮新库通过：取消先提交与成功先提交两种顺序均观察真实PG锁等待；后续SQL23514回滚不留下比较/幂等/成功receipt；真实commit后受控注入确认丢失，由另一真实Python进程恢复已有成功receipt而不重做副作用。后者不是实际断网实验或生产恢复保证。

| 项目 | 本次更新结论 |
| --- | --- |
| ISSUE-001 | RESOLVED，原权限/业务字段恢复缺陷已关闭，旧格式安全拒绝边界明确 |
| ISSUE-002 | RESOLVED，旧比较自身复核要求与原调用关联已校验 |
| M301 | PASS（限定本地五工具/schema/真实服务与SDK适配）；重放完整性缺陷关闭 |
| M302 | PASS（当前上下文与资料权限）；跨owner/冻结范围及撤销重放缺陷关闭 |
| M303 | 沿用r1未变错误分类证据，结合本轮恢复schema/限额/明确失效错误，PASS |
| M304 | PASS，当前比较复核门禁与受影响事务已验证 |
| M305 | PASS，重放不增计数/预算且事务恢复通过；未变预算/重试机制引用r1基准证据 |

没有发现本次范围内新的必须整改项。**结合r1未变部分，WP-07达到限定范围REVIEW_PASS**；建议接受五业务工具、可信上下文、持久调用记录/预算及本地执行器、只读观察的技术范围。此建议不是用户接受，不等于远程模型strict兼容、业务MCP、正式Agent或整个P3完成。

## 6. 保留项与停止

- 同任务曾实施、整改和复核的流程限制，不能称不同任务独立审核。
- 旧无版本receipt不能经工具自动重放；保留原审计和历史读取，不擅自重做副作用。
- owner粗锁性能、监控、清理、uncertain运维及未来观察写入接入复测等既有非阻断待办保留；本轮不增加无关整改要求。
- E10 NOT_VERIFIED，另行授权后最迟WP09；真实资料门槛NOT_MET，最迟WP10/真实效果验收前。合成规格/within_range不是维修标准或部件正常结论。
- SSE首次超时根因仍未确认。未重跑完整入口/前端/第二环境/模型评测，未验证生产恢复或真实维修效果。

结束保护核对：2932项开始基准全部未变，Git index与旧项目63项相同；STATUS、接受记录、历史报告/证据、已有迁移未修改。仅新增本轮报告与审核工件，未提交/推送/付费调用，未推进WP08。报告封存后停止，等待用户决定。
