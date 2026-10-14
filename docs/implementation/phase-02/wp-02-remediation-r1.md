# WP-02 r1整改记录

记录时间：2026-09-18T10:53:38.456750+08:00。状态：**IMPLEMENTED_NOT_ACCEPTED，r1整改完成，等待独立r2复核**。仅处理r1的ISSUE-001/002；不重新接受WP-02，不进入WP-03。

## 1. 依据与开始基准

检查项目/上级及相关目录AGENTS，未发现适用文件。已读取STATUS、wp-02-review-r1、contract、result和P2实施说明/清单。r1的442项交付及其封存审核工件均匹配，原报告哈希匹配；当前共509项文件固定于evidence/wp-02-remediation-r1/baseline.json。审核新增工件与实现分开，不将原审计证据视为实现变化。

Git根E:/Work/xiutu-v5，main无HEAD（验证128）；暂存/未暂存/未跟踪清单以及cached/unstaged diff保存于同目录。Git index SHA256：`c451d6e78b8f29fc818002923a19fb1a888139ced20679ad545f75e9692a9ec6`。仅命令级safe.directory，不改全局配置、不调整暂存区、不提交推送。

原result、review、WP-00/01接受记录、所有历史证据、两份原迁移、共享db_target、旧项目63项保护文件均保留；没有读取旧.env或旧业务数据库。

## 2. ISSUE-001：测试父目录

修改scripts/test.ps1。先保持完整模式缺TEST_DATABASE_URL明确拒绝，再检查项目路径各级与.test-runs不是重解析点；没有父目录时安全创建，已有路径必须为目录。普通文件/junction明确报错，不删除、覆盖或跟随。每次UUID子目录，拒绝碰撞，打印临时路径并透传pytest退出码，不清理历史目录。

原始反例保留在r1审核的full.txt/xml、offline-clean.txt/xml（92通过10错误、78通过7错误），未改写。

本轮两个全新源码副本与全新venv：

- A：`E:\Work\xiutu-v5\.test-runs\wp02-remediation-2510d69e14b441039183a099b3738b69\A`，首次运行完整入口。
- B：`E:\Work\xiutu-v5\.test-runs\wp02-remediation-2510d69e14b441039183a099b3738b69\B`，首次运行OfflineOnly，清除DATABASE_URL/TEST_DATABASE_URL。

没有复制旧venv/测试目录，也没有由验证程序预建两个副本的.test-runs；clean-before.json记录首次入口前均不存在。prepare.py/run-clean.py为可核对的构造与执行工具，原发布test.ps1在副本实际执行。

A首次123通过，B首次106通过；各0失败/错误/跳过。B第二次执行时保留历史哨兵字节，使用不同UUID子目录。仅隔离副本构造普通文件和指向副本外的junction，均退出1且原文件/外部哨兵不变。缺DB配置完整模式仍退出1。证据：entry-checks.json、file-refused.txt、junction-refused.txt、missing-db-refused.txt。

## 3. ISSUE-002：NUL与数据库异常

修改domain/schemas.py：PersistedText使用共享AfterValidator拒绝实际U+0000，应用于fault_description、vehicle.model、engine_code、engine_family。Pydantic在调用service前返回422 VALIDATION_ERROR/retryable=false，错误字段仅位置/类型，不回显输入。不删除替换字符，不扩大禁止所有控制字符。

其他可写输入核对：VIN仍严格17字符白名单；fault_codes为ASCII字母数字/连字符；Idempotency-Key为ASCII字母数字及._:-并有长度限制，既有规则拒绝NUL。owner/corpus/revision非客户端写字段，故障码规范化保持不变。

修改api/errors.py，分类只看DBAPI异常类型、SQLSTATE、connection_invalidated及是否处于无SQL语句的连接建立阶段，不解析错误文本：

| 情况 | 对外结果 |
| --- | --- |
| 已定义DomainError幂等/revision冲突 | 原409及业务code |
| 连接失效、08类、57P01—03、3D000、无语句的驱动连接失败 | 503 DATABASE_UNAVAILABLE，可重试 |
| 池等待超时、40001/40P01/55P03/57014 | 503 DATABASE_BUSY，可重试 |
| 22类确定性数据错误 | 500 DATABASE_DATA_ERROR，不重试 |
| 23类确定性约束错误 | 500 DATABASE_CONSTRAINT_ERROR，不重试 |
| 未知数据库/程序错误 | 500 INTERNAL_ERROR，不重试 |

确定性DB错误在此层没有足够客户端业务归责信息，因此不一律映射422；合法业务冲突继续显式DomainError。NUL在进入事务前即422。所有错误均不输出原SQL、参数、异常文本、凭据或堆栈。

新增tests/unit/test_wp02_remediation.py共21项：12个字段/位置组合用禁止进入service的独立断言；9种异常通过实际ASGI错误处理器检查code/status/retryable和脱敏，包括数据、唯一/FK、未知SQL/SQLAlchemy异常、连接失败、序列化失败。没有用这些模拟分类替代真实数据库验证。

真实HTTP：http-server.py仅是隔离测试启动器，包装生产CaseService计数并监听业务引擎begin事件，未给产品增加接口。http-nul.py启动独立Uvicorn，用真实JSON分别发送四字段开头/中间/结尾NUL共12项。每项422、VALIDATION_ERROR、retryable=false，service/transaction计数均不增加；独立psycopg查询case和幂等总行数不变，同key改合法内容后201，GET与返回内容相等，ready仍200。中文、emoji、组合Unicode、正文换行以及字面量反斜杠u0000原样保存；发动机字段null201、空串422。http-nul-results.json逐项记录。

