# WP-08 ISSUE-001 与 Compose 验证整改 r1

时间：2026-09-18T23:11:36.468648+08:00。
状态：**IMPLEMENTED_NOT_ACCEPTED**。仅完成ISSUE-001最小修复和Compose补测，等待定点复核；这是同任务执行者自测，不是审核关闭、REVIEW_PASS或用户接受。没有开始WP-09。

目前成功返回会在全部阻塞锁/来源SQL之后重新读取当前grant。撤销、自然到期或授权变化不能再沿用锁等待前的授权发布成功正文/receipt。修复后的新镜像已完成三工具、health及容器只读权限验证。

## 1. 基准与文件范围

已读取适用路径（项目及上级未发现AGENTS.md）、当前STATUS、WP08契约、r1审核、原真实锁等待反例及两次Compose失败脚本/日志。开始逐项核对r1 baseline及seal，**3325项**匹配，无非预期差异。Git main，无HEAD；分支/暂存/未暂存/未跟踪记录见[baseline.json](evidence/wp-08-remediation-r1/baseline.json)。

修改已有文件仅：

- `backend/app/mcp_server/main.py`：成功返回前最终授权点，响应准备仍在原owner事务锁内。
- `docs/implementation/phase-03/wp-08-contract.md`：补充准确的最终判定点、错误与网络边界。

新增必要文件：

- `tests/integration/test_mcp_final_authorization.py`：5种真实PG等待/授权变化实例。
- `tests/wp08_mcp_process.py`：仅隔离测试子进程使用的时序屏障，不是生产开关。
- `scripts/probes/verify_manual_mcp_compose.py`：一次启动、同一60秒deadline、逐次状态/日志与实际权限断言。
- 本报告和独立证据目录。

未改变客户端重试/预算、应用executor发布、ManualTools/source算法、旧receipt机制、依赖锁、Compose发布配置或任何迁移。没有新接口或认证平台。差异见[main.diff](evidence/wp-08-remediation-r1/main.diff)、[contract.diff](evidence/wp-08-remediation-r1/contract.diff)。

结束保护：3325项基准中仅上列两个已授权现有文件变化；STATUS、全部原报告/证据/接受记录、0001—0007、db_target及其他实现未变，旧项目63项保护一致。Git index仍为`c451d6e78b8f29fc818002923a19fb1a888139ced20679ad545f75e9692a9ec6`。见[protection-final.json](evidence/wp-08-remediation-r1/protection-final.json)。

## 2. ISSUE-001：根因、最终授权点与失败边界

原authorized在authenticate后再等待owner锁；执行后的authorized也如此。grant可在最终owner锁或后续来源SQL等待期间撤销，而返回路径不再读取配置。r1已证明新请求401、在途调用仍成功并落receipt。

本次保留初始/最终owner、case、revision、manifest、epoch及来源校验；不以换掉首次authenticate位置解决问题。现在顺序为：

1. 原最终authorized取得owner事务锁并检查当前case/source。
2. 原validate_result完成全部来源SQL、正文/hash/locator/规格校验。
3. 准备并验证成功信封、大小和JSON数据，仍持有同一owner锁。
4. **最终授权判定点**：重新加载受保护配置并authenticate当前token，按当前UTC时钟判断期限；完整Binding（包含allowlist）须等于本次初始可信上下文，工具仍在允许列表。
5. 再做墙钟deadline检查；其后仅结束只读事务、SDK序列化/发送，没有新资料查询。

撤销/到期为MCP_UNAUTHORIZED；Binding/allowlist变化为CONTEXT_STALE。失败返回ok=false、data=null、无provenance，retryable=false。应用原executor将该次调用记failed，不写成功receipt，不自动重试授权错误、不fallback。服务端只读UOW异常退出回滚并释放锁；本轮没有新增服务端业务写入。

这定义了发送前的最终授权判定点，**不承诺该点后网络发送期间的即时撤回**。数据库资料撤销仍受原owner锁串行保护，未降低原来源门禁。仅延长仍合法的有效期不要求无故拒绝；自然到期在最终认证时重新判断。

