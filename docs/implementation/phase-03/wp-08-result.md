# WP-08 真实业务 MCP 服务与双客户端交付

完成时间：2026-09-18T22:04:22.856389+08:00。状态：**IMPLEMENTED_NOT_ACCEPTED**，等待一次集中审核及用户决定。这里只是执行者实现/自测，不是REVIEW_PASS或用户接受；未开始WP09，不接受整个P3。

现在应用可经真实HTTP调用三项只读资料工具：查手册、取同版本上下文、查已审核规格。独立CLI可访问同一受限资料并核对来源。只读服务不能写比较、观察、预算或审计；后两项业务工具和持久执行记录仍在可信应用侧。合成资料仅用于隔离测试；真实资料门槛未满足时，正式查询允许无结果，不能把测试规格用于维修。

用户可按[运行手册](../../runbooks/mcp.md)直接运行合成双客户端演示或创建自己受限凭据；[协议说明](../../api/wp-08-mcp.md)和[schema](../../api/wp-08-mcp-schemas.json)给出准确输入输出。服务没有前端、Agent或LLM接入。

## 1. 基准与改动范围

已读取用户指定依据、P3 M306—M311及工具权限/预算契约；项目及上级未发现适用AGENTS。开始核对WP07 r2基准/封存报告，接受记录及STATUS差异按用户授权计入，**3082项**文件基准匹配，没有非预期实现差异。r2报告另以其final-check中的SHA256核对。Git main，无HEAD；Git index固定`c451d6e78b8f29fc818002923a19fb1a888139ced20679ad545f75e9692a9ec6`。仅命令级safe.directory，未调整暂存区/提交/推送。

新增：

- `backend/app/mcp_server/`：严格受保护配置、服务端凭据映射、SDK服务、当前来源与输出校验。
- `backend/app/infrastructure/mcp_client.py`：真实SDK connect/discover/call/close与显式transport错误分类。
- `scripts/provision_mcp_role.py`、`scripts/configure_manual_mcp.py`、`scripts/probes/manual_mcp_client.py`：新只读角色、双凭据、独立CLI。
- `deploy/manual-mcp.Dockerfile`、`deploy/compose.mcp-debug.yaml`、`.dockerignore`及新增manual-mcp Compose服务。
- 集成测试`test_manual_mcp.py`、契约测试`test_mcp_transport_contract.py`，本包契约/运行手册/API/schema/hash及独立证据。

必要现有调整：Settings增加mode/config；ContextFactory抽出原current-scope检查给两侧共享（保持owner、revision、manifest/profile、epoch和source规则）；ToolExecutor三只读分支走HTTP并在原发布事务内再验远端来源，预算/比较/取消/receipt逻辑未重建。旧本地测试fixture显式local。mcp1.30.0/httpx0.28.1成为精确直接约束，原版本不升级；uv解析锁并导出requirements。README/工具说明/兼容矩阵/CHANGELOG/STATUS同步当前能力。

**无新迁移**：现有0007_tools足够，0001—0007、共享db_target、历史报告/证据及接受记录保留。MCP内部连接采用独立结构化配置，只有postgres:5432或调试127.0.0.1:5433，拒绝PG环境覆盖；没有放宽原迁移/测试目标门禁。结束保护和实际逐文件差异见protection-final.json、scope-changes.json，旧项目63项与Git index未变。完整运行所用125项源码/脚本/锁文件哈希见full-code-hashes.json，之后无实现变化。

## 2. 设计和兼容变化

SDK `mcp==1.30.0`真实Streamable HTTP `/mcp`，协议`2025-11-25`；stateless JSON响应，每次新尝试initialize→精确三工具schema发现→call→close。不是echo探针或自制JSON接口。MCP schema并非OpenAPI，本包不修改主应用HTTP业务端点。

服务token与cookie/capability分离：受保护文件保存token哈希→actor/case/revision/冻结manifest/profile/allowlist/期限，CLI与应用独立token。工具参数不能指定授权身份或提高预算。每次HTTP请求及业务执行前后检查；Host/Origin精确，默认无浏览器Origin许可；无Origin CLI也认证；Mcp-Session-Id请求拒绝。当前grant/资料撤销不能通过旧UUID或hash绕过。

