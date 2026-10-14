# WP-08 集中审核 r1

审核时间：2026-09-18T22:36:37.828566+08:00。
结论：**CHANGES_REQUIRED**。M306、M307、M308、M310、M311在本包限定范围通过；M309存在一项已实际复现的授权撤销窗口，不能建议现在接受WP-08。另有本轮Compose权限验证未完成，详见下文，不将审核等待器异常直接判成产品缺陷。

本任务参与过WP-08实施，本轮切换审核角色；**实施与本次审核由同一任务完成，不属于不同任务独立审核**。没有现场修复业务代码，没有修改STATUS或生成接受记录。

## 1. 依据、基准及保护

已读取STATUS、WP07接受记录、WP08契约/结果、MCP运行手册/API/导出schema、依赖矩阵，以及旧项目P3实施说明/验收清单、总指南9.1/9.2、WP08与资料权限/预算规定。项目与上级未发现适用AGENTS.md。

工作区：E:/Work/xiutu-v5；旧项目E:/Work/v4-double保持不变。Git根为新项目，main，无HEAD（未首次提交）；未因无HEAD跳过未跟踪文件。起始Git根/分支/HEAD退出码、完整暂存/未暂存/未跟踪状态保存在[baseline.json](evidence/wp-08-review-r1/baseline.json)。只使用命令级safe.directory。

- 执行者delivery-hashes中的**3232项**逐项匹配；结果报告、delivery/protection/baseline/full-code封存哈希均匹配final-check。
- 审核起始保护集包含以上文件及两个封存文件，共3234项；结束逐项无差异。
- full-code-hashes的**125项**当前源码/测试/脚本/锁文件均匹配，确认执行者最终301完整运行后没有实现变化；审核完整入口也导入当前backend源码，而非旧editable副本。
- Git index开始/结束均为`c451d6e78b8f29fc818002923a19fb1a888139ced20679ad545f75e9692a9ec6`。0001—0007、db_target、历史审核/接受记录和证据受上述文件集合保护；旧项目63项另行核对一致。
- 新增内容仅本报告与本轮审核证据/隔离测试工件。未修改实现、已有迁移、STATUS、接受记录、原证据或Git index，未提交/推送。

证据：[static-baseline.json](evidence/wp-08-review-r1/static-baseline.json)、[protection-final.json](evidence/wp-08-review-r1/protection-final.json)、最终seal.json。锁定实际版本mcp1.30.0、httpx0.28.1、SQLAlchemy2.0.54、psycopg3.3.5、Pydantic2.13.5。已读安装SDK的manager/client源码，确认handle_request经过SDK请求体限制和真实stateless transport管理器；未用echo或直接函数替代业务协议。

执行者历史证据独立解析：[historical-xml-check.json](evidence/wp-08-review-r1/historical-xml-check.json)。首次full.xml仅1个collection error占位，0业务测试执行；final-full为301通过/1既有警告。它们不计作本轮运行。

## 2. 本轮实际运行与隔离

本轮新库：`xiutu_test_wp08audit_ceb429c8acd4`；来源仅本项目受保护数据库配置，未读取旧.env或输出连接串。Docker Server29.4.0；现有postgres容器c15ff5e421d3，标签xiutu-v5/postgres，127.0.0.1:5433，开始/结束healthy。未删除库/卷、重建postgres或停止未知服务。

完整入口新临时目录：`.test-runs/run-8d6b3aaa051242658afa71bcb02c5686`。补充测试新目录：`.test-runs/wp08-audit-targeted-ceb429c8`，父目录已准备。输出全部在`evidence/wp-08-review-r1`。沿用已核对venv与本地E5；无新模型选型、质量评测、前端或第二环境验证。

所有命令cwd=E:/Work/xiutu-v5；以下通过本轮run.py静默注入仅测试连接和独立输出目录。完整argv、时间与退出码见各同名JSON，stdout/stderr见TXT。

