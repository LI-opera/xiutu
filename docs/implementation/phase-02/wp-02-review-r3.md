# WP-02 ISSUE-003 定点复核 r3

**结论：REVIEW_PASS（限定WP-02范围）；ISSUE-003 RESOLVED。建议用户结合列明保留项决定是否接受。**

角色声明：整改实施与本次复核由同一任务完成。本次按审核角色只读检查实现并新生成验证证据，不能如请求所述称为“不同任务复核”，也不将同任务r2称为独立审核。本限制不意味着必须重做整包验证。本轮没有修改实现、STATUS、接受记录或历史证据，没有自行接受WP-02。

## 基准及范围

检查项目、上级及相关子目录，未发现适用AGENTS.md。读取review-r2、remediation-r2、contract、errors.py和对应测试，核对errors.diff、protection-final.json、targeted.xml、asgi-results.json。

Git根E:/Work/xiutu-v5，main，无HEAD（原核对退出128）；root/branch/head/status/cached/unstaged.txt记录开始状态。Git仅命令级safe.directory，未调整index。baseline.json固定661份文件及Git index。整改清单659项全部匹配；整改报告、清单本身及index与整改final-check匹配。

与整改开始629项基准比较，只有errors.py、test_wp02_remediation.py、wp-02-contract.md三项变化，符合授权范围；其余新增项为既有r2整改工件。三项当前SHA256：

| 文件 | SHA256 |
| --- | --- |
| backend/app/api/errors.py | 9a5e86c213b6333b94f02640b431d77f4e751cbec6dfb845e1dac5233ea6fb08 |
| tests/unit/test_wp02_remediation.py | ea0cde1508b85877221cdec64f524896443c3a7c00559191c47899e7a9d5cf17 |
| docs/implementation/phase-02/wp-02-contract.md | 2d77c9cb5d8d516a3dacecf2f9e7824977ad04f7ab08d84caceb9fb34c888a8c |

结束protection-final.json确认661项均未变化；旧项目63项保护哈希一致；Git index仍为c451d6e78b8f29fc818002923a19fb1a888139ced20679ad545f75e9692a9ec6。保护范围包括原迁移、db_target、NUL校验、目录准备、STATUS、历史审核/整改/接受记录。初次准备脚本曾把旧清单相对路径误按当前目录解析而触发断言，随后改用旧项目绝对根只读核对63项成功；未由此修改任何保护文件。

## ISSUE-003复核

**RESOLVED。** errors.py:36—43将28类认证、3D000缺库、无SQLSTATE且无statement的驱动OperationalError优先返回503 DATABASE_UNAVAILABLE，DomainError默认retryable=false；这些分支先于44—49的connection_invalidated判断，因此不会再次被标为可重试。未解析异常文本，没有猜测无SQLSTATE究竟是认证还是网络错误。

现有08类/57P01—03及连接失效分支保留；池超时、40001/40P01/55P03/57014保留DATABASE_BUSY。22/23类和未知错误仍安全返回不可重试500，不把IntegrityError一律变客户端422；业务DomainError处理器未改，幂等/revision409保持。对未来所有故障的恢复概率不作保证。

19项分类测试覆盖明确认证、缺库、无SQLSTATE及connection_invalidated优先级，瞬态、数据、唯一/FK约束、未知错误和秘密脱敏。测试经过register_errors注册的ASGI处理器，不仅调用分类函数。另以实际生产create_app入口和真实PostgreSQL连接验证正确/错误凭据。

未发现新的具体必须整改问题；不重新打开ISSUE-001及ISSUE-002已验证的NUL部分。ISSUE-002原遗留分类问题由本次ISSUE-003闭环。

## 本轮实际运行

当前Docker Server29.4.0可用。container.txt确认xiutu-v5/postgres标签、running、127.0.0.1:5433映射及镜像sha256:00ba258a66dac104fd5171074a0084462a64a1369d8513f3d0a634e2f24d15bc。只复用归属明确的服务与xiutu_test_wp02r2_6bca6d7b2e0b4c7fbcaee4a0测试库；未改真实密码、停止服务或删除库/卷。

复用r2 A环境，通过PYTHONPATH指向当前backend，并断言app.api.errors.__file__为E:/Work/xiutu-v5/backend/app/api/errors.py（loaded-source.txt），未运行旧editable副本实现。workspace.json记录解释器与新UUID临时目录。测试使用新随机owner，幂等key在新owner命名空间隔离。静默读取本项目被忽略凭据，未读取旧.env。