## 3. 定点验证（执行者本轮）

隔离库：`xiutu_test_wp08fix_f2322f7c6927`，由本轮新建；只在该库应用现有0007迁移，不读取旧.env。新临时目录`.test-runs/wp08-fix-targeted-f2322f7c`与`.test-runs/wp08-fix-allowlist-f2322f7c`，父目录已准备。凭据静默加载，原文/数值均synthetic；复用现有本地E5，无付费请求。

原反例`test_audit_wp08.py`及`audit_server.py`原样复制到本轮证据目录运行，只选原锁等待用例；字节SHA256与原件相同。原件和旧失败日志不改。本轮[grant-final-lock-01fa2abc.json](evidence/wp-08-remediation-r1/grant-final-lock-01fa2abc.json)为ok=false、MCP_UNAUTHORIZED、failed、attempts=1、receipt={}。

正式回归屏障仅暂停真实ManualTools读取之后或真实validate_result之前；授权、来源校验与HTTP transport仍执行原实现。owner窗口持有真实pg_advisory_xact_lock；source_sql窗口持有chunks表ACCESS EXCLUSIVE锁，让最终真实SELECT等待。每例检查pg_stat_activity的Lock类型、pg_blocking_pids确含本轮阻塞连接，记录DB时钟；不是仅启动线程。自然到期例先证实等待开始早于expiry，再等待真实时间跨越期限，不替换时钟。

| 场景（原始JSON见同目录） | 错误 | 实际PG等待 | 核心断言 |
| --- | --- | --- | --- |
| owner_lock-allowlist | CONTEXT_STALE | 66174:advisory | failed / 1 / 空；新凭据成功、used 1→2 |
| owner_lock-binding | CONTEXT_STALE | 65617:advisory | failed / 1 / 空；新凭据成功、used 1→2 |
| owner_lock-expire | MCP_UNAUTHORIZED | 65532:advisory | failed / 1 / 空；新凭据成功、used 1→2 |
| owner_lock-revoke | MCP_UNAUTHORIZED | 65489:advisory | failed / 1 / 空；新凭据成功、used 1→2 |
| source_sql-revoke | MCP_UNAUTHORIZED | 65658:relation | failed / 1 / 空；新凭据成功、used 1→2 |

各例还验证失败同key重放不再增加尝试；换独立有效凭据和新key可成功，总used仅1→2，search_used=0（本组使用context工具）。原失败记录保持failed、attempts=1。新凭据成功不改写旧调用。

选中11项不同实例：5个新窗口、原审核反例1项、现有三工具双客户端/认证/超时取消/应用deadline各1项，以及transport重试分类1项。没有重新跑完整入口。

| 运行 | 实际结果 | 时间与证据 |
| --- | --- | --- |
| targeted | **10通过、1失败、0错误/跳过**，exit1；158.74秒 | 2026-09-18T22:58:56.570839+08:00—2026-09-18T23:01:37.285310+08:00；[targeted.xml](evidence/wp-08-remediation-r1/targeted.xml)、同名TXT/JSON |
| allowlist-fix | **1通过、0失败/错误/跳过**，exit0；16.76秒，仅重跑失败实例 | 2026-09-18T23:03:43.763954+08:00—2026-09-18T23:04:02.266712+08:00；[allowlist-fix.xml](evidence/wp-08-remediation-r1/allowlist-fix.xml) |
| lint | 本次4个Python文件ruff check --no-cache，exit0 | lint.json/TXT |

首轮失败原因：测试夹具构建两份grant时浅拷贝了相同allowlist列表；测试用remove原地收窄第一个grant，同时改变了备用合法凭据。原调用拒绝、无receipt/预算等断言已经通过，失败在最后“新合法凭据成功”。已改为只替换目标grant的列表，未改业务实现或削弱断言。首轮测试源码保留`test-final-authorization-first.py.txt`；`allowlist-test-diagnosis.json`保存两份列表被误改的实际配置摘要。随后只重跑这一项通过；不能将重复实例累加为12项不同覆盖，也不声称一次11/11首轮全绿。

