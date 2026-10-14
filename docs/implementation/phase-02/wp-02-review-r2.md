# WP-02 r2复核报告

**结论：CHANGES_REQUIRED；暂不建议接受当前WP-02。**

**整改实施与本次复核由同一任务完成。** 本轮依用户明确指令切换为审核角色，新建源码副本、新venv和新库并重新运行验证；这只能证明本轮运行和证据独立生成，不能替代审核角色独立性。不声称由另一审核窗口或另一审核者完成。本报告未修改业务实现、STATUS或接受记录；发现问题只记录，没有现场修复。

审核开始：2026-09-18T11:04:17.198756+08:00；报告记录：2026-09-18T11:11:58.853725+08:00。范围仅WP-02数据库、领域、本地认证和create/get/list，重点ISSUE-001/002及受影响回归。

## 1. 依据和固定基准

检查E:/、E:/Work、项目及相关目录AGENTS.md，未发现适用文件。读取STATUS、r1审核、r1整改、当前contract、原result、P2实施/验收说明及总指南相关输入、错误、事务、测试契约；read-basis.json保存来源哈希。历史材料只作依据，不把执行者的123/106统计转抄为本轮结论。

- 项目/Git根 `E:/Work/xiutu-v5`，分支main；HEAD不存在（验证退出128）。本轮仍固定完整清单、SHA256和index；root/branch/head/status/cached/unstaged.txt保存实际输出，不仅依赖git diff。
- 整改delivery-hashes.json的567项逐文件匹配；整改报告、交付清单本身和index与final-check一致。连同清单及封存记录共569项纳入本轮baseline.json。没有非预期实现变化。
- 暂存32项及既有工作区变更保持原样；不add/commit/reset/push。Git只用单命令safe.directory与--no-optional-locks，无全局配置修改。
- 结束protection-after.json确认569项均未变；旧项目63项保护哈希未变，Git index未变。历史result/review/remediation/evidence、WP-00/01接受记录、原迁移和共享db_target均在保护范围。
- 两个副本各55项输入均由固定基准复制并逐字节匹配；copy-hashes.json及结束保护确认运行后这些输入没有变化。没有复制旧venv或历史临时目录，也未修改被审测试来制造通过。

关键输入SHA256：

| 输入 | SHA256 |
| --- | --- |
| `scripts/test.ps1` | `37806aaacca1019ae0f94db98b921b807d623fa94c31b332d5b8692e55a8fbbc` |
| `backend/app/domain/schemas.py` | `1ac9c6e48fa7159c3a10a7392ebcceac3c6f7df7b2d6846bb7616a3b4f891070` |
| `backend/app/api/errors.py` | `6a45512370c275b24404c860aa417e306a626278913161bb42b7065a65edca9f` |
| `docs/implementation/phase-02/wp-02-review-r1.md` | `0d3dfd0d985aa00bbae93599412d10e047649f7ecaafd9995034242a07586451` |
| `docs/implementation/phase-02/wp-02-remediation-r1.md` | `04a47d399b99dcd133953c9e9aa435bdc62568fd2781ce53a2747ac0a83c24dc` |
| `docs/implementation/phase-01/wp-01-acceptance.md` | `72af50d9db637503a37469ceef4af0e9bc7f445dfe9603c2b660ac66ba7f261c` |
| `migrations/versions/0001_environment.py` | `87142e6e38b67ffc517b48d2145321219bd11780d8a3b3999c582f6a017f9e51` |
| `migrations/versions/0002_core.py` | `b28ddf8470563bea6de187d381fb81bea3edfeb418002be3dff2007bf4b00d0d` |
| `backend/app/infrastructure/db_target.py` | `e9baeaf17a09851ad945c9ab39fa9b602973c48af436cced978be0d0770d5469` |
| Git index | `c451d6e78b8f29fc818002923a19fb1a888139ced20679ad545f75e9692a9ec6` |

## 2. 当前环境、隔离和独立运行

当前Docker Server29.4.0可用；container.txt确认xiutu-v5/postgres标签、项目compose文件、running及127.0.0.1:5433映射，镜像ID为sha256:00ba258a66dac104fd5171074a0084462a64a1369d8513f3d0a634e2f24d15bc。没有把历史Docker故障当作当前阻塞。没有改配置、重建容器、删除卷或停止未知服务。