commands.json保存每条实际argv、cwd、起止时间和退出码；cwd均E:/Work/xiutu-v5，以下全部退出0：

- docker version；docker inspect（仅标签、端口、状态、镜像，不输出容器环境）。
- 当前源码导入路径断言。
- `<复用python> -B -m pytest -p no:cacheprovider tests/unit/test_wp02_remediation.py::test_database_error_response tests/unit/test_wp02_remediation.py::test_retry_requires_structured_evidence tests/integration/test_cases.py -q -s --basetemp <新目录>/pytest --junitxml <本轮目录>/targeted.xml`。
- `<复用python> -B <本轮目录>/verify-asgi.py`。

本轮独立生成统计：**24 passed，0 failed、0 errors、0 skipped，1.10秒，1条既有Starlette/AnyIO BlockingPortal弃用警告**。其中分类19项、真实数据库会话集成5项，涵盖所有权、分页、同key重放/异请求409、revision冲突、并发幂等和事务失败回滚。此次未将原53项或整包123/106项统计转抄为本轮结果，也不将线程测试扩展为新完成全部锁等待演练。

生产应用ASGI实际结果（asgi-results.json）：

| 条件 | 状态 | code / retryable |
| --- | --- | --- |
| 正确连接凭据、新owner读取 | 200 | 空列表，正常 |
| 同服务/用户/数据库，仅客户端密码改成随机错误值 | 503 | DATABASE_UNAVAILABLE / false |
| 正确密码、唯一不存在测试库名 | 503 | DATABASE_UNAVAILABLE / false |

两种失败均实际观察到驱动OperationalError、sqlstate=null、statement_is_none=true；没有解析错误文本。登录使用应用真实认证，再请求GET /api/v2/cases。这里只声称ASGI入口实测，不声称新启动Uvicorn网络HTTP。探针由整改脚本复制至新目录，来源哈希见probe-provenance.json；当前运行的owner、秘密及结果均重新生成，没有覆盖历史输出。

响应和捕获应用日志对数据库密码、错误密码、操作员token、cookie、CSRF作零匹配断言；证据文件另扫描实际数据库密码，零匹配。asgi-log.txt记录本轮捕获日志；不将该有限检查夸大为全部部署日志审计。

## 引用证据及更新结论

| 项目 | 结论 | 本轮与引用范围 |
| --- | --- | --- |
| ISSUE-001测试入口 | RESOLVED，维持 | 引用review-r2的首次干净完整/离线运行、目录与退出码反例；scripts/test.ps1哈希未变，本轮不重复 |
| ISSUE-002 NUL | RESOLVED，维持该部分 | 引用review-r2的12项真实HTTP、无事务/无残留、合法Unicode等；schemas.py和相关输入代码哈希未变 |
| ISSUE-003分类 | RESOLVED | 本轮19项分类及生产ASGI正确密码/错误密码/缺库实测 |
| D201所有权与输入 | PASS（WP-02范围） | 本轮会话/跨owner回归，加上述未变输入证据 |
| D202迁移与约束 | PASS（引用未变证据） | r2完整入口及其引用的r1精确并发/迁移证据；迁移、ORM、UoW、隔离门禁均未变，不声称本轮重跑迁移 |
| D203幂等 | PASS | 本轮重放/409/回滚/原并发回归，加r1/r2未变部分精确时序证据 |

原r2数据库分类FAIL由本轮限定差异实测更新为PASS。历史报告保持原样。无新环境阻塞。没有重建venv、前端构建、迁移演练、完整入口或整包审核；这些未在本轮重跑不构成本次定点复核BLOCKED。

## 接受建议与停止

结合此前未变部分证据，**给出WP-02范围内REVIEW_PASS，建议用户在知悉同任务审核角色限制及以下保留项后决定接受**；不是用户已接受，不自动更新STATUS。

E10仍NOT_VERIFIED：真实DeepSeek调用须先授权模型、范围和预算，最迟WP-09收口。真实资料仍NOT_MET：来源/许可、精确车型/发动机适配、规格、电路、拆装/复核章节及缺图，最迟WP-10/真实效果验收前补齐。不得扩展为任务执行、正式诊断、生产恢复、正式业务MCP或真实维修效果通过。

WP-02仍IMPLEMENTED_NOT_ACCEPTED。没有付费调用、提交推送或进入WP-03。本轮到此停止，等待用户决定。

报告生成时间：2026-09-18T12:00:28.058910+08:00。