只读服务复用ManualTools/WP05/06逻辑与owner advisory事务锁，检索推理不持事务，输出前重新检查；专用数据库role只授必要表SELECT、不授审计/预算表。应用侧保留原原子预算预留及receipt发布，先验证cookie/capability/资料，远端结果再核对模型schema、大小、真实文本/hash/locator、适配及规格来源。历史receipt按WP07当前授权安全恢复，不重新执行或新增MCP尝试；这不同于远端失败fallback。

默认ToolExecutor **remote_mcp**，必须有匹配execution范围的受保护客户端配置；显式local留测试。仅三只读工具远端，比较/观察仍应用本地。每次transport尝试由执行器记预算（搜索双计数），客户端不再重试；仅明确连接/读断连最多重试1次。认证/schema/超时等不自动重试。默认10秒，有界客户端等待和应用最终DB deadline/取消守卫；CPU只读工作可能晚结束，但不能发布迟到成功receipt。未实现硬实时抢占或通用远端任务恢复。

## 3. 本轮实际验证（不是审核结论）

| 项目 | 执行结论 | 真实证据与限制 |
| --- | --- | --- |
| M306 | PASS | 独立Uvicorn MCP进程＋应用SDK客户端＋独立CLI子进程；真实initialize/list/call，protocol2025-11-25；dual-clients-*.json、server-*.log及集成测试 |
| M307 | PASS | SDK发现恰好三个只读工具、精确输入/逐工具输出schema；compare显式TOOL_FORBIDDEN，其他名称同一allowlist门禁；协议漂移反例17项的一部分 |
| M308 | PASS | 三项工具应用与CLI data/provenance一致，包括chunk/version/index/hash/locator及规格evidence/version；真实本地E5、真实PG/上传解析索引，不以测试向量替代；重放不再扣预算 |
| M309 | PASS | 错/过期token、错误/null Origin、Host、伪session、scope冲突、额外owner/profile、跨corpus、伪客户端case映射、撤销/注销拒绝；固定旧索引仍合法时可用；角色在关闭default readonly后写/DDL/审计读取仍42501；Compose原文/模型写入OSError30 |
| M310 | PASS | 只停止本轮MCP进程后明确TOOL_TRANSIENT，无fallback；失败call attempts=2，总/search预算加2；新进程重新initialize后成功。真实PG owner锁等待使客户端/应用超时，无成功receipt；取消先记录后返回也不能发布 |
| M311 | PASS（边界） | 仅后端执行器适配及独立CLI，无业务页面、Agent、观察写入或远程模型strict验收；原WP01 echo结果只是完整回归旧探针，不作上述业务证明 |

输出篡改/错误schema/大小/发现写工具均拒绝。固定旧索引通过真实重建active切换验证，未偷偷使用新active。实际服务是只读角色；通过真实SQL关闭只读默认后仍验证GRANT拒绝，未把`default_transaction_read_only`单独当权限证明。应用预算/审计属于读写应用连接，不授给MCP。每个新测试owner/key独立。

真实Compose运行：新增容器`xiutu-v5-manual-mcp-1`，镜像`sha256:19557fb97b20ca5cc263a7f63dc14fd085a6dfe77944b57ffe9881d6001ad054`；Python3.12.10-slim-bookworm基础digest在Dockerfile固定。Docker Desktop4.69.0/Engine29.4.0，项目postgres保持healthy和127.0.0.1:5433。容器内部postgres:5432专用role，非root/rootfs只读，三个bind mounts RW=false；实际三工具与health正常，原文/模型写入errno30。验证后只停止本轮新MCP容器，保留供检查；未停止postgres/未知服务、删除库/卷。详见compose-results.json、compose-commands.json、docker-resources.txt。

## 4. 命令、统计与失败保留

所有命令cwd=`E:/Work/xiutu-v5`；完整命令数组、起止、退出码见各label.json，输出同名.txt，测试统计见XML/test-summary.json。测试库`xiutu_test_wp08_6668be276b1f46b8`及全新UUID临时目录；迁移回归自行另建新测试库，未复用旧验收库。原文、role/token配置仅本轮受保护/忽略目录；没有读取旧.env或导入私人手册。

