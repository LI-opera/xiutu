# WP-08 ISSUE-001 与 Compose 权限定点复核 r2

结论：**REVIEW_PASS（限定 WP-08 三项只读业务 MCP 技术范围）**。ISSUE-001 关闭；r1 中未完成的 Compose 动态权限检查已由本轮实际运行补齐。结合 r1 未变部分，建议用户在下列限制下接受 WP-08；本报告不是用户接受记录，也不代表整个 P3 通过。

**本任务参与过实施、整改和本次复核，不属于不同任务独立审核。** 本轮没有修改实现、STATUS、接受记录或原始证据。

## 1. 依据与基准

已读取 r1 审核、r1 整改、当前契约、源码差异、原反例/启动失败日志及封存文件。项目及上级未发现适用 AGENTS.md。工作区 E:/Work/xiutu-v5；Git 根相同，main，无 HEAD。Git 根/分支/HEAD 返回码、暂存和未暂存状态、未跟踪清单均记录于 baseline.json；仅使用命令级 safe.directory。

- 整改 delivery-hashes 的 **3398 项**全部匹配。整改报告、delivery、protection、r1 报告及 r1 seal 均匹配 final-check。
- 将 delivery 和 final-check 本身加入保护，共 **3400 项**；本轮结束全部不变。Git index 开始/结束 SHA256 均为 `c451d6e78b8f29fc818002923a19fb1a888139ced20679ad545f75e9692a9ec6`。
- 整改前 3325 项基准中只有声明的 `backend/app/mcp_server/main.py` 和 `wp-08-contract.md` 有差异。新增正式测试、测试进程屏障和 Compose 验证脚本与报告声明一致。整改定点源码集合 **128 项**当前全部匹配；客户端重试、预算、应用 receipt 发布、来源门禁、已有迁移没有额外变化。
- 当前导入路径实测为 `E:/Work/xiutu-v5/backend/app/mcp_server/main.py`。没有运行旧 editable 副本。
- 旧项目保护清单 **63 项**核对一致。历史接受记录、审核/整改报告、迁移、STATUS 均在上述保护集合内。
- 原审核 `test_audit_wp08.py`、`audit_server.py` 按字节复制到本轮目录；未修改原反例或断言。

证据：[baseline.json](evidence/wp-08-review-r2/baseline.json)、[static-check.json](evidence/wp-08-review-r2/static-check.json)、[protection-final.json](evidence/wp-08-review-r2/protection-final.json)。本轮文件另由 seal.json 封存。

## 2. ISSUE-001：RESOLVED

### 代码及契约核对

`main.py` 的成功路径保持原 owner 事务锁和当前来源复验。最终 `validate_result` 的所有来源查询、信封构造、大小校验及 `model_dump(mode="json")` 完成后，仍在同一个 UnitOfWork 内重新 `config().authenticate(header).context()`：

1. 配置重新从受保护文件读取，认证重新检查 token 是否仍存在及实时有效期。
2. 当前完整 Binding（含 actor/case/revision/manifest/profile/allowlist）必须等于本次初始可信上下文，工具仍须获允许。
3. 其后仅 deadline 检查、只读事务提交/连接释放及 SDK 序列化发送，没有新的业务资料查询。原 owner 锁在事务结束前持续持有。
4. 拒绝返回无正文、无 provenance 的不可重试错误；应用原有非瞬态失败路径不发布成功 receipt、不执行本地 fallback。

契约明确这一最终判定点，不承诺网络发送后即时撤回。未降低数据库来源撤销保护。`UnitOfWork.__exit__` 提交失败仍会抛出到安全错误路径，而不会返回成功正文。

allowlist 夹具差异仅将共享列表上的 `.remove(name)` 改成赋予目标 grant 一个新列表，避免同时改坏独立合法凭据；与首轮保存源码逐行比较，业务断言及授权规则未变化。

### 本轮实际锁等待与结果

下列实例各运行一次，屏障只控制时序，不替换认证、来源 SQL、SDK 或应用发布。原反例返回 401 后，在途请求也正确失败。