真实SQL额外检查：本轮自建schema中非法整数转换SQLSTATE22P02、唯一冲突23505及不存在表42P01分别得到不可重试500的数据/约束/内部分类；UnitOfWork回滚、池checkedout=0，哨兵行数仍1，仅清理该schema。真实数据库不可用使用允许的本地5433上随机不存在数据库，不停止服务；实际HTTP GET/POST均503 DATABASE_UNAVAILABLE/retryable=true，live200/ready503，见http-down-results.json。

响应与服务器日志检查未出现本轮真实token/cookie/CSRF、输入秘密标记或数据库密码。原r1的NUL503失败证据保留。

## 4. 独立环境、命令和实际结果

Docker当前Server29.4.0，xiutu-v5/postgres标签和127.0.0.1:5433映射确认后才建库，见docker-version/container.txt。仅复用本项目服务，无容器/卷重建或删除，无旧8014操作。凭据静默读取本项目被忽略的.local-data配置，在进程内/环境中使用，不输出连接串。

保留的新测试库：`xiutu_test_wp02fix_afb78cde6c224c2789a7f1af`, `xiutu_test_wp02mig_7f1d967ab79942ceb51d7f0e`, `xiutu_test_wp02mig_8435fc447500420d8ba53a7d`。后两个由本轮迁移测试自行新建；没有复用旧执行者/审核者保留库，也未执行DROP DATABASE。

全部标准命令含argv/cwd/起止时间/退出码见commands.json；独立HTTP子进程另在http-*-results.json记录PID和命令。JUnit均正斜杠绝对路径，未覆盖历史文件。

| 命令/检查 | 退出码 | 实际结果/证据 |
| --- | --- | --- |
| A、B分别uv sync --frozen --group dev | 0/0 | A-install/B-install.txt；独立新venv |
| A首次scripts/test.ps1 | 0 | 123 passed，0 failed/errors/skipped，38.09秒，A-full.xml |
| B首次scripts/test.ps1 -OfflineOnly | 0 | 106 passed，0 failed/errors/skipped，16.63秒，B-offline.xml |
| B已有合法父目录第二次OfflineOnly | 0 | 106 passed，16.59秒；不同UUID，历史哨兵不变 |
| 文件/junction/缺DB三个反例 | 各1（预期） | 明确拒绝，entry-checks及txt |
| http-nul.py | 0 | 12个真实HTTP组合、Unicode/空值正反例及3类真实SQL错误 |
| http-down.py | 0 | 独立无效目标GET/POST真实503，未停止数据库 |
| 最终格式整理后A完整入口 | 0 | 123 passed，0 failed/errors/skipped，38.05秒，A-final.xml |
| 最终格式整理后B离线入口 | 0 | 106 passed，0 failed/errors/skipped，16.55秒，B-final.xml |
| ruff check最终修改文件 | 0 | ruff-final.txt |

每次pytest均仅1条既有Starlette/AnyIO BlockingPortal弃用警告。通过数从102/85增加21，来自上述12+9项测试，不要求维持历史统计。完整入口覆盖原认证、不同owner、并发幂等、唯一约束、真实SQL回滚、升降级/外部sentinel、共享门禁、PG/vector/schema隔离、跨进程checkpoint及真实MCP往返/断连；没有静默skip或付费live收集。离线没有DB配置，仍运行真实本地MCP。

首次ruff发现3项import格式问题，已保存ruff-before输出，修正后再格式化并把三份文件同步A/B，最终两入口重新运行；format-only-refresh.json记录前后哈希，verified-copy-hashes.json确认最终代码副本与交付逐文件一致。没有改前端，本轮未重复前端构建。

## 5. 修改清单、保护和剩余项

实现/测试：scripts/test.ps1、backend/app/domain/schemas.py、backend/app/api/errors.py、新增tests/unit/test_wp02_remediation.py。

当前文档：README、tests/README、CHANGELOG、STATUS、wp-02-contract；新增本整改报告和独立evidence。原result/review/历史证据/接受记录不修改。

protection-final.json：开始509项中仅8份授权既有文件变化，无非预期变化；Git index不变，旧63项哈希不变，迁移与共享目标门禁不变，历史报告/接受记录/原始证据不变。delivery-hashes.json保存本轮最终交付文件SHA256，final-check.json封存清单与报告哈希。最终未进行add/commit/reset/push。

无本轮核心执行阻塞；上述仅为执行者整改与验证结果，仍需独立r2确认，不自行作技术审核通过或用户接受结论。WP-02保持IMPLEMENTED_NOT_ACCEPTED；WP-03—17保持NOT_STARTED。

E10继续NOT_VERIFIED，须先取得模型/调用范围/预算授权，最迟WP-09收口；资料门槛NOT_MET，来源/许可、精确车型与发动机、正式规格/电路/拆装/复核及缺图最迟WP-10/真实效果验收前补齐。不付费调用，不宣称生产恢复、正式业务MCP或维修效果。

## 6. r2复核入口与停止

优先读本报告、修改的三个实现文件、新增单测、clean-before/entry-checks、A/B首次及最终JUnit、http-nul/http-down结果、保护清单。审核者可在新副本新venv执行原test.ps1（首次无需mkdir），另用新xiutu_test_*库执行HTTP脚本等效用例；不要直接重跑本证据脚本覆盖其输出，须使用新的证据路径与测试库。

完成后停止，等待独立r2复核及用户决定；不进入WP-03。