| 运行 | 实际命令（省略仅用于记录的run.py包装） | 时间/退出码/结果 |
| --- | --- | --- |
| create | `.venv/Scripts/python.exe -B scripts/probes/prepare_database.py --name xiutu_test_wp08audit_ceb429c8acd4` | exit0，全新库 |
| migrate | `.venv/Scripts/python.exe -B -m alembic upgrade head` | exit0，仅隔离库现有0007环境 |
| full | `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/test.ps1` | 2026-09-18T22:15:22.126218+08:00—2026-09-18T22:28:54.498116+08:00；exit0；**301通过，0失败/错误/跳过，1警告，809.50秒** |
| targeted | `.venv/Scripts/python.exe -B -m pytest docs/implementation/phase-03/evidence/wp-08-review-r1/test_audit_wp08.py -q -s --tb=short -p no:cacheprovider --basetemp .test-runs/wp08-audit-targeted-ceb429c8 --junitxml=E:/Work/xiutu-v5/docs/implementation/phase-03/evidence/wp-08-review-r1/targeted.xml` | 2026-09-18T22:29:48.467125+08:00—2026-09-18T22:30:33.968843+08:00；exit1；**1通过、2失败、0错误/跳过，43.67秒** |
| compose-continuation | `.venv/Scripts/python.exe -B docs/implementation/phase-03/evidence/wp-08-review-r1/compose_continue.py` | 2026-09-18T22:31:48.511184+08:00—2026-09-18T22:31:54.806042+08:00；exit1；启动期ReadError，权限断言未执行完 |

完整JUnit：[full.xml](evidence/wp-08-review-r1/full.xml)，输出[full.txt](evidence/wp-08-review-r1/full.txt)。警告为既有Starlette/AnyIO BlockingPortal弃用提示，没有屏蔽。补充JUnit：[targeted.xml](evidence/wp-08-review-r1/targeted.xml)，输出[targeted.txt](evidence/wp-08-review-r1/targeted.txt)。不将301与补充运行简单累加成不同功能覆盖数。

补充三项结果分开解释：

1. `test_grant_revoked_during_final_lock`：**失败，真实实现缺陷**，见ISSUE-001。
2. `test_missing_config_and_auth_budget`：**通过**。默认remote缺配置返回MCP_CONFIG_UNAVAILABLE；服务token撤销后实际SDK调用返回MCP_UNAUTHORIZED；各attempt=1、failed、无receipt，没有认证重试或local fallback。
3. `test_compose_readonly`：**审核启动等待器失败**。Compose up成功，但HTTP健康探测在服务启动期收到RemoteProtocolError，立即退出，finally停止本轮容器；尚未执行容器写入拒绝断言。保留原脚本/日志，没有修改失败断言。

为完成尚未执行的权限检查，另建compose_continue.py，仅start同一个本轮容器，增加对已观察启动期连接关闭的有界等待；随后遇到ReadError（WinError10053），再次在权限断言前退出。两份失败原文均保留；没有继续循环重跑、扩大超时或宣称Compose通过。空容器日志及最终Exit137来自审核finally停止启动中容器，不能据此认定业务服务崩溃或最终环境根因。

本轮Compose资源：project `xiutu-wp08-audit-1c6289279d`、容器`d48aa4f85044819012dbb75a4bc85fa98b54494c9dae146d91e055adab7c092d`，现已停止；复用镜像`sha256:19557fb97b20ca5cc263a7f63dc14fd085a6dfe77944b57ffe9881d6001ad054`，未重建依赖。使用独立测试角色/凭据，外部网络仅连接已归属xiutu-v5的postgres；审核文件只为独立project和loopback临时端口调整部署，不接管原manual-mcp容器。原容器338bcfe76878一直保持停止，postgres保持healthy。

[compose-commands.json](evidence/wp-08-review-r1/compose-commands.json)、[compose-continuation-commands.json](evidence/wp-08-review-r1/compose-continuation-commands.json)、[docker-final.json](evidence/wp-08-review-r1/docker-final.json)保留真实轨迹。静态Compose和实际创建容器配置可核对非root、rootfs只读、cap_drop ALL、no-new-privileges、只读bind；**本轮内核写入拒绝和容器内角色拒绝仍NOT_VERIFIED**。执行者compose-results中的成功属于旧证据，不能替代本轮未完成检查。本轮完整入口已经在原生独立MCP进程实测只读role关闭transaction_read_only后DML/DDL/审计表读取均42501。

