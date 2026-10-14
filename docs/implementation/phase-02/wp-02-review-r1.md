# WP-02 独立审核 r1

**结论：CHANGES_REQUIRED。暂不建议接受当前 WP-02；需修复下列两项 P2 问题后独立复核。**

审核仅覆盖数据库、领域、本地认证和会话 create/get/list。没有修改实现、STATUS、接受记录或原始证据，没有替用户接受，没有推进 WP-03。D204—D214 为后续包，不计本包失败或完成。

## 1. 依据、审核输入与保护

审核开始：2026-09-18T10:14:12.447898+08:00；报告记录：2026-09-18T10:32:26.724066+08:00。

已核对项目/上级及相关目录 AGENTS.md，未发现适用文件。读取 STATUS、wp-02-result、wp-02-contract、WP-01 acceptance/review-r2、旧项目 P2 实施说明/验收清单、总指南第4/5/7节及WP-02、README；契约作为被审对象，与上级要求及实际代码/数据库交叉核对，不以执行者 PASS 作为审核结论。

- 项目绝对路径与 Git 根：`E:/Work/xiutu-v5`；分支 `main`；HEAD 不存在，验证退出128。旧项目 `E:/Work/v4-double`，旧项目保护范围按既有63项清单检查。
- 开始32项暂存（含历史暂存版本），5项已跟踪工作区修改，其余大量未跟踪交付。完整列表、cached diff、未暂存 diff 分别在本证据目录 `status.txt/cached.txt/unstaged.txt`；没有仅用diff判断新文件。
- WP-02原 `delivery-hashes.json` 的441项全部匹配；把该清单本身也纳入本轮基准，共442项。`baseline-before.json`保存逐文件SHA256、Git命令输出、旧项目63项和原JUnit迁移核对。
- 对照WP-02原 `baseline.json` / `protection-final.json`：301项历史保护文件当前一致，包括WP-00/01 result/review/remediation/acceptance、0001迁移和共享db_target；旧项目63项一致。没有把WP-02已声明的实现/STATUS变更误报为并行修改。
- 结束 `protection-after.json`：442项均未变化，301项历史保护均未变化，旧项目63项均未变化，Git index不变；新增Git可见文件仅本次审核工件。报告写入后再以 `final-check.json`封存最终核对及审核工件哈希。
- Git仅单次 `-c safe.directory=E:/Work/xiutu-v5`，配合 `--no-optional-locks`；没有add/commit/reset/push或全局配置修改。

关键SHA256（完整清单见baseline-before.json）：

| 文件 | SHA256 |
| --- | --- |
| `docs/implementation/phase-02/wp-02-result.md` | `24487c2d851146ecb94d5c04f2bf6224e574f19883d57fb2655fc61da00e66b3` |
| `docs/implementation/phase-02/wp-02-contract.md` | `4f257eaab4b63d026ded4903ef5d0544be9c7ee757bdf46387f3e32a6bc6c1a4` |
| `docs/implementation/phase-01/wp-00-review-r1.md` | `842f085cbffd50dfb92177a7042597b52ff0b751203a341edc0e43227a694b9b` |
| `docs/implementation/phase-01/wp-00-acceptance.md` | `c5af6d91211f295252633a4c5c64229f2368010255b1809ae06c6dc7b3c524db` |
| `docs/implementation/phase-01/wp-01-review-r2.md` | `047642214be5e48a75df5a0719dfbdf673123b428a50a11f7f38b3d63dc08869` |
| `docs/implementation/phase-01/wp-01-acceptance.md` | `72af50d9db637503a37469ceef4af0e9bc7f445dfe9603c2b660ac66ba7f261c` |
| `migrations/versions/0001_environment.py` | `87142e6e38b67ffc517b48d2145321219bd11780d8a3b3999c582f6a017f9e51` |
| `backend/app/infrastructure/db_target.py` | `e9baeaf17a09851ad945c9ab39fa9b602973c48af436cced978be0d0770d5469` |
| Git index | `c451d6e78b8f29fc818002923a19fb1a888139ced20679ad545f75e9692a9ec6` |

审核环境：`E:\Work\xiutu-v5\.test-runs\wp02-review-07fbd93371d44882bd390d094b75c1e2\snapshot`；全新venv：`E:\Work\xiutu-v5\.test-runs\wp02-review-07fbd93371d44882bd390d094b75c1e2\venv`。65项输入文件按原始字节复制，`snapshot-inputs.json`记录来源哈希。未复制原venv、node_modules、.env、业务库。额外审核脚本放本轮evidence；子进程cwd为审核副本。少量外层审核脚本由工具默认cwd `E:/Work/v4-double` 以绝对路径调用，但只读取明确保护文件，全部写入均显式定位新项目审核目录/审核临时目录，没有写旧目录。

