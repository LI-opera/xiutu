# WP-02 执行结果

记录时间：2026-09-18T04:10:23.583373+08:00。**状态：IMPLEMENTED_NOT_ACCEPTED，等待独立审核。** 仅数据库、领域、认证与会话create/get/list；WP-03—17仍NOT_STARTED。本文件不作REVIEW_PASS或ACCEPTED结论。

## 1. 依据、基准和范围

工作目录/Git根E:\Work\xiutu-v5，main无HEAD（验证退出128），原暂存区保留。读取适用AGENTS（项目/上级未发现）、STATUS、WP-01接受/r2审核/r1整改、依赖矩阵、P2实施说明/清单及总指南4/5/7节和WP-02。先向用户列明文件范围、衔接差异、验证顺序，再形成[具体契约](wp-02-contract.md)。

开始348项文件SHA256、Git分支/状态/cached/unstaged见evidence/wp-02/baseline.json和相应txt。STATUS接受更新为预期前置变化；原报告、证据、接受记录不改。结束保护见protection-final.json，交付清单见delivery-hashes.json。新文件多数未跟踪，不能只读git diff --stat。没有git add/commit/reset/push或全局safe.directory修改。

保留0001_environment，新增0002_core；统一健康预期版本、同步当前探针断言；测试默认入口纳入unit/integration。创建无expected_revision、revision0；仅在服务/领域层验证已有对象revision，不为测试扩充写接口。

## 2. 实际文件和契约选择

- domain/enums.py、schemas.py、policies.py：状态、严格输入与嵌套extra=forbid、字段长度/年款/故障码归一化、CaseSnapshot/分页/错误模型及revision冲突。
- infrastructure/orm.py、migrations/versions/0002_core.py：八表cases、documents、document_versions、chunks、runs、jobs、run_events、idempotency_keys；UUID、timestamptz、RESTRICT FK、CHECK、唯一约束及活跃run部分唯一。迁移内冻结定义独立于可变app metadata；降级仅八表，不删除vector。
- infrastructure/uow.py、repositories/cases.py、services/case_service.py：共享目标门禁后重建驱动参数，begin/commit/rollback/释放；owner过滤、签名键集游标、创建与幂等响应同事务。
- api/auth.py、dependencies.py、errors.py、cases.py、openapi.py，config.py/main.py：受保护环境令牌、稳定OPERATOR_ID、限时内存认证、Cookie/Origin/CSRF、退出失效与统一脱敏错误；OpenAPI明确认证及必需写请求头，私有响应no-store。
- db.py/schema_version.py、tests/probes/test_pgvector_probe.py：0002_core统一预期，保留缺/错迁移及真实连接故障分支。
- tests/unit、tests/integration、pyproject.toml/scripts/test.ps1，以及README/CHANGELOG/tests/README/STATUS和本包文档。

单操作员默认单进程，认证会话1小时、重启失效；HTTPS使用Secure，HTTP仅loopback。不同Cookie仍属同一operator owner；跨owner测试使用不同UUID身份。登录也验证Origin，不进入业务幂等缓存；成功登录轮换所带旧会话，logout撤销。重放业务请求重新验认证/Origin/CSRF。

业务幂等(actor,route,key)唯一，规范化输入稳定hash；INSERT ON CONFLICT DO NOTHING等待原事务后读取已提交响应，同请求原201/原响应、异请求409。新key/case/响应同事务，失败全部回滚；不会在失效事务继续查询。记录不清理，至少保留7天，本包无清理worker。

资料快照corpus_manifest由服务端保存为空。active_run=null、report_gate={available:false,reason:"NOT_IMPLEMENTED"}，不声称已具备任务状态查询或报告判断。document_versions.active_index_id未建，WP-05随index_versions及FK一起加入。分期未建区域/观察/报告等见契约；任务表不是WP-03执行能力。

## 3. 本次独立环境及真实执行

