# WP-07 r1 两项整改记录

状态：**IMPLEMENTED_NOT_ACCEPTED，整改自测完成，等待ISSUE-001/002定点复核**。本报告不是审核通过或用户接受。记录时间：2026-09-18T18:35:20.783326+08:00。

## 1. 范围、基准与保护

仅处理WP07 r1的两项receipt重放问题。读取适用AGENTS（项目及上级未发现）、现行契约、r1报告、原test_audit_tools.py/JUnit和marker-cross-owner、condition-key-*、comparison-review-history原始证据。开始核对**2781项**交付/审核文件无差异，报告与protection-final/final-check封存一致。main无HEAD（verify预期退出128），使用文件SHA256和index固定基准，未因无首次提交省略核对。

开始/结束索引SHA256均为 `c451d6e78b8f29fc818002923a19fb1a888139ced20679ad545f75e9692a9ec6`。旧项目63项、STATUS、接受记录、原报告/证据、0001—0007迁移均未修改。仅五份原文件按授权变化（below），另新增一份正式回归测试、本报告及独立证据。基准、Git完整暂存/未暂存/未跟踪输出、变化哈希与保护结果见baseline.json、git-final.json、protection-final.json。无全局Git设置、add/commit/reset/push操作。

| 文件 | 实际改动 |
| --- | --- |
| backend/app/tools/manual_tools.py | receipt v2固定位置摘要/恢复，chunk当前授权及index成员检查，观察原请求范围筛选，旧比较自身有效性与原调用关联 |
| backend/app/tools/executor.py | 传入可信工具名/原请求/原call，接收恢复信封，重放仍校验输出schema与整个信封大小；预算/预留/发布事务未改 |
| backend/app/services/evidence_service.py | get_comparison增加可选connection，复用WP06原有效性逻辑与外层事务；原HTTP默认行为不变 |
| tests/integration/test_tool_receipts.py（新） | 原反例正式化、业务键/嵌套payload、五工具重放、旧格式策略、比较关联/计数、观察范围、并发、输出限制 |
| docs/implementation/phase-03/wp-07-contract.md、docs/api/wp-07-tools.md | 明确v2格式、旧格式拒绝、合法键语义及COMPARISON_INVALID |

没有迁移、依赖、公开schema或HTTP路由变更。STATUS按用户要求保持原样；其旧“等待集中审核”文字未在本次同步，本报告说明当前等待定点复核。

## 2. ISSUE-001：业务数据与内部恢复信息分离

根因：原summarize/hydrate递归删除text/payload并解释任意_restore_*，把用户conditions变成引用指令。r1真实反例可读另一owner且不在manifest的正文；合法工况键也损坏。原失败XML/JSON/源码完整保留，没有改原断言。

修复：成功摘要使用独立顶层 `{receipt_version:2, tool:可信工具名, answer:信封摘要}`。只在两类固定schema路径省略正文：chunk工具的data.chunks[*].text、观察工具的data.observations[*].payload。其他业务字典不递归解释、不按字段名删除。text/payload/_restore_note/_restore_text在工况、规格及嵌套观察数据内保持原语义。conditions仍为字符串映射，未放宽WP06输入；嵌套JSON通过观察payload验证。

chunk恢复在现有owner锁/事务内调用WP06 source，复核owner、冻结manifest、version/index/profile/authorization_epoch和当前资格；另校验chunk属于该index、hash及locator。上下文还复核原中心和neighbors，搜索重放复核原收窄scope。观察通过原case/area/at_revision及supersedes规则筛选，按保存ID恢复，不补入新记录。整个路径继续调用当前认证/可信context检查，schema与字节限制在重放后生效。UUID、hash、receipt本身均不充当授权。

**旧格式策略**：无版本/不支持格式明确返回不可重试RECEIPT_UNSUPPORTED。原成功状态和审计摘要不改，历史比较可经现有HTTP查看。不递归恢复、不猜测迁移、不重新执行、不加比较或预算、不删除审计。v2没有把chunk正文或观察全文复制进tool_calls；测试以实际审计行检查正文和cookie/capability未进入记录。

验证证据（均本轮新库）：正式测试保留原text/payload/_restore_note及跨owner反例断言，新增_restore_text；新组合用例对五工具普通调用/重放/真实LangChain ToolCall→ToolMessage逐一比对，含嵌套观察payload。`marker-cross-owner-*.json`中foreign_text_in_replay=false。`v2-five-replay-*.json`确认五调用、五次预算、一条比较、固定旧index，撤销/注销拒绝且不加计数。`saved-chunk-authorization-*.json`直接把固定引用位置改成外部owner引用也被CORPUS_NOT_ALLOWED拒绝。`observation-scope-*.json`拒绝错case/area/revision。`legacy-receipt-*.json`证明旧格式保留原记录且used=1/比较1/幂等1。`replay-limit-*.json`验证OUTPUT_INVALID和RESULT_TOO_LARGE。