## 2. 环境与独立执行

当前Docker检查均退出0：Server29.4.0、Desktop4.69.0、context desktop-linux。`container.txt`确认Compose project=xiutu-v5、service=postgres、配置为本项目deploy/compose.yaml，127.0.0.1:5433映射5432。仅复用该容器，没有重建、停止、删除卷或改全局设置。

镜像：`pgvector/pgvector:0.8.2-pg16-bookworm`；digest `sha256:00ba258a66dac104fd5171074a0084462a64a1369d8513f3d0a634e2f24d15bc`。本轮实际 PostgreSQL16.14、vector0.8.2、最终revision0002_core；见docker-version/container/image及extra-db.json。

凭据仅静默读取新项目被忽略的 `.local-data/wp01-postgres.json`，在子进程环境/进程内构造连接串；无旧.env读取、无凭据或完整连接串进入命令日志。实际新增并保留审核库：

- `xiutu_test_wp02r1_8e470587ab064adc8f2113af`：本轮完整测试及额外事务/HTTP。
- `xiutu_test_wp02mig_c39e5174a531406f976954c1`：首次完整入口内迁移测试自建库。
- `xiutu_test_wp02mig_d0ea68ca63f94a1c97880f51`：补建临时父目录后完整入口内迁移测试自建库。
- `xiutu_test_wp02r1mig_a2f28d19688c43deafeee3`：额外实际HTTP升降级及输入反例。

未复用执行者WP-01/WP-02保留测试库。管理员xiutu_dev仅用于创建上述新库；没有DROP DATABASE。只清理本轮创建的probe/sentinel schema及自己启动的子进程；未知服务和旧8014未操作。

### 2.1 实际命令、退出码与统计

`commands.json`保存安装/标准入口/前端的实际argv、cwd、起止时间和退出码；对应txt是本轮原始输出。额外脚本的逐项时间、独立进程argv/PID、数据库锁信息分别在 `extra-db.json`、`http-results-v2.json`、`http-migration-input.json`；见 `additional-invocations.json`。命令中的PYTHON为workspace.json记录的审核venv解释器，不是旧项目Python环境。

| 执行 | 退出 | 本轮结果及证据 |
| --- | --- | --- |
| `uv sync --frozen --group dev`，新UV_PROJECT_ENVIRONMENT | 0 | frozen-sync.txt；Python3.12.10新环境 |
| `uv pip check --python <审核venv>` | 0 | pip-check.txt；versions.txt保存完整版本 |
| `uv export --frozen --no-dev --no-emit-project` | 0 | requirements-parity.json：除生成命令注释外与交付requirements相同 |
| 首次实际 `powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/test.ps1` | 1 | **92 passed / 0 failed / 10 errors / 0 skipped**，24.47s，1 warning；full.txt/xml |
| 未配置DB的首次 `scripts/test.ps1 -OfflineOnly` | 1 | **78 passed / 0 failed / 7 errors / 0 skipped**，6.66s，1 warning；offline-clean.txt/xml |
| 只在审核副本新建 `.test-runs` 父目录后，再执行原完整脚本 | 0 | **102 passed / 0 failed / 0 errors / 0 skipped**，37.65s，1 warning；full-with-temp-parent.txt/xml |
| 同样前提，清除DATABASE_URL/TEST_DATABASE_URL后原OfflineOnly | 0 | **85 passed / 0 failed / 0 errors / 0 skipped**，16.50s，1 warning；offline-with-temp-parent.txt/xml |
| 无DB配置执行完整脚本 | 1（预期） | full-missing-db.txt：明确拒绝，不静默skip |
| `extra-db.py`（实际SQL、锁等待、commit失败及分页） | 0 | 8组结构化验证，extra-db.json；不是pytest统计 |
| `extra-http-v2.py`，真实Uvicorn | 0 | 登录→创建→读取→列表→重放/冲突→退出、两个owner、安全反例、重启/过期/DB不可用；http-results-v2.json及server-v2日志 |
| `extra-migration-input.py` | 0 | 实际HTTP迁移健康变化与4个NUL输入复现；脚本退出0仅表示观测断言成立，**不表示NUL行为合格** |
| `npm.cmd ci` | 0 | npm-ci.txt；实际preinstall门禁，Node24.14.0 |
| `npm.cmd run test:runtime` | 0 | 2 passed，0 failed/skipped；node-gate.txt |
| `npm.cmd run typecheck` / `npm.cmd run build` | 0 / 0 | typecheck/build.txt，实际pre生命周期检查；Vite27modules |
| 实际Node检查入口及npm pretypecheck模拟18.0.0 | 1 / 1（预期） | node-unsupported-entry/lifecycle.txt：明确要求24.14.0，不修改全局Node |