## 3. M306—M311逐项结论

| ID | 结论 | 代码审查及本轮证据 |
| --- | --- | --- |
| M306 | PASS | main.py真实SDK Server/StreamableHTTPSessionManager；client.py真实ClientSession和streamable_http_client，protocol2025-11-25。独立Uvicorn服务、应用测试进程、独立CLI子进程；stateless拒绝session header，每次新尝试initialize/list/call/close。完整入口dual-clients、reconnect、server日志；资源通过AsyncExitStack/manager lifespan关闭，CPU只读工作不承诺硬抢占 |
| M307 | PASS | tools/list恰好三工具，INPUTS及逐工具OUTPUTS嵌入schema与导出文件逐项一致；extra=forbid、输入上限和65536字节输出限制。未知工具、伪owner/profile、schema漂移、非法/超大结果明确拒绝。SDK协议错误反例中的替身仅证明错误处理，真实服务能力来自集成用例 |
| M308 | PASS | 本轮dual-clients-cca07c9c.json：应用remote_mcp＋CLI真实HTTP三工具，独立token；data/provenance一致，含chunk/version/index/hash/locator和spec/evidence/version。搜索真实PG及本地E5，无重复演示或echo充数 |
| M309 | **FAIL** | 常规token/Host/Origin/null/session、scope/corpus、资料撤销、cookie注销及远端篡改拒绝通过；固定旧index未被active替换。**最终锁等待期间撤销token仍发布成功**，ISSUE-001。Compose本轮动态权限检查另为NOT_VERIFIED，原因如上 |
| M310 | PASS（现有故障/预算范围） | 实际停止本轮MCP进程，失败2次尝试、总/search预算各+2，无fallback；重启新PID重新initialize成功。真实PG等待超时、取消和迟到结果均无成功receipt。新增缺配置/认证失败各只1次；transport本身无重试，executor最多1次明确瞬态重试。WP07比较/观察、receipt v2、旧receipt拒绝与旧比较invalid回归在本轮完整入口通过。此PASS不覆盖M309授权缺陷 |
| M311 | PASS | 报告/API/运行手册准确限定后端适配器、独立CLI和只读部署；无正式Agent/UI、远程模型strict、模型付费请求或整个P3完成声明 |

主要原始证据（均本轮生成）：dual-clients-cca07c9c.json、authorization-ea31d644.json、reconnect-653b0823.json、timeout-cancel-cbef14be.json、deadline-pg-wait-f1c48050.json、frozen-and-output-c7e6961f.json，以及missing-auth-budget-*.json、grant-final-lock-06745078.json。其完整文件名/哈希在seal.json中。

审核确认的关键边界：

- 服务端token→可信Binding，不接收模型身份/profile；本地客户端Binding与execution比对，应用发布又以当前cookie/capability/revision/manifest/source校验。
- validate_result并非只验UUID/schema：chunk使用source与receipt v2 hydrate核对冻结index、epoch、当前owner/资格、邻块、文本hash/locator与真实正文；spec复用approved并核对case来源和定义。伪正文实测SOURCE_INVALID。
- receipt重放不新增MCP请求/预算，但应用当前权限及来源仍检查；它不是远端失败fallback。CLI独立token与浏览器logout不承诺自动联动，已按各自生命周期判断。
- 未把原生role权限证据当作容器只读挂载证据；静态部署不当运行通过。

## 4. A：必须整改

### ISSUE-001 / 高（P1）/ M309：最终数据库锁等待使token撤销检查失效

**位置**：`backend/app/mcp_server/main.py:50—55`（authorized先authenticate，再可能阻塞owner_lock）；`main.py:84—100`（最终authorized返回后验证资料并返回，没有再读取grant）；应用成功落receipt的关联路径`backend/app/tools/executor.py:165—218`。本问题不是要求网络发送期间实时撤回，而是在最终验证尚未完成、真实锁仍等待时撤销已发生，却仍沿用等待前的授权。