全部新证据在evidence/wp-02/，commands.json记录命令/cwd/起止时间/退出码/原始输出。每次全新basetemp，未覆盖历史。新venv为`.test-runs/wp02-dc9f9361c1194e1c9b826011ec042d72/reproduction-venv`；独立前端副本安装，不复用主node_modules。Python3.12.10、Node24.14.0及锁定版本不变。

| 执行 | 退出码 | 实测结果与证据 |
| --- | --- | --- |
| docker version / inspect指定字段 | 0 / 0 | docker-version.txt、docker-owned.txt；Server29.4.0，xiutu-v5/postgres healthy，127.0.0.1:5433；未重建/停止容器或删卷 |
| prepare_database.py创建唯一库；alembic upgrade head | 0 / 0 | create-db.txt、upgrade.txt；新库0002_core |
| 首次unit | 0 | unit-first.txt/xml：24 passed，1 warning |
| 首次完整pytest默认收集 | 0 | full-first.txt/xml：99 passed，1 warning，26.99秒 |
| 全新UV_PROJECT_ENVIRONMENT uv sync --frozen --group dev；uv pip check | 0 / 0 | frozen-reproduction.txt、dependency-check.txt；83包依赖兼容 |
| 补充数据库检查后scripts/test.ps1 | 0 | default-entry-full.txt/full-final.xml：101 passed，1 warning，35.53秒 |
| **最终发布入口scripts/test.ps1，新venv** | **0** | **default-entry-delivery.txt/full-delivery.xml：102 passed，0 failed/errors/skipped，1 warning，36.05秒** |
| **最终scripts/test.ps1 -OfflineOnly，无数据库配置** | **0** | **offline-entry-delivery.txt/offline-delivery.xml：85 passed，0 failed/errors/skipped，1 warning，16.17秒** |
| 实际Uvicorn HTTP三个独立进程 | 0 | http-results-final.json、http-final-*-server.txt；认证/创建/读取/列表、重放/409、两owner、CSRF、退出、DB不可用503 |
| 独立前端npm ci/typecheck/build | 0 / 0 / 0 | frontend-ci.txt/typecheck.txt/build.txt；Node检查实际执行，Vite构建27modules，无新页面 |
| 最终ruff check | 0 | ruff-delivery.txt：All checks passed |

本轮没有付费模型请求。1条Starlette/AnyIO弃用警告原样保留。102与85为本轮实际统计，不复用WP-01历史通过数；默认完整模式无skip。

99→101→102来自新增真实SQL回滚/数据库CHECK内省、OpenAPI安全契约测试。首次lint103项、自动修复后的格式问题及后续新迁移import位置2项均保留；格式整理和移至模块顶层后最终通过，不改0001。前端build本身退出0且原始输出已写，辅助记录程序在随后控制台打印Unicode勾号时遇GBK编码错误；不是构建失败，后续记录显式UTF-8。

JUnit经PYTEST_ADDOPTS传入Windows反斜杠路径，被pytest/shlex去掉反斜杠，四份文件初次生成在项目根。发现后确认其不在基准且目标不存在，按原字节移入本证据目录，前后SHA256和逐项统计见junit-relocation.json；未伪造XML或覆盖历史。后续应使用正斜杠路径或正确引号。

## 4. 真实数据库、安全和回归

主测试库`xiutu_test_wp02_e605b3af828943b8a232b02f50`。另外每轮迁移测试创建独立新库，未复用WP-01保留库；管理员连接xiutu_dev仅CREATE新库，不迁移开发库。凭据静默读取新项目忽略文件，未读取旧.env，不进入命令参数日志。