正常三工具真实HTTP/独立CLI、认证与资料撤销、超时/取消、PG等待deadline及无迟到receipt使用选中的现有测试证明，原完整301其余部分复用r1整改前证据。**没有整改后完整入口通过的声明**，没有前端/第二环境/模型评测重跑。测试未报告新增pytest警告；编写期lint提示和一次无写权限的ruff缓存失败不算业务测试，最终使用no-cache限定检查通过。

## 4. Compose：原失败分析与本轮补齐

原审核两次失败分别为RemoteProtocolError、ReadError/WinError10053，均发生在容器启动后的HTTP探测期；旧等待器仅捕获部分异常，提前退出并在finally停止了尚启动中的实例。原日志为空、退出137、无OOM证据，不能据此认定服务代码崩溃，也不能确定Windows/Docker转发层的唯一根因。原脚本和失败证据保持不变。

新脚本不只加长等待：

- **总deadline仍60秒**，从唯一up开始覆盖ps/inspect/logs/HTTP；每个子命令和HTTP timeout受剩余时间约束。
- 仅处理已知启动期ConnectError/ConnectTimeout/ReadError/ReadTimeout/RemoteProtocolError；记录每次时间、异常类型、容器State和日志。非预期HTTP状态、容器退出、断言/配置错误直接失败。
- 不重新启动、重建或循环创建服务；成功后实际执行权限与业务断言。失败也保留probe/command证据，并只停止自己新project的manual-mcp。
- 从现行deploy/compose.yaml及debug override渲染获得实际服务配置，检查默认无ports、debug仅127.0.0.1；只将本次image、新secret路径和隔离project网络接入替换，不手写另一套权限规则。

本轮前两次`compose-launch.py`夹具选择失败均发生在Docker调用前：选择前缀长于pytest实际截短目录名，第二次排除current链接仍未修正前缀；随后使用已核实真实目录（排除符号链接）。对应compose/compose-run TXT/JSON及两个脚本初稿保留。**实际容器启动只有一次**，并非两次启动失败后循环重启。

### 新镜像与实际验证

源码发生变化，因此新构建镜像，未拿旧镜像证明修复；固定基础镜像与依赖层缓存复用，backend重新COPY。

- tag：`xiutu-manual-mcp:wp08-remediation-r1`。
- image ID/manifest-list digest：`sha256:fc83a656fb5a2dbd44b078ccea16ae4f762073b27a0b86e73e62683f4ce95dd7`。
- linux amd64 manifest digest：`sha256:03189003d1a8b3aad349e9137417cef97a0f72986fb21726ec8aa239df95da41`。
- 对容器内**67项backend Python文件**逐项与当前宿主源码SHA256比对，全部一致。
- 本轮project：`xiutu-wp08-fix-69369e56a694`；容器：`635173518ab2b53c66dc5fd46e0c9892d36073e80c0afddcb88e6e20ff743059`。
- 启动命令1次，探测2次：首次RemoteProtocolError被记录，第二次HTTP200，status=ready/protocol2025-11-25/readonly=true；没有扩展60秒deadline。

实际成功项：

| 检查 | 本轮结果 |
| --- | --- |
| health及三工具 | PASS；固定本地E5真实search、context、spec，经SDK HTTP；非空，context与search的chunk/version/index/hash/locator一致 |
| 专用角色权限 | PASS；容器内将transaction_read_only设off后，DELETE、UPDATE、CREATE TABLE、读取tool_calls、读取tool_executions均SQLSTATE42501 |
| 挂载与rootfs | PASS；/manuals、/models/e5、/根写探针均内核errno30；3个bind mount RW=false |
| 用户与capabilities | PASS；实际uid10001、rootfs只读、cap_drop ALL、no-new-privileges |
| 网络 | PASS；默认渲染无宿主端口；实际本轮debug只绑定loopback，DB内部postgres:5432，不公开数据库凭据 |
| 源码及生命周期 | PASS；新image及67项源码匹配；最后只stop本轮服务，exit0；容器内部Docker healthcheck也记录exit0 |