所有pytest运行仅1条既有Starlette/AnyIO `BlockingPortal` 弃用警告。数字来自本轮XML解析，见 `test-inventory.json`，没有转抄原102/85。完整入口实际收集unit/integration/contract/probes；离线收集unit/contract及真实MCP，未收集数据库integration、PG/vector/checkpoint或付费live测试。JUnit使用正斜杠绝对路径，未发生本轮shlex路径损坏。原 `junit-relocation.json`四个最终XML的SHA256全部匹配，原证据未移动或改写。

首次完整命令的原始输出/退出1已保存后，外层记录程序向GBK控制台打印错误片段发生UnicodeEncodeError；它不是产品故障，也没有改变已保存的JUnit。后续记录显式UTF-8。首次额外HTTP审核脚本错误地构造18字符合成VIN，被正确422拒绝；保留 `extra-http.py/http-results.json/owner-*-server.txt`，新建v2脚本纠正审核数据为17字符，不修改被审测试或覆盖首次记录。Windows `Popen.terminate`造成本轮已验证子进程退出1是审核清理行为，不计服务自发崩溃。

## 3. 逐项代码、契约与真实验证结论

| 项目 | 结论 | 独立依据 |
| --- | --- | --- |
| D201 所有权与输入 | **FAIL** | owner只来自认证，两个不同UUID实际HTTP读取404、列表隔离、跨owner游标400、同owner多cookie稳定均通过；嵌套extra/伪造corpus等拒绝。但4个持久化文本字段接受NUL后误报可重试503，见ISSUE-002 |
| D202 迁移与唯一约束 | **PASS** | 空库/0001→0002/降级再升级实际执行；冻结迁移与ORM DDL相等；真实锁等待下仅一个活跃run；完整真实FK/唯一/CHECK测试通过 |
| D203 幂等 | **PASS** | 规范化同请求原201/原响应，异请求409，不同owner同key独立；实际事务锁等待、先行事务提交/回滚及10秒超时均验证；没有空占位响应或失败事务继续查询 |
| 安装/干净测试入口 | **FAIL** | frozen安装及依赖导出相符；但README所述原测试入口在新副本缺临时父目录失败，见ISSUE-001；补建父目录后通过不能抹去原失败 |
| 认证/权限 | PASS（本包本地范围） | 严格Origin、JSON、Cookie HttpOnly/SameSite、TTL、轮换/logout/重启失效；缺/坏/过期cookie、缺/错CSRF、缺/错/null Origin与重放重新检查实际验证 |
| HTTP/数据库异常 | 部分FAIL | 真实库不可用统一503、无敏感回显；输入错误误分类见ISSUE-002；真实commit/锁等待/SQL错误释放和回滚通过 |
| health/迁移衔接 | PASS | 同一实际Uvicorn随空库503、0001为503、0002为200、降级503、重升200、wrong503、恢复200；shared EXPECTED_REVISION=0002_core |
| WP-01共享基础回归 | PASS（技术探针） | 本轮共享门禁反例、向量排序、schema隔离、Postgres跨进程checkpoint、真实MCP初始化/工具/断连、HTTP启动等待均独立重跑 |
| 前端壳/Node | PASS | 独立副本ci/typecheck/build；实际入口和生命周期拒绝不支持版本；没有新增业务工作台 |
| D204—D214 | NOT_VERIFIED（后续包，不纳入本包判定） | 不要求本包实现任务/资料/索引/规格等，也不宣布其完成 |

### 3.1 迁移、领域与分层

`0002_core`正确衔接未改动的`0001_environment`。迁移持有自身冻结Table定义，不导入可变app metadata；`extra-db.py`以PostgreSQL方言编译CreateTable/CreateIndex比较两者，完全相等。`database-inventory.json`为本轮真实八表列/类型/可空/默认/CHECK/FK/唯一/索引内省。