- A：`E:\Work\xiutu-v5\.test-runs\wp02-r2-eb3556993d904333bce5867f09f01f28\A`，独立新.venv，首次执行完整入口。
- B：`E:\Work\xiutu-v5\.test-runs\wp02-r2-eb3556993d904333bce5867f09f01f28\B`，独立新.venv，首次清除DB配置执行OfflineOnly。
- 主审核库：`xiutu_test_wp02r2_6bca6d7b2e0b4c7fbcaee4a0`；本轮迁移测试另建`xiutu_test_wp02mig_883ab3a7541e43c9a3cd94b1`。均全新唯一，未复用执行者/r1审核/整改测试库；未DROP DATABASE。
- 本项目忽略凭据仅静默读取并用于新库连接，不读取旧.env、不输出完整连接串。管理员xiutu_dev只用于新建审核库，未迁移它。
- 只清理本轮启动的进程和本轮创建的probe/schema；保留测试数据库和合成记录供复核。未操作旧8014服务。

### 实际执行表

标准命令argv、cwd、开始/结束、退出码在commands.json；实际Uvicorn进程命令/PID另在http-nul-results.json、http-down-results.json。所有输出与JUnit均在本次r2目录，XML使用正斜杠路径。测试统计独立解析为test-statistics.json。

| 命令/检查 | 退出码 | 本轮结果/证据 |
| --- | --- | --- |
| A/B `uv sync --frozen --group dev` | 0/0 | A-install/B-install.txt，两个全新venv |
| `uv pip check --python <A新venv>` | 0 | pip-check.txt |
| A首次 `powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/test.ps1` | 0 | **123 passed，0 failed/errors/skipped，38.51s**；A-first-full.txt、A-full.xml |
| B首次原脚本 `-OfflineOnly`，无DATABASE_URL/TEST_DATABASE_URL | 0 | **106 passed，0 failed/errors/skipped，17.06s**；B-first-offline.txt、B-offline.xml |
| B已有父目录再次OfflineOnly | 0 | 106 passed，16.95s；B-offline-second.xml，哨兵保持且新UUID |
| 普通文件/junction/缺DB完整入口 | 各1（预期） | file-refused/junction-refused/missing-db-refused.txt；目标内容未变 |
| 额外故意失败pytest，通过原OfflineOnly入口 | 1（预期） | 1 failed、106 deselected，4.09s；intentional-failure.xml，证明真实pytest失败未被脚本吞掉 |
| 本轮 `http-nul.py` | 0 | 12种真实HTTP NUL、Unicode/空值和无残留验证；http-nul-results.json及server日志 |
| 本轮 `http-down.py` | 0 | 允许的本地服务上唯一不存在库：实际HTTP GET/POST 503、live200/ready503；无停止服务 |
| `classify-real.py` | 0（完成观测） | 真实22/23/42错误经ASGI；错误密码反例暴露ISSUE-003。退出0不代表错误密码行为合格 |
| `other-inputs.py` | 0 | VIN/fault_codes/Idempotency-Key的NUL均ASGI422且未进入service |

每次pytest保留1条既有Starlette/AnyIO BlockingPortal弃用警告。故意失败探针单列，不计入产品回归失败，也没有被伪装成通过。完整/离线结果来自本轮，不是整改者统计。

本轮复读并复用部分隔离观测脚本，将其复制到新的r2目录再运行，来源见probe-provenance.json；其配置、目录、数据库、进程和结果均属于本轮。没有原地执行会覆盖历史输出的整改脚本。复用脚本不构成另一审核者的独立性，本报告对此不作声称。

## 3. ISSUE-001：RESOLVED

实际检查test.ps1：完整模式先拒绝缺TEST_DATABASE_URL；逐级检查项目路径和.test-runs的ReparsePoint与目录属性；不存在时自行创建；UUID子目录不碰撞、不清理历史；最后exit $LASTEXITCODE。

clean-before.json确认A/B首次调用前均无.test-runs。审核准备程序只创建源码副本和venv，未预建临时父目录；A首次完整、B首次离线都实际成功。这次未使用r1审核时的手工mkdir补救。