- 新空库upgrade head；独立库0002→0001→0002成功。空/旧/错revision不就绪，0002匹配就绪。降级后public仅alembic_version，vector0.8.2与独立sentinel schema及值7保留，最后只清理自身sentinel。
- migration-manifest-final.json保存实际列/默认/NOT NULL/CHECK/FK/唯一键/索引；database-inventory-final.json确认PG16.14、vector0.8.2、revision0002_core，无wp01残留schema或后续表。
- 4个并发真实事务同key仅1条case/响应；同key异请求409；不同owner同key不串响应。应用注入错误及真实SQL约束错误均回滚，后续可使用同key重新创建。
- 2个真实事务并发争抢同case活跃run仅1个提交；waiting_input释放槽、cancel_requested占槽、NULL case可并存，jobs.run_id唯一。文档hash/chunk ordinal唯一、FK阻止删除被引用父行；无效状态和负数拒绝。
- 输入拒绝伪造owner/revision/corpus及嵌套额外字段；两个独立owner读取404/列表隔离；非法/跨owner游标拒绝；服务revision冲突且数据不变。
- 真实HTTP两个独立Uvicorn进程使用不同owner，创建/读取/列表/重放/409/CSRF/退出均通过；第三无DB进程认证后创建得到统一503。保存脱敏响应和openapi-final.json，不保存登录token/Cookie/CSRF秘密。
- WP-01原共享门禁35项+新增UoW入口拒绝反例通过。真实vector排序/schema清理、Postgres checkpoint两进程/错误workflow、MCP SDK初始化/list/call/有界断连均在最终完整输出；没有SQLite/MemorySaver替代。
- OfflineOnly真实脚本无DATABASE_URL/TEST_DATABASE_URL，仅unit/contract/MCP，不包含任何数据库模块。完整入口包含integration，缺DB不允许静默skip。

创建并保留的本轮测试库：

- `xiutu_test_wp02_e605b3af828943b8a232b02f50`
- `xiutu_test_wp02mig_9749a4378b8e4567a0143f97`
- `xiutu_test_wp02mig_c0a5fbd42f684c498a9c54c8`
- `xiutu_test_wp02mig_c4156a8e785a4545a31d8e6c`

未执行DROP DATABASE。数据库内保留本轮合成记录供复核；独立HTTP/MCP子进程和自身probe schema已清理，不停止其他服务。

## 5. 自测清单、遗留与保护

D201所有权/输入、D202迁移/并发约束、D203幂等均有上述实际自测证据供独立审核。D204—D214等后续包项目未实现，不判本包通过项。本文件是执行结果，不是独立审核结论。

无本包核心阻塞。限制：认证仅单进程内存会话，重启失效；不提供注册、多角色、生产多worker会话共享。无任务执行/worker/租约/SSE、资料上传解析检索、正式MCP、诊断Agent、报告或新业务UI。探针成功不等于生产恢复保证、正式产品或维修效果。

E10真实DeepSeek仍NOT_VERIFIED，另须模型/范围/预算授权，最迟WP-09；资料仍NOT_MET，来源/许可、车型/发动机、规格/电路/拆装/复核章节和缺图最迟WP-10/真实效果验收前补齐。

保护详情见protection-final.json：原接受记录、历史报告/证据、0001迁移、共享db_target、Git index不变，旧项目63项逐文件哈希不变。仅本包允许的实现/当前文档修改。不存在提交或推送。

## 6. 用户验证与停止

README给出：确认Docker归属→创建全新xiutu_test_*→upgrade head→scripts/test.ps1；不升级WP-01保留库。可先运行OfflineOnly。配置受保护OPERATOR_TOKEN/APP_ORIGIN，单worker Uvicorn启动后按README登录→携Cookie/CSRF/Origin/Idempotency-Key创建→GET/列表→重放/冲突→logout。预期状态和响应见OpenAPI/HTTP证据。

审核者优先阅读wp-02-contract.md、0002_core.py、uow.py、case_service.py、api/dependencies.py、config.py、最终JUnit、HTTP、迁移清单和保护哈希。秘密不得复制进Git或审核文档。

**停止：WP-02=IMPLEMENTED_NOT_ACCEPTED，等待独立审核与用户接受；WP-03—17=NOT_STARTED。不开始WP-03，不提交、不推送。**