真实命令、每次探测、权限输出和三工具结果分别在[compose/commands.json](evidence/wp-08-remediation-r1/compose/commands.json)、[probes.json](evidence/wp-08-remediation-r1/compose/probes.json)、[results.json](evidence/wp-08-remediation-r1/compose/results.json)。运行窗口2026-09-18T23:05:21.608673+08:00—2026-09-18T23:05:39.077419+08:00，exit0。停止后的Docker Health.Status标记不作为运行期健康失败；其Log实际ExitCode0、FailingStreak0，最终进程exit0。postgres原容器保持healthy，原实现/审核MCP容器状态未变；未删除库/卷或改既有角色密码。

## 5. 可复查命令

cwd均为E:/Work/xiutu-v5。完整argv/起止/退出码见各label.json；run.py只静默配置本轮DB/临时路径及输出，未把URL或secret放命令行。

- create：`python -B scripts/probes/prepare_database.py --name xiutu_test_wp08fix_f2322f7c6927`，exit0。
- migrate：`python -B -m alembic upgrade head`，exit0。
- targeted：`python -B -m pytest tests/integration/test_mcp_final_authorization.py tests/integration/test_manual_mcp.py::test_real_dual_clients_and_readonly tests/integration/test_manual_mcp.py::test_auth_scope_and_revocation tests/integration/test_manual_mcp.py::test_remote_timeout_cancel_and_late_response tests/integration/test_manual_mcp.py::test_application_deadline_wait_and_no_late_receipt tests/contract/test_mcp_transport_contract.py::test_transport_retry_classification docs/implementation/phase-03/evidence/wp-08-remediation-r1/test_original_audit.py::test_grant_revoked_during_final_lock -q -s --tb=short -p no:cacheprovider --basetemp .test-runs/wp08-fix-targeted-f2322f7c --junitxml=E:/Work/xiutu-v5/docs/implementation/phase-03/evidence/wp-08-remediation-r1/targeted.xml`。
- 失败单项复跑：同pytest选`test_final_grant_after_database_wait[owner_lock-allowlist-CONTEXT_STALE]`，新basetemp和allowlist-fix.xml，exit0。
- image-build：`docker build -f deploy/manual-mcp.Dockerfile -t xiutu-manual-mcp:wp08-remediation-r1 .`，exit0。
- Compose实际入口：`python -B scripts/probes/verify_manual_mcp_compose.py --server-config <本轮新合成夹具/server-secret.json> --client-config <本轮新合成夹具/client-1-secret.json> --image xiutu-manual-mcp:wp08-remediation-r1 --output <全新证据目录>`，由compose-launch.py选取本轮正确目录调用。后续复核应使用新的输出/授权夹具，不覆盖当前目录或复用过期token。

## 6. 剩余限制与停止点

ISSUE-001修复及本轮必要验证完成，Compose先前未完成的权限项已有本轮新镜像实测证据；尚待审核者定点复核，**不在执行者报告中关闭审核问题或生成审核通过**。

保留：同任务实施/审核历史限制；发送后的授权实时撤回不在本包承诺内；旧receipt安全拒绝与旧比较复核要求；CPU非硬实时、owner粗锁、性能/监控/清理/uncertain等既有待办。原两次Compose异常的底层唯一根因未确证，新脚本只修正有界启动探测契约；不据此宣称修复Docker平台。

E10继续**NOT_VERIFIED**，另行授权后最迟WP-09；真实资料门槛继续**NOT_MET**，最迟WP-10/真实效果验收前。SSE首次超时根因仍未确认。本包无付费模型调用、私人资料上传、正式Agent/UI或WP09实施。

STATUS未修改，WP08保持IMPLEMENTED_NOT_ACCEPTED。无接受记录修改、Git index调整、提交或推送。报告及交付哈希封存后停止，等待仅针对ISSUE-001及Compose证据的定点复核。