B合法父目录的历史哨兵哈希不变，再次运行生成不同UUID目录；普通文件原字节保持，junction指向副本外目录被拒绝且外部哨兵/目录清单不变。反例均只在本轮隔离目录构造，没有动主项目历史.test-runs。

额外test_exit_probe.py故意assert False，借PYTEST_ADDOPTS加入原发布入口并只选此测试；最终PowerShell退出1，证明未隐藏pytest失败。原代码/测试未改动。

当前对项目祖先重解析点一并拒绝，是比仅拒绝外部链接更严格的本地范围限制：README、contract、脚本注释已说明项目路径/junction/symlink拒绝；包括指向项目内的重解析点。这里不认定为缺陷，也不把检查声称为抵御恶意并发替换目录的完整安全保证。

## 4. ISSUE-002：UNRESOLVED（NUL部分已修复，分类兜底仍需整改）

### 已验证有效的部分

共享PersistedText/AfterValidator在四个自由文本字段拒绝实际U+0000，未静默删除/替换；既有strip/长度约束保持。VIN、故障码、幂等key的字符白名单继续有效。

本轮真实Uvicorn HTTP逐一发送四字段×开头/中间/结尾共12种NUL组合。每次独立观察：422 VALIDATION_ERROR、retryable=false；CaseService调用计数和业务引擎begin计数不变；独立数据库连接的case/幂等总行数不变；同key改合法请求201，读取内容相等，ready仍200。计数启动器只包装观察后委托原service，SQLAlchemy事件只计数，不替换校验、服务或事务逻辑。

中文、emoji、组合Unicode、正文换行及字面量反斜杠u0000均保存/读取一致；可选null201、空字符串422。补充ASGI验证VIN/fault_codes/key含NUL为422且不进入service；幂等key NUL未试图通过非法网络报文发送，使用TestClient验证应用边界，明确与12种真实HTTP区分。

响应/日志未出现测试输入秘密、操作员令牌、cookie、CSRF或数据库密码；检查结果及本轮实际密码零匹配见HTTP结果和protection-after.json。

### 异常分类审查

分类使用异常类型、SQLSTATE、connection_invalidated和statement是否为空，没有解析异常文本。DomainError幂等/revision409未改动；不是所有IntegrityError都被改为客户端422。

classify-real.py在本轮自建schema制造真实SQL错误，经register_errors注册的实际FastAPI ASGI处理器返回：22P02→500 DATABASE_DATA_ERROR、23505→500 DATABASE_CONSTRAINT_ERROR、42P01→500 INTERNAL_ERROR，均不可重试、无SQL参数/错误细节；每次UnitOfWork回滚、连接池checkedout=0、哨兵行数保持1。该证据不只是调用分类函数。

池超时、40001序列化失败、40P01死锁、55P03锁不可用、57014查询取消/超时列为DATABASE_BUSY；具有结构化状态依据，不把任意异常文本归类为忙。当前生产路径自身有statement_timeout；不将此清单扩展为所有未来取消操作均应自动重试的业务保证。

连接不可用反例实际仍503，但缺SQLSTATE兜底过宽：错误密码同样满足该分支，见下方ISSUE-003。原NUL503缺陷不能因已修复就掩盖本次明确要求复核的分类风险。

## 5. 新问题 ISSUE-003 — P2：无SQLSTATE的认证失败被标为可重试断库