UUID、timestamptz、revision/graph_epoch非负、状态CHECK、FK RESTRICT、jobs.run_id唯一、文档内hash唯一、版本内chunk ordinal唯一均落实。runs部分唯一准确限定非空case_id及queued/running/cancel_requested，waiting_input不占槽。run_events使用bigint identity是总指南明确例外。owner为外部认证UUID，本包没有accounts表，不虚构外键。降级仅本迁移八表及其对象，vector与外部sentinel值保留。active_index_id随WP-05与index_versions/FK一起补；其他未建业务表已明确分期，不以缺后续能力否决本包。

CaseRepository只有create/get/list；路由不拼SQL，domain不导入FastAPI/SQLAlchemy。corpus_manifest服务端固定空数组、拒绝客户端传入，不伪装已授权资料。active_run=null和report_gate.NOT_IMPLEMENTED边界已明确，不能当作正式任务查询/报告门禁。Create无expected_revision是创建revision0的衔接；现有service get与领域策略的revision冲突测试通过，没有要求增设更新API。

所有连接入口继续共享db_target校验并重建驱动参数；新make_engine没有原始DSN旁路。迁移/test fixture/graph worker/prepare_database/健康池与业务引擎均遵守loopback:5433和test/development范围；query覆盖、hostaddr、service、多主机、缺参、PG环境变量等反例在连接前拒绝。拒绝所有非空PG*是已有明确本地限制，本轮没有放宽门禁。

### 3.2 事务与真正并发的证据

额外审核在SQLAlchemy执行器事件中，**A真实INSERT成功后**持有事务屏障；B在独立连接执行同一约束冲突INSERT，观察连接查询pg_stat_activity/pg_blocking_pids，确认B wait_event_type=Lock、wait_event=transactionid且blocker为A PID后才释放A。不是仅启动线程或串行调用。详见extra-db.py及extra-db.json。

- 幂等提交：A PID46208、B46209，B等待A；提交后两者201及同一完整响应，只1个case。
- 幂等回滚：A46209、B46208；A受控异常回滚，B成功取得键并提交完整响应，只1个case。
- 活跃run提交/回滚各形成真实锁等待。提交路径B唯一冲突；回滚路径B成功；最终各1个run。
- 当前真实事务隔离为read committed，符合ON CONFLICT等待后下一条SELECT读取已提交响应的依赖；不声称已支持REPEATABLE READ或更改服务端默认隔离的部署。
- 超时路径B真实等待10秒触发OperationalError，A随后回滚；重试可创建，连接池checkedout=0。
- 自建临时schema的延迟FK在COMMIT才触发真实IntegrityError；UnitOfWork finally释放连接，行回滚，后续SELECT1成功。不是mock commit异常。
- 完整集成测试另验证真实SQL错误、FK、唯一键、状态及数值边界。所有权分页额外11行同一事务相同created_at，按UUID次序用limit1/3/50遍历，无重复遗漏；篡改和跨owner游标拒绝。

### 3.3 认证、安全、OpenAPI与回归边界

操作员令牌无可用默认值，SecretStr隐藏配置表示；用户显式环境注入。内存会话按cookie SHA256存储，随机cookie/CSRF，单进程锁，默认一小时。README启动为单worker，与实现一致；本包不要求完整账号/多worker共享会话。两真实Uvicorn实例分别配置不同owner UUID，同一操作员轮换cookie后owner不变，不将两个同owner cookie冒充越权测试。

OpenAPI有SessionCookie、写入时CSRFToken、required Origin/Idempotency-Key及错误envelope，与正常HTTP一致；NUL异常属于输入/错误边界缺陷，并非OpenAPI主路径全部不符。实际HTTP验证了归一化VIN/故障码、空白、布尔year、额外字段、limit0/51、分页/重放/409。HTTPS Secure分支由本轮单测+代码检查覆盖；没有部署真实TLS反向代理，不宣称浏览器生产部署安全已验收。

本轮已执行分支的错误响应与服务器输出未出现实际token、cookie、CSRF、合成VIN原文、数据库密码或SQL参数；每个server日志在持有本次秘密时检查后脱敏保存，结果secret_matches=[]。此结论限定检查过的分支，不是对所有将来未知异常的绝对保证。

本轮Postgres checkpoint输出记录两个不同进程PID、A正常退出后B恢复相同workflow、count仍1及错误workflow退出4；vector合成排序[1,2,3]、schema创建清理前后清单相同；MCP确经独立服务器与SDK Streamable HTTP，断连叶异常为McpError/ConnectTimeout。这里只证明技术探针，不等于正式业务MCP、生产恢复或维修能力。