| 实例 | 实际等待证据 | 本轮结果 |
| --- | --- | --- |
| 原审核最终锁撤销 | PG PID 68367，advisory；2026-09-18 15:21:09.104565 UTC | MCP_UNAUTHORIZED，failed、attempts=1、receipt={} |
| owner 锁期间撤销 | final-grant-owner_lock-revoke-ddc9ce0c.json | MCP_UNAUTHORIZED |
| owner 锁期间自然到期 | final-grant-owner_lock-expire-26b69c55.json；等待观察早于 expiry，数据库 changed_at 不早于 expiry | MCP_UNAUTHORIZED |
| owner 锁期间 allowlist 收窄 | final-grant-owner_lock-allowlist-d0473938.json | CONTEXT_STALE |
| owner 锁期间 Binding 变化 | final-grant-owner_lock-binding-4cd89c42.json | CONTEXT_STALE |
| 后续来源 SQL 期间撤销 | final-grant-source_sql-revoke-7d428a19.json；relation 等待且 query 指向 chunks | MCP_UNAUTHORIZED |

新增五例均核对 `pg_blocking_pids` 包含本轮阻塞连接，保存数据库时钟与变更时序；不是以线程启动推断竞争。各例 data=null、provenance=[]、retryable=false、failed、attempts=1、receipt={}，使用额度为 total=1/search=0。失败同 key 重放不额外尝试；换独立有效凭据和新 key 成功后 total=2，旧失败调用仍为一次尝试，未被改写。

## 3. 本轮命令与统计

新库 `xiutu_test_wp08r2_333d155c28ff`，新临时目录 `.test-runs/wp08-r2-333d155c28ff`；调用前已准备父目录。凭据静默来自本项目受保护配置，未读旧 .env。Docker Server 29.4.0，既有 postgres 标签 xiutu-v5/postgres、仅 127.0.0.1:5433、healthy。没有重建数据库服务、删除库卷或停止未知服务。

所有命令 cwd=`E:/Work/xiutu-v5`；run.py 仅注入本轮隔离配置并记录日志。完整 argv、起止时间、退出码见各同名 JSON，原始 stdout/stderr 见 TXT。

| 运行 | 实际命令/范围 | 结果 |
| --- | --- | --- |
| create | `.venv/Scripts/python.exe -B scripts/probes/prepare_database.py --name xiutu_test_wp08r2_333d155c28ff` | exit 0，新库 |
| migrate | `.venv/Scripts/python.exe -B -m alembic upgrade head` | exit 0，仅审核新库，已有迁移未改 |
| targeted | `python -B -m pytest`，选择下列 11 实例，`-q -s --tb=short -p no:cacheprovider`，本轮 basetemp/JUnit | **11 passed，0 failed/error/skipped，未报告警告，152.17 秒，exit 0** |
| compose-check | `python -B .../wp-08-review-r2/compose_review.py` → `scripts/probes/verify_manual_mcp_compose.py`，参数见 compose-argv.json | exit 0，一次启动，完整权限断言通过 |

定点运行时间 **2026-09-18T23:18:35.942634+08:00—23:21:09.880184+08:00**。选择为：

- `test_mcp_final_authorization.py` 的五个参数实例；
- `test_manual_mcp.py::test_real_dual_clients_and_readonly`；
- `test_auth_scope_and_revocation`；
- `test_remote_timeout_cancel_and_late_response`；
- `test_application_deadline_wait_and_no_late_receipt`；
- `test_mcp_transport_contract.py::test_transport_retry_classification`；
- 本轮原样副本 `test_original_audit.py::test_grant_revoked_during_final_lock`。

证据：[targeted.json](evidence/wp-08-review-r2/targeted.json)、[targeted.xml](evidence/wp-08-review-r2/targeted.xml)、[targeted.txt](evidence/wp-08-review-r2/targeted.txt)。正常三工具的应用与独立 CLI 经真实 HTTP 比较 data/provenance，协议版本 2025-11-25；重放预算保持 3。认证/来源撤销、真实 PG 等待超时、取消、应用 deadline 后无成功 receipt 均通过。未额外重复同等演示或重新运行完整入口。

## 4. Compose 动态权限：已补齐

本轮 **2026-09-18T23:21:35.839286+08:00—23:21:53.025727+08:00**，使用本轮新库及双客户端用例的新授权夹具，复用修复后镜像，没有 rebuild。