**实际复现**：审核专用audit_server.py只在原ManualTools.execute真实完成后设置屏障，不替换权限校验、数据库查询、SDK或发布逻辑。步骤：

1. 应用执行器预留调用，经HTTP到独立MCP进程，实际读取授权上下文。
2. 屏障处暂停；审核连接持有相同owner advisory事务锁，然后放行服务进入最终authorized。
3. `pg_stat_activity`观察服务只读role的PID **61965**，wait_event_type=Lock、wait_event=advisory；数据库时间`2026-09-18 14:30:05.670906+00:00`。
4. 保持锁期间移除应用token的grant；同token新HTTP请求已返回**401**，证明撤销配置生效。
5. 解锁。在途调用却返回**ok=true、一块正文**；应用tool_calls变为**succeeded，attempts=1，receipt_version=2**。

证据：[test_audit_wp08.py](evidence/wp-08-review-r1/test_audit_wp08.py)、[audit_server.py](evidence/wp-08-review-r1/audit_server.py)、[grant-final-lock-06745078.json](evidence/wp-08-review-r1/grant-final-lock-06745078.json)、targeted.xml/TXT。反例仅运行一次，失败原样保留，未现场修实现。

**影响**：管理员已撤销的服务凭据仍能让在途读取成为应用可重放的成功receipt。当前源码对有效期/allowlist/Binding变化也在锁前取值，存在同类过时授权风险；本轮实际证明的是grant撤销，不冒称所有变体均已实测。

**最小修复要求**：保留原owner/source保护；在最终可能阻塞的锁与来源SQL之后、返回成功之前重新读取当前grant并认证，比较本次授权Binding/allowlist及有效期，明确最终判定点。最终拒绝必须传回应用，不发布成功receipt，不通过重试或local fallback绕过。不能只将首次检查换个位置、降低“执行后校验”契约，亦不要求扩建认证平台或网络硬实时撤回。

**复核**：保留此真实PG锁等待反例；覆盖撤销、到期/权限收窄及必要后续SQL等待窗口。断言无成功正文/receipt、attempt预算不额外增加，新合法凭据正常；只补受影响权限/发布路径，不默认重开整包审核。

## 5. B：非阻断建议及本轮未验证

- 既有owner粗锁、连接/模型冷启动、性能/监控/清理、uncertain处置待办保留；没有当前证据要求本包重构。
- 审核Compose启动器应在明确总deadline内识别本机Docker转发层的预期启动期连接错误并保留时序。它不是本次业务代码整改项；本轮停止追加尝试，容器动态挂载/角色检查待一次定点完成，不能抹去两次失败。
- 不重做模型选型、留出集、未变前端/第二环境，不验证正式Agent/UI/OAuth公网部署/生产恢复。
- 本轮日志与证据按实际生成的28个凭据值扫描无命中，见secret-scan.json；fixture另检查cookie/capability/server日志。具体字节扫描不是对一切潜在秘密泄漏的绝对证明。
- SSE本轮17秒心跳/过期用例通过，但**历史首次超时根因未确认**，不称已修复。
- **E10 NOT_VERIFIED，另行授权后最迟WP-09**；本地E5和真实MCP不等同于真实DeepSeek验证。
- **真实资料门槛NOT_MET，最迟WP-10/真实效果验收前**；所有技术演示使用synthetic，不能当实际维修规格或效果。

## 6. 接受建议和停止点

本轮已完成代码、契约与证据审查及实际完整入口，结论不是仅做哈希核对。**暂不建议接受WP-08**：先最小整改ISSUE-001，再对该窗口和受影响发布路径定点复核；同时完成本轮尚未完成的Compose权限检查并明确其证据版本。无需因非阻断建议重做前端、模型评测或其他工作包。

未修改实现、STATUS、接受记录、旧项目、迁移或Git index，未付费调用/提交/推送；未推进WP-09、未接受整个P3。报告封存后停止，等待用户决定。