## 4. 必须整改问题

### ISSUE-001 — P2：干净副本的标准测试入口未创建临时父目录

- 对应：本轮独立运行第6/7项、总指南测试入口约定；影响WP-02可复现验证，不否定已运行成功的数据库约束。
- 文件：`scripts/test.ps1:5`、`:13`；README安装/运行步骤；bootstrap不创建该目录。
- 触发/复现：从交付文件复制到全新目录（不复制被忽略的.test-runs），完成frozen安装，按README执行 `scripts/test.ps1 -OfflineOnly`；pytest为嵌套basetemp执行mkdir而父目录不存在，WinError3。完整模式同样失败。
- 实际结果：full.txt/xml为92通过10 errors；offline-clean为78通过7 errors。没有测试断言失败，却不能正常执行完整验证。执行者工作区预存目录掩盖了这个前置依赖。
- 影响：新安装/新审核副本按文档命令不能直接复现；历史通过统计不足以证明干净环境入口可用。
- 修复要求：脚本安全确保本项目.test-runs父目录存在/确为目录，保留每次唯一子目录及退出码，不删除历史目录、不依赖手工预建。
- 复核：另一全新副本、新venv，初始不存在.test-runs；不额外手工建目录，分别真实运行完整/OfflineOnly，核对0 errors/skip及历史目录不动。当前审核只补建了副本父目录以继续检查，没有修改被审实现。

### ISSUE-002 — P2：不支持持久化的NUL输入被误报为可重试数据库故障

- 对应：D201输入、总指南7节422与统一错误/重试语义、本次异常边界审查。
- 文件：`backend/app/domain/schemas.py:24`、`:26-27`、`:42`；`backend/app/api/errors.py:42-45`。
- 触发：已认证且合法Origin/CSRF/唯一key，提交JSON中间含转义`\u0000`的fault_description，或vehicle.model/engine_code/engine_family。可用 `{"vehicle":{"model":"Synthetic"},"fault_description":"synthetic\u0000input"}`。不需要特殊数据库状态。
- 实际结果：四个字段均通过当前结构/长度验证，进入数据库后失败；HTTP503 / DATABASE_UNAVAILABLE / retryable=true。与此同时ready=200；该请求不可能靠重试相同输入成功。证据 `http-migration-input.json` 的四条nul-field，以及原始migration-health-server-migration.txt；首次独立发现见http-results-v2.json。
- 影响：客户端把确定性输入错误当成数据库暂时故障，产生无意义重试并掩盖真正原因；API应拒绝不支持的文本或明确定义安全表示，而不是宣称DB不可用。
- 修复要求：在进入事务前验证所有当前可写持久化文本，拒绝NUL并返回不回显输入的422 VALIDATION_ERROR/retryable=false；不要静默删除字符改变请求语义。核对SQLAlchemy异常映射，避免可确定的输入/约束错误一律当瞬态503，同时仍保持秘密不泄露。
- 复核：四字段分别实际HTTP发送转义NUL，检查422、retryable=false、不写case或幂等占位、同key合法请求可创建、ready仍200、日志/响应不含秘密；正常Unicode和合法输入仍成功。
- 已确认没有数据损坏：每个反例事务回滚，幂等表无该key，同key改成合法请求随后201。孤立Unicode surrogate由Pydantic422拒绝，没有另报问题。

无证据表明当前Docker阻塞或所有权绕过。上述是代码/入口问题，不应通过修Docker、放宽目标门禁或改验收指标解决。

## 5. 未验证项、限制与接受建议

1. E10真实DeepSeek仍NOT_VERIFIED。没有真实/付费模型请求；先另取模型、范围与预算授权，最迟WP-09收口。
2. 真实资料门槛NOT_MET：来源/许可、精确车型与发动机适配、正式规格、电路、拆装/复核章节和缺图；最迟WP-10/真实效果验收前补齐。私人备份许可不等于公开分发许可，教学/合成资料不作为正式维修依据。
3. 不验证后续任务执行/租约/fencing/SSE、正式诊断、报告或维修效果；不声称生产恢复保证。仅单进程认证；真实TLS/多worker部署不在本包交付范围。
4. 独立测试主要路径及真实数据库并发已通过，但不能替代上述输入/复现缺陷整改。建议仅整改ISSUE-001/002并补必要回归，保留r1原始失败证据，然后安排r2独立复核，再由用户决定接受。

**停止：CHANGES_REQUIRED；未修改STATUS为ACCEPTED，未实施整改，未进入WP-03。**