| 运行 | 命令概要/证据 | 实际结果 |
| --- | --- | --- |
| create / migrate | prepare_database.py新唯一库；alembic upgrade head | exit0/0，仅准备0007现有环境 |
| targeted-1 | pytest tests/integration/test_manual_mcp.py（首4例） | 4通过，exit0，79.20秒 |
| targeted-2 | 2新增定点：冻结/输出＋真实DB等待deadline | 1通过、1失败，exit1，32.07秒；失败为测试误用AuthStore.logout，业务断言此前已通过 |
| frozen-fix | 仅修为现有revoke接口后重跑该失败例 | 1通过，exit0，18.77秒；不放宽断言 |
| protocol-contract | 独立协议/schema/目标/错误反例 | 17通过，exit0，1.48秒；受控替身只证明错误契约 |
| compose / compose-fixed | compose-check.py运行本轮新增服务 | 首次验证脚本字符串语法错误exit1、尚未启动；保留初稿；修正后exit0真实Compose成功 |
| configuration | 实际configure_manual_mcp脚本、ACL和重复拒绝 | 首次exit0，新角色/独立凭据/范围匹配；再次明确exit1，全部文件hash未变 |
| full | scripts/test.ps1首次完整入口 | 0测试实际执行、1收集错误，exit2；两个新测试文件同名，XML中的error testcase是收集占位，不算通过实例 |
| **full-final** | **powershell -NoProfile -ExecutionPolicy Bypass -File scripts/test.ps1** | **301通过、0失败/错误/跳过、1警告，exit0，802.51秒**；2026-09-18T21:45:44.403033+08:00—2026-09-18T21:59:09.664524+08:00 |
| lock / dependency / lint | uv lock --check --offline；uv pip check；ruff限定改动文件 | exit0；锁97包、安装兼容96包（含开发环境差异），没有第二venv验证 |

首次完整入口没有执行业务测试，因此仅将契约测试重命名为test_mcp_transport_contract.py后运行尚未完成的完整测试。未通过循环重跑/放宽超时或断言取得成功；没有重跑前端、模型选型/留出集或第二环境。完整首次源码与最终源码基准分别保留，差异只是该测试路径。最终完整301包含旧包当前回归及本包23个新实例，**不能与4/17等重复定点统计累加成覆盖总数**。

唯一pytest warning为既有Starlette TestClient对anyio BlockingPortal别名的弃用提示。初次uv editable重建提示跨盘hardlink回退copy、镜像构建pip提示为root安装发生于build阶段，runtime为10001；均有原输出。初始沙箱Docker管道访问受限，经正常权限流程后可用，不误判为引擎故障。首次读取大基准JSON的GBK解码失败在写入前发生，改UTF8后核对匹配才实施。

凭据检查：本轮server日志逐fixture断言token/DB密码/cookie/capability未出现；secret-scan.json再以运行时实际凭据扫描证据，无命中。它是具体字节检查，不声称覆盖所有可能秘密。没有保存原文/观察全文到tool_calls；三工具返回的有限合成chunk正文属于输出证据。

## 5. 用户验证与保留项

[运行手册](../../runbooks/mcp.md)的`test_real_dual_clients_and_readonly`演示会创建合成资料→真实worker解析/审核/索引→新case/证据/合成规格→双客户端三工具→只读拒绝。若已准备授权case，可使用配置生成脚本和独立CLI，无需LLM；每个输出必须新路径。Compose默认没有宿主端口，调试需显式loopback override。不要把secret写入示例、URL或模型参数。

当前未发现必须继续修复的本包实现阻塞；此表仅执行者自测，仍等待集中审核。保留：

- 同任务参与前包实施/审核/整改的历史流程限制，本次不自行审核或记录用户接受。
- 旧receipt返回RECEIPT_UNSUPPORTED、旧比较COMPARISON_INVALID及不清除needs_review要求保持。
- owner粗锁、模型冷启动/规模、监控/清理、uncertain处置、观察后续写入及共享连接优化是既有或本包非阻断待办；没有压测、OAuth/公网TLS或生产高可用验收。
- CLI独立credential生命周期与浏览器cookie分开，管理员分别轮换/撤销；当前单机可信配置，不提供面向不可信管理员的控制平面。
- SSE本轮17秒心跳/过期用例通过，**历史首次超时根因仍未确认**。
- E10 **NOT_VERIFIED**，另行授权后最迟WP09；本地embedding/MCP不代表真实DeepSeek验证。
- 真实资料 **NOT_MET**，最迟WP10/真实效果验收前补齐。合成标签/规格不是实际维修标准，检索不等于诊断或维修效果。
- 无付费请求、私人资料上传、正式Agent/UI/观察写入或WP09实施，不接受整个P3；旧项目、历史证据、接受记录、0001—0007及Git index保留。

报告与交付清单封存后停止，等待用户安排一次集中审核。