## 3. ISSUE-002：旧比较本身有效性及关联

根因：原重放只检查当前spec approved，规格重新批准后忽略comparison自身needs_review，导致历史HTTP为invalid但工具返回无失效说明的within_range。

修复：按comparison_id调用WP06 get_comparison，在同一物理连接/owner事务中复用原current_validity。检查comparison对应当前case/spec、原tool-call的幂等记录key/请求hash/响应ID以及不可变结果内容。旧比较需复核返回不可重试COMPARISON_INVALID；不清标记、不改outcome、不重做原逻辑调用。新key的新合法比较仍正常。关联异常返回SOURCE_INVALID。

验证：真实HTTP撤销→重新批准后，原GET仍current_validity.valid=false；工具旧同key明确COMPARISON_INVALID；新key成功。`comparison-review-history-*.json`与`comparison-review-counts-*.json`记录最终2条比较/2个幂等响应/used=2，每call attempts=1。`comparison-association-*.json`覆盖将receipt换成另一comparison、错spec或篡改input的拒绝。`concurrent-replay-*.json`先持owner锁，观察两个请求真实PG阻塞后放行，两次响应完全一致且预算/比较/幂等记录未增加。

## 4. 实际运行、失败和回归边界

只复用经当前inspect确认的xiutu-v5-postgres-1（running、项目标签、127.0.0.1:5433），未启动/重建/停止容器。新唯一数据库：`xiutu_test_wp07fix_56ba9b897b4648c491`，新临时/存储目录，现有0007迁移应用到新库。仅静默读取本项目凭据；未读取旧.env、改实际密码、删除既有库或卷。真实HTTP、独立worker、本地固定E5、真实PostgreSQL用于资料和规格准备，未使用付费服务。

| 本轮运行 | 结果 | 说明 |
| --- | --- | --- |
| targeted | **33通过、1失败、0错误/跳过；exit1，215.84秒** | 34项。唯一失败为新增组合测试json.dumps审计快照时UUID不可序列化；此前五工具/SDK重放已通过。不是产品失败，也未删除失败日志 |
| targeted-followup | **5通过、0失败/错误/跳过；exit0，40.42秒** | 修正测试记录为default=str后只复跑该项；旧比较用例加强计数断言后复跑，并新增引用与输出限制3项。未重跑整包 |
| lint-initial | exit1 | 新测试fixture导入标记/导入顺序问题，记录后修正；无业务异常 |
| lint、lint-final | exit0 | 当前三份实现和新测试静态检查通过 |

两个pytest运行均无警告摘要。本次共覆盖37个不同测试实例；重复运行的两个实例不叠加计数。最终实现与首轮targeted相同，仅新增测试修正/加强和说明文件有后续差异，targeted-code-hashes及最终哈希可核对。原初稿测试另存test_tool_receipts.initial.py.txt，原失败targeted.txt/xml原样保留。

原r1 audit源码逐字复制到本轮目录，仅运行其中4个事务/恢复实例（两个cancel顺序、后续SQL错误、提交确认丢失后的实际新进程成功receipt恢复），输出落本轮目录；原文件和失败记录不变。原5个失败实例已按相同语义断言加入正式回归（并扩展一个合法键），本轮通过，不以修改原断言宣称旧审核通过。

受影响定点回归还包括：比较超时/取消/后续receipt SQL延迟的整体回滚、并发同逻辑比较一条记录、WP06精确边界经工具与HTTP结果一致、真实LangChain schema/调用输出。成功先提交/取消先提交测试观察了实际PG锁等待；失去commit确认是**真实commit之后的受控异常注入**，另一个真实进程恢复，不宣称真实网络断线或生产恢复保证。

执行者/审核r1的完整260项及其其他事务证据仅作整改前引用，本次**没有运行完整入口、前端、第二环境或模型评测**，不将其写成整改后260通过。所有运行cwd均E:/Work/xiutu-v5，详细命令、起止与退出码如下，连接串未出现在命令中。

