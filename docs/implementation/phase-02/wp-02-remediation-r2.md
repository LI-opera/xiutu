# WP-02 remediation r2：仅ISSUE-003最小修正

记录时间：2026-09-18T11:31:17.706807+08:00。WP-02保持**IMPLEMENTED_NOT_ACCEPTED**。本报告为执行结果，不是审核结论；完成后交不同审核窗口仅复核本次差异，不在同一任务自行生成独立审核通过或接受记录。

## 1. 基准与范围

读取适用AGENTS（项目/上级及相关目录未发现）、wp-02-review-r2、当前contract、api/errors.py和test_wp02_remediation.py。对照r2 baseline/final-check：既有交付、审核工件和报告哈希均匹配，无非预期变化。开始共629项Git可见文件固定于本证据目录baseline.json。

工作目录/Git根E:/Work/xiutu-v5，main无HEAD（验证128），完整暂存/未暂存/未跟踪列表及cached/unstaged diff已保存。不因无HEAD跳过基准；safe.directory仅单命令，不调整暂存、不提交推送、不改全局配置。

Git index始终为`c451d6e78b8f29fc818002923a19fb1a888139ced20679ad545f75e9692a9ec6`。STATUS不改，状态仍IMPLEMENTED_NOT_ACCEPTED；原result/review/remediation、历史失败证据和接受记录均保留。

## 2. 唯一改动范围与规则

仅修改以下三份既有文件：

1. `backend/app/api/errors.py`：调整classify_database_error连接阶段分类。
2. `tests/unit/test_wp02_remediation.py`：更新2个原预期，新增10个结构化分类反例/正例，仍经注册的ASGI处理器检查状态、code、retryable和脱敏。
3. `docs/implementation/phase-02/wp-02-contract.md`：同步当前重试语义及本整改链接。

另新增本报告和evidence/wp-02-remediation-r2证据。NUL校验、目录准备脚本、两份迁移、共享db_target、业务service/repository、前端、README、CHANGELOG和STATUS均未修改；没有借本次扩展工作包。

最小规则变化：

| 分类 | HTTP/code | retryable |
| --- | --- | --- |
| SQLSTATE 28类明确认证失败 | 503 DATABASE_UNAVAILABLE | false |
| SQLSTATE 3D000数据库不存在 | 503 DATABASE_UNAVAILABLE | false |
| 无SQLSTATE、无SQL语句的驱动OperationalError（连接阶段） | 503 DATABASE_UNAVAILABLE | false |
| 其余有依据的连接失效、08类、57P01—03 | 原503 DATABASE_UNAVAILABLE | true |
| 池超时、40001/40P01/55P03/57014 | 原503 DATABASE_BUSY | true |
| 22类/23类/未知程序错误 | 原500数据/约束/内部错误 | false |
| 已定义幂等/revision冲突 | 原409业务错误 | false |

前3条保守分支优先于connection_invalidated，避免明确认证/缺库或缺证据的连接阶段错误被失效标志重新包装为可重试。503仅说明本次服务不可用，不代表原样重试必定有意义；没有可靠依据时不猜错误密码还是网络问题。不解析异常文本，不输出密码、连接串或SQL参数。

代码差异见errors.diff、test_wp02_remediation.diff；逐文件前后SHA256见protection-final.json。全部629项基准中仅上述3项变化。

## 3. 环境复用与真实验证

当前只读docker version/inspect确认Server29.4.0，xiutu-v5/postgres running，127.0.0.1:5433属于本项目。证据docker-version.txt、container.txt。没有重启服务、修改实际数据库密码、建删容器或删库/卷。

复用r2的Python环境：`E:\Work\xiutu-v5\.test-runs\wp02-r2-eb3556993d904333bce5867f09f01f28\A\.venv\Scripts\python.exe`；复用已迁移的隔离库`xiutu_test_wp02r2_6bca6d7b2e0b4c7fbcaee4a0`。没有新建venv或数据库，没有迁移演练/前端构建。测试通过新UUID owner/key隔离合成数据，不删除已有测试记录。新临时目录为`E:\Work\xiutu-v5\.test-runs\wp02-issue003-ae5c907478c541b69a0222c89ff6d215`，未复用历史basetemp。