- 镜像 `xiutu-manual-mcp:wp08-remediation-r1`，ID `sha256:fc83a656fb5a2dbd44b078ccea16ae4f762073b27a0b86e73e62683f4ce95dd7`。
- 实际 linux/amd64 manifest digest `sha256:03189003d1a8b3aad349e9137417cef97a0f72986fb21726ec8aa239df95da41`。
- 容器内 **67 项 backend Python 源码**逐项 SHA256 与当前宿主相等，未拿旧镜像替代修复代码。
- 本轮 project `xiutu-wp08-fix-8a54a5fc0b7d`，容器 `bbff7e22c6d73d6cbba6f0e6cf4641818fa674b01036331c0d41b76ceb0d423f`。完成后只停止这个新服务，postgres 仍 healthy。
- 原 60 秒总启动 deadline 未变；**up 只执行一次**。23:21:41.028851 首次探测 ReadError，容器 running；23:21:41.925263 第二次返回 health 200/ready。每次状态、日志、异常均保存；未循环重启、吞掉容器退出或权限断言错误。
- 容器内关闭默认 transaction_read_only 后：DELETE chunks、UPDATE cases、CREATE TABLE、读取 tool_calls、读取 tool_executions 五项均返回 SQLSTATE **42501**，证明真实 GRANT 限制。
- `/manuals`、`/models/e5`、rootfs 三处实际创建文件均被内核以 **errno 30** 拒绝；UID 10001，rootfs readonly，原文/模型/secret 挂载 readonly，cap_drop ALL、no-new-privileges。
- 从实际 Compose 渲染检查默认不发布宿主端口；debug 仅 loopback。审核服务派生自该配置，复用已有项目数据库网络，没有接管 postgres。
- health 与三工具真实 SDK/HTTP 均成功且非空，上下文 chunk 与搜索结果关联一致。

证据：[compose/results.json](evidence/wp-08-review-r2/compose/results.json)、[compose/commands.json](evidence/wp-08-review-r2/compose/commands.json)、[compose/probes.json](evidence/wp-08-review-r2/compose/probes.json)、[compose-check.json](evidence/wp-08-review-r2/compose-check.json)。

r1 的 RemoteProtocolError、ReadError 两次失败及整改初次夹具失败全部保留。本轮有界等待识别了启动期 ReadError 并完成检查，**不据此认定历史底层原因已确证，更不认定 Docker 是唯一根因**。

## 5. 证据版本、结论与保留项

| 项目 | 结论与证据边界 |
| --- | --- |
| ISSUE-001 | **RESOLVED**：当前代码审查及本轮原反例＋五窗口验证 |
| Compose 动态权限 | **PASS / 补齐**：本轮修复镜像、67 源码对应、实际容器内权限与 HTTP |
| M309 | 结合 r1 未变的常规权限证据、本轮授权与 Compose 补测，限定范围 **PASS** |
| M306/M307/M308/M310/M311 | 引用 r1 基准未变部分；本轮另外重验三工具/双客户端、认证、取消超时/deadline与重试分类，未重新声称全量验证 |
| WP-08 | **REVIEW_PASS，建议限定范围接受，用户尚未接受** |

历史统计严格分开：r1 整改前完整 **301 通过**；整改自测首次 **10 通过、1 个夹具失败**，修正共享列表后失败实例 **1 通过**；本轮 **11 定点通过**及一次 Compose 动态验证。没有将重复测试相加为功能覆盖数，**没有声称整改后 301 项完整入口重新通过**。

没有发现本次范围内新的必须整改问题。性能、owner 粗锁、监控、清理、uncertain 处置、观察接入仍属既有非阻断待办。旧 receipt 安全拒绝及旧比较 needs_review 规则保留。本次只证明后端适配器、独立 CLI、三工具和只读部署；不等于正式 Agent/UI、远程模型 strict、生产恢复或整个 P3 验收。

本轮归档 46 份子进程日志，按 26 个实际测试秘密值扫描证据无命中；这不是对所有潜在泄漏的绝对证明。未调用付费模型或上传私人资料。

- **E10 NOT_VERIFIED**，另行授权后最迟 WP-09。
- **真实资料门槛 NOT_MET**，最迟 WP-10/真实效果验收前补齐；合成技术资料不证明维修效果。
- **SSE 首次超时根因未确认**。
- 同任务实施/整改/复核的流程限制保留，不称为不同任务独立审核。

结束保护核对：3400 项、旧项目 63 项及 Git index 不变。仅新增本报告、审核证据与隔离工件；未改实现、STATUS、接受记录、历史证据或迁移，未提交推送。完成后停止，等待用户决定，不推进 WP-09。