| 标签 | 命令 | 退出码 | 起止 |
| --- | --- | --- | --- |
| environment | `docker inspect xiutu-v5-postgres-1 --format {{json .Config.Labels}} {{json .State.Status}} {{json .NetworkSettings.Ports}}` | 0 | 2026-09-18T18:24:41.646333+08:00 — 2026-09-18T18:24:41.804917+08:00 |
| create | `E:\Work\xiutu-v5\.venv\Scripts\python.exe -B scripts/probes/prepare_database.py --name xiutu_test_wp07fix_56ba9b897b4648c491` | 0 | 2026-09-18T18:26:41.621521+08:00 — 2026-09-18T18:26:42.295161+08:00 |
| migrate | `E:\Work\xiutu-v5\.venv\Scripts\python.exe -B -m alembic upgrade head` | 0 | 2026-09-18T18:27:02.548729+08:00 — 2026-09-18T18:27:03.706540+08:00 |
| lint-initial | `E:\Work\xiutu-v5\.venv\Scripts\ruff.exe check backend/app/tools/manual_tools.py backend/app/tools/executor.py backend/app/services/evidence_service.py tests/integration/test_tool_receipts.py` | 1 | 2026-09-18T18:27:32.177688+08:00 — 2026-09-18T18:27:32.221070+08:00 |
| lint | `E:\Work\xiutu-v5\.venv\Scripts\python.exe -B -m ruff check backend/app/tools/manual_tools.py backend/app/tools/executor.py backend/app/services/evidence_service.py tests/integration/test_tool_receipts.py` | 0 | 2026-09-18T18:29:26.117312+08:00 — 2026-09-18T18:29:26.261536+08:00 |
| targeted | `E:\Work\xiutu-v5\.venv\Scripts\python.exe -B -m pytest tests/integration/test_tool_receipts.py tests/integration/test_business_tools.py::test_comparison_publication_is_atomic tests/integration/test_business_tools.py::test_concurrent_comparison_identity tests/integration/test_business_tools.py::test_tool_comparison_matches_wp06 tests/contract/test_tools.py docs/implementation/phase-03/evidence/wp-07-remediation-r1/test_audit_tools.py::test_committed_receipt_survives_lost_commit_ack docs/implementation/phase-03/evidence/wp-07-remediation-r1/test_audit_tools.py::test_cancel_commit_orders_with_real_pg_wait docs/implementation/phase-03/evidence/wp-07-remediation-r1/test_audit_tools.py::test_later_sql_error_rolls_back_comparison_and_receipt -q -p no:cacheprovider --basetemp E:/Work/xiutu-v5/.test-runs/wp07fix-targeted-a5ea8720 --junitxml=E:/Work/xiutu-v5/docs/implementation/phase-03/evidence/wp-07-remediation-r1/targeted.xml` | 1 | 2026-09-18T18:27:32.490824+08:00 — 2026-09-18T18:31:10.249953+08:00 |
| targeted-followup | `E:\Work\xiutu-v5\.venv\Scripts\python.exe -B -m pytest tests/integration/test_tool_receipts.py::test_combined_nested_business_keys_and_five_replays tests/integration/test_tool_receipts.py::test_revoked_then_approved_comparison_keeps_review_requirement tests/integration/test_tool_receipts.py::test_saved_chunk_reference_is_not_authority tests/integration/test_tool_receipts.py::test_replay_validates_output_and_envelope_size -q -p no:cacheprovider --basetemp E:/Work/xiutu-v5/.test-runs/wp07fix-followup-091ac82e --junitxml=E:/Work/xiutu-v5/docs/implementation/phase-03/evidence/wp-07-remediation-r1/targeted-followup.xml` | 0 | 2026-09-18T18:32:04.232366+08:00 — 2026-09-18T18:32:46.602452+08:00 |
| lint-final | `E:\Work\xiutu-v5\.venv\Scripts\python.exe -B -m ruff check backend/app/tools/manual_tools.py backend/app/tools/executor.py backend/app/services/evidence_service.py tests/integration/test_tool_receipts.py` | 0 | 2026-09-18T18:32:38.556752+08:00 — 2026-09-18T18:32:38.685531+08:00 |

原始证据目录：`docs/implementation/phase-03/evidence/wp-07-remediation-r1/`；每运行有json元数据、txt输出及JUnit。child-logs保存本轮子进程日志，映射和SHA256另附，输出已扫描实际本地数据库密码及fixture认证泄漏断言。测试结束只清理本轮fixture子进程/schema，新测试库保留。基准、源码/交付哈希和封存记录支持后续定点复核。

## 5. 残余限制与停止

两项修复已完成执行者定点自测，**不生成REVIEW_PASS，不代替审核关闭或用户接受**。请仅定点复核两项及受影响路径，无新增影响依据不重开整包。旧无版本receipt的安全拒绝是明确兼容变化；历史不可通过工具自动恢复，仍可经原历史接口读取，不擅自新建逻辑调用代替恢复。

同任务实施、审核、整改的流程限制保留。原owner粗锁、性能/监控/清理、不明结果人工处置、观察未来写入等非阻断待办不在此次整改。E10仍NOT_VERIFIED，授权后最迟WP09；真实资料仍NOT_MET，最迟WP10/真实效果验收前；SSE首次根因未确认。未实现WP08业务MCP/正式Agent/观察写入，不接受整个P3，不做真实维修效果或生产恢复结论。

本轮未修改STATUS、接受记录、旧项目、原报告/证据、已有迁移或Git index；无提交推送/付费调用。报告封存后停止，等待定点复核。