- 对应：ISSUE-002分类整改及本次第4节“已知确定性配置/认证错误不得无依据归为瞬态”。
- 文件：`backend/app/api/errors.py:42-48`，classify_database_error中state为空、statement为空且orig为DriverOperationalError的兜底。
- 触发：本轮新审核库、同一loopback:5433和xiutu用户；正确配置GET /api/v2/cases得到200，仅把数据库密码替换为进程内生成的随机错误值，再经应用登录和GET读取。
- 实测：同配置的SQLAlchemy真实连接捕获驱动OperationalError，sqlstate=null、statement_is_none=true、connection_invalidated=false；生产应用实际ASGI GET返回503 DATABASE_UNAVAILABLE、retryable=true。正确凭据控制组200。两次使用同一新库和服务，不是Docker故障或目标隔离拒绝。
- 证据：classification-results.json最后两条与classify-real.txt；脚本未解析错误文本进行分类或结论断言，没有保存密码/完整DSN。
- 影响：无SQLSTATE并不能证明是瞬态连接故障。固定错误凭据不会因原样重试变正确，当前语义误导调用方无效重试并掩盖配置问题。该分支也把未来无法识别的连接阶段OperationalError无依据地标为可重试。
- 修复要求：对已知认证/配置错误使用不可重试的安全分类；缺SQLSTATE时不要仅凭OperationalError+无statement断言瞬态。没有可确认的结构化依据时采用保守的未知/不可重试语义；保留确有依据的连接不可用503和已有业务冲突409。不要解析含秘密的异常文本，不要求暴露底层原因或将所有约束错误422。
- 复核方法：新库上正确凭据200、仅改密码的真实失败不可重试，响应/日志无秘密；明确28类认证错误和无SQLSTATE连接兜底均有测试；真正可确认的连接故障仍符合503契约；22/23/未知错误、幂等409、事务回滚和池释放继续通过。必须经过实际应用ASGI处理器，不只测分类函数。

本轮没有修改该代码，也没有为通过而放宽判断或修正文档。

## 6. D201—D203及受影响回归

| 项目 | 结论 | 依据 |
| --- | --- | --- |
| D201 所有权与输入 | PASS（本包输入/owner范围） | 本轮真实NUL校验/无残留与Unicode正例通过；完整入口重跑原认证、跨owner、extra、游标、输入约束。数据库凭据分类另列ISSUE-003，不等于发现业务owner越权 |
| D202 迁移与唯一约束 | PASS | 本轮完整入口真实迁移升降级/sentinel/唯一/FK/活跃run测试通过；更精确真实锁等待提交/回滚证据引用r1，相关实现哈希未变 |
| D203 幂等 | PASS | 本轮原并发/同key重放/异请求409及回滚测试通过；NUL同key合法重试成功；r1实际锁等待额外演练的service/UoW/ORM代码哈希仍一致 |
| 标准测试入口 | PASS | A/B首次无父目录成功；已有目录/历史哨兵/UUID/文件及junction拒绝/缺DB/真实pytest失败退出码均验证 |
| 数据库错误分类 | FAIL | 22/23/未知SQL分支通过，但错误认证无SQLSTATE兜底误报可重试，ISSUE-003 |
| WP-01基础回归 | PASS（技术探针范围） | 共享目标门禁、health、PG/vector、跨进程checkpoint、MCP实际初始化/工具往返/断连在本轮完整入口运行；未使用SQLite或内存saver替代 |
| D204—D214 | NOT_VERIFIED（后续包，不计本包失败/完成） | 未执行WP-03及后续能力 |

r1-reference-scope.json明确列出本轮引用的11份不变代码/测试/迁移哈希（ORM/UoW/db_target/db、service/repository、两迁移及三集成测试）。r1精确并发额外证据只在这些未变部分引用，不用它替代本轮新增分类检查。未改前端，不重复其构建；不声称有新的前端验证结果。

## 7. 保护、剩余项和接受建议

protection-after.json记录开始/结束569项文件、旧63项、A/B各55项输入及Git index均未改变。新增只限本轮review和evidence；final-check.json另封存报告/审核工件哈希及最终保护核对。没有覆盖r1失败、整改统计或原接受记录；STATUS继续IMPLEMENTED_NOT_ACCEPTED，WP-03—17未开始。

没有环境阻塞；ISSUE-001可关闭，ISSUE-002的NUL部分有效但异常分类闭环未完成。**建议仅针对ISSUE-003安排下一次授权整改和复核，当前不建议接受WP-02。** 本轮同任务复核的独立性限制已在报告开头明确，不以新环境运行冒充另一审核者评审。

保留门槛：E10真实DeepSeek仍NOT_VERIFIED，须先授权模型/范围/预算，最迟WP-09；真实资料NOT_MET，来源/许可、精确车型与发动机适配、规格、电路、拆装/复核章节及缺图，最迟WP-10/真实效果验收前补齐。没有付费调用，不把技术探针通过扩展为生产恢复、正式业务MCP或真实维修效果。

**停止：仅交付本报告与本轮证据，CHANGES_REQUIRED。未替用户接受、未修改STATUS、未现场修复、未进入WP-03。**