显式PYTHONPATH指向当前`E:/Work/xiutu-v5/backend`，loaded-source.txt确认实际导入当前errors.py，而非旧审核副本中的实现。凭据静默读取本项目被忽略配置；没有读取旧.env，命令中不带敏感DSN。

实际应用ASGI验证（verify-asgi.py，生产create_app+登录+GET /api/v2/cases）：

- 正确凭据：200，随机新owner列表为空。
- 仅在客户端连接参数中改为随机错误密码：503 DATABASE_UNAVAILABLE、retryable=false。观测驱动OperationalError/sqlstate=null/statement为空；只通过事件读取元信息，不改变错误或事务行为。
- 随机不存在数据库：503 DATABASE_UNAVAILABLE、retryable=false。此真实连接也无SQLSTATE，走保守兜底；3D000明确状态另由分类测试覆盖。
- 响应及捕获日志均无本轮数据库密码、随机错误密码、操作员token、cookie、CSRF。结果asgi-results.json，日志asgi-log.txt。未把ASGI测试写成真实网络/TLS部署测试。

## 4. 命令、统计与必要回归

commands.json记录所有实际argv、cwd、开始/结束和退出码；各txt保存原始输出。JUnit显式独立正斜杠路径，不覆盖历史。

| 命令/检查 | 退出 | 本轮结果 |
| --- | --- | --- |
| docker version / 指定字段inspect | 0/0 | 现有专用服务归属确认 |
| ruff check --fix / format / 最终check，仅两份Python文件 | 0/0/0 | 1项import整理，最终All checks passed；保留输出 |
| 现有Python -B -m pytest -p no:cacheprovider tests/unit/test_wp02_remediation.py tests/unit/test_case_domain.py tests/integration/test_cases.py -q -s --basetemp 新目录 --junitxml 新路径 | 0 | **53 passed，0 failed/errors/skipped，1 warning，1.35s** |
| 现有Python -B verify-asgi.py | 0 | 正确凭据200；错误密码和缺库503且不可重试；秘密零匹配 |
| git diff --check / cached --check | 0/0 | 无空白问题，暂存区未调整 |

53项构成见test-statistics.json：新增10个分类测试加原分类/NUL、领域和真实PostgreSQL会话集成回归。明确认证28类、缺库3D000及无状态兜底（含connection_invalidated=true反例）均不可重试；明确连接失败、暂不可连接、死锁、锁等待、查询取消及池超时保留原瞬态语义。原22/23/未知错误、12个NUL拒绝、幂等同请求重放/异请求409、revision冲突、并发幂等及失败回滚相关用例通过。

唯一警告为既有Starlette/AnyIO BlockingPortal弃用警告。本轮没有运行整套123/106入口，也没有把历史通过数当本轮结果；没有发现要求扩大到前端或迁移的新增风险。

## 5. 结束保护、剩余事项与停止

protection-final.json：629项基准仅授权3文件变化，其余包含原审核/整改/结果/历史证据/接受记录均不变；旧项目63项逐文件哈希不变，Git index不变。新交付哈希见delivery-hashes.json；final-check.json封存报告和清单自身哈希。没有改旧项目或实际数据库密码，未提交或推送。

ISSUE-003已按本次明确规则完成最小实现与验证；是否关闭由不同审核窗口仅复核本次差异后判断。本任务不自行作独立审核结论，不重新接受WP-02。

E10仍NOT_VERIFIED，模型/调用范围/预算须另授权，最迟WP-09；资料门槛仍NOT_MET，来源/许可、车型发动机适配、规格/电路/拆装/复核及缺图最迟WP-10/真实效果验收前收口。不付费调用、不宣称生产恢复或维修效果。

**停止：WP-02保持IMPLEMENTED_NOT_ACCEPTED；交不同审核窗口复核本次差异，不进入WP-03。**
