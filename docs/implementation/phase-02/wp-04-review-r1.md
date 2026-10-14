# WP-04 集中审核 r1

结论：**CHANGES_REQUIRED**。D207、D209通过；D208的常规解析验证通过，但发布保护存在1项必须整改问题（ISSUE-001）。暂不建议接受WP-04。只需对该问题整改并定点复核，不默认重开整包审核。

## 审核角色与边界

**WP-04实施与本次审核由同一任务完成，审核任务参与过实现；本报告不声称不同任务独立审核。** 本轮重新固定基准、实际运行测试、追加审核反例，未现场修复实现。用户接受权保留。

只审核WP-04资料上传、解析、审核与版本，关注其worker/job_store/ingest衔接。没有重审未变WP-02全部能力，没有前端或第二环境重建，也没有开展WP-05。未修改STATUS、接受记录、旧项目、原迁移/原报告/原始执行证据或Git index。

## 依据、范围及基准

已读取适用路径检查结果（E:\、E:\Work、项目及相关子目录未找到适用AGENTS.md）、STATUS、wp-04-result/contract、wp-03-acceptance、README、旧项目P2实施说明和验收清单，以及总指南WP-04及资料/任务/接口相关契约。实际检查上传、存储、领域输入、文档服务/API、0004/ORM/health、MD/PDF/chunker、worker、job_store、ingest_state、测试及原始执行日志。

开始于2026-09-18 13:57:54 +08:00。Git根E:\Work\xiutu-v5，分支main，无HEAD（rev-parse退出128，按实际记录）。暂存与未暂存diff、未跟踪清单见本目录[evidence/wp-04-review-r1](evidence/wp-04-review-r1/)的root/branch/head/status/cached/unstaged.txt及baseline.json，不能仅靠diff判断未跟踪交付。

- 原delivery-hashes.json的**1133项全部匹配**，没有非预期交付差异。原清单SHA256：ab26564c932719c3f0016b11467b199589638198bd7512d2e985c2f3b289f0b8。
- 再保护原清单和final-check.json，共1135项；含实现、0001—0003、共享db_target、历史报告/证据及WP-00—03接受记录。旧项目63项单独固定，保留原计划文档变化历史，不误称全盘所有文件都受保护。
- Git index：c451d6e78b8f29fc818002923a19fb1a888139ced20679ad545f75e9692a9ec6。
- 对照本包change-manifest：变更集中于资料模型/0004、上传解析、发布衔接、接口/测试/锁依赖及说明。scope-check.json记录声明修改文件；runs API、UoW、共享db_target对照WP-04开始基准未变。test_job_recovery.py有本包ingest预期调整，不把整个文件称为未变。
- 结束保护核对见final-protection.json：1135项、旧项目63项、Git index开始/结束一致；新增范围仅本报告、审核证据及忽略的本轮测试工件。

## 本轮环境与命令

初查引擎管道不存在，创建新库/迁移均失败退出1；docker-current/create/migration原失败证据保留。用户启动Docker后引擎可用但项目容器一度exited，用户随后启动该已有容器。审核未重建/停止容器、改配置或删卷。

docker-started确认project=xiutu-v5、service=postgres、Compose路径属于本项目、映射127.0.0.1:5433→5432；镜像sha256:00ba258a66dac104fd5171074a0084462a64a1369d8513f3d0a634e2f24d15bc。实际PG16.14、vector0.8.2、revision=0004_documents（environment-summary.json）。ENV：本轮初始阻塞已解除，不沿用历史故障判定最终状态。

仅静默读取本项目受保护凭据；新库xiutu_test_wp04r_47acc170505e4e049a1788d5，完整测试迁移用例另外创建自己的唯一xiutu_test_wp02mig_b7912ee9c6494360bf7e6deb，均保留。没有读取旧.env或私人手册。Python复用项目.venv；环境证据确认实际导入当前backend/app/worker.py、job_store.py、document_service.py。未切换旧editable副本。

命令cwd均E:\Work\xiutu-v5，详细起止时间和原命令数组见各同名.json，stdout/stderr见.txt。包装器run.py只静默装入隔离连接配置并保存本轮输出；无完整敏感连接串。命令如下：

| 本轮运行 | 实际入口 | 退出码 / 结果 |
| --- | --- | --- |
| docker-started | docker --context desktop-linux inspect xiutu-v5-postgres-1（限定format） | 0，归属/端口/镜像通过 |
| create-after-start | .venv/Scripts/python.exe -B scripts/probes/prepare_database.py --name xiutu_test_wp04r_47acc170505e4e049a1788d5 | 0，新库创建 |
| migration-after-start | .venv/Scripts/python.exe -B -m alembic upgrade head | 0，仅新库 |
| full | pwsh -NoProfile -File scripts/test.ps1 | **0；169 passed，0 failed/error/skipped，1 warning** |
| lease-window | .venv/Scripts/python.exe -B -m pytest -p no:cacheprovider docs/implementation/phase-02/evidence/wp-04-review-r1/test_audit_wp04.py -q -s --basetemp E:/Work/xiutu-v5/.test-runs/wp04-review-f9580f84d15f4808b78ae9b23a15981f/lease-window --junitxml=E:/Work/xiutu-v5/docs/implementation/phase-02/evidence/wp-04-review-r1/lease-window.xml | **1；1 failed，0 passed/error/skipped，无警告** |
| environment | .venv/Scripts/python.exe -B docs/implementation/phase-02/evidence/wp-04-review-r1/environment.py | 0，当前源码、PG版本、失败反例的持久事件 |

完整入口仅执行一次，14:07:05—14:09:51 +08:00，pytest 160.36秒。PYTEST_ADDOPTS指向本轮full.xml；新basetemp为.test-runs/run-5c38fb3c6d1a467ca34d8287b123d107。JUnit正确使用正斜杠路径；统计/哈希见test-summary.json。唯一警告是原Starlette/AnyIO BlockingPortal弃用。

追加反例仅一次，pytest 6.85秒；不重复通过用例凑统计，不把169通过掩盖本轮新增失败。只有审核用例文件新增，未修改被审测试或生产行为。真实HTTP子进程、worker、PG行锁，未替换校验/发布实现。

## D207—D209及受影响检查

| 验收项 | 结论 | 本轮实测与代码证据 |
| --- | --- | --- |
| D207 上传与版本 | PASS | full.xml中资料HTTP用例：同key重放/异请求409、同文档同hash200复用且不改审核、新内容新version旧原文保持；两个HTTP请求经屏障后在同文档行锁上真实等待，放行后一份version/job；跨owner读/写/原文/chunk/run统一404。真实SQL上传失败回滚并清理本次候选。流式实际字节/part/header限制、伪PDF/编码/加密/路径拒绝；实际junction拒绝测试。UUID独占原文件，哈希读取校验。 |
| D208 解析及发布保护 | **FAIL** | full中Markdown长表、Unicode、超长内容覆盖/BPE上限、页码与扫描/混合page_issues、损坏/加密拒绝均通过。真实worker取消、finish前过期、崩溃恢复、耗尽和第二chunk SQL错误整体回滚/恢复通过。但新增“finish内版本锁等待跨租约期限”实测仍发布chunk与成功事件，见ISSUE-001。 |
| D209 人工审核 | PASS | 真实HTTP pending→approved→rejected历史可追溯、actor/time/source/scope/note、同key历史不重复、重传不重置审核、跨owner审核404、needs_ocr不能批准。safety始终formal_usable=false/index_implemented=false；approved仅index_pending。没有索引任务或假搜索，synthetic/unknown没有变成正式维修证据。 |
| 受影响任务/接口回归 | 常规回归PASS，发布边界例外见ISSUE-001 | 完整入口涵盖独立双worker竞争、心跳、前后中断、旧锁/旧token、取消竞争、预算、真实HTTP/SSE、断锁不重连；迁移/health、认证/事务幂等及基础PG/vector/checkpoint/MCP也实际执行，没有静默skip。不是对未变包的重新接受。 |

文件/数据库跨介质不是原子事务：正常数据库失败及并发重复路径有本轮证明；硬中断孤儿与提交结果不明确的极端网络窗口未穷举，不声称生产恢复保证。原文存储要求本机可信写权限，路径检查不等于抵御特权并发路径替换。PDF复杂布局理解、OCR均未实现。

## A. 必须整改

### ISSUE-001 / P1 / D208：发布等待期间过期租约仍能写入正式结果

位置：backend/app/infrastructure/job_store.py:207—218（finish持有lease.mutex，先_valid再publish）；backend/app/infrastructure/ingest_state.py:29—64（获取version行锁后直接插入chunks/改状态）；有效期检查在job_store.py:178—187。

触发：解析完成时租约有效，finish检查通过；另一事务持有对应document_versions行锁，finish随后等待该锁直至租约过期。finish持有mutex，独立心跳无法续租；锁释放后没有再次校验有效期，继续写chunks、version并发布成功。

**真实复现**（test_audit_wp04.py、lease-window.txt/xml、lease-lock-window.json、lease-window-events.json）：

1. 通过实际HTTP上传合成MD；独立worker OS PID29660，测试租约2秒/心跳0.15秒，真实解析完成后停在before_finish屏障。
2. 审核连接PG PID659对该version SELECT FOR UPDATE；释放worker屏障。pg_stat_activity和pg_blocking_pids证实worker PG PID658在transactionid锁等待，查询为document_versions行锁，开始06:10:12.921812 UTC。
3. 数据库clock_timestamp=06:10:15.249542 UTC时，lease_until=06:10:14.917139 UTC，token=1，仍running，chunks=0；已明确过期约0.332秒。
4. 释放本轮行锁后worker正常退出0，**chunks=2、version=review_pending、run=succeeded**，持久事件含run.succeeded（id133）。事件created_at使用事务时间，不是提交时间，不能拿其早于过期的值否定实际锁等待/提交时序。
5. 审核断言“过期后不发布chunk”失败。全套原测试只覆盖finish调用前过期，未覆盖此窗口。2秒是隔离测试允许的缩短租约；生产60秒相同执行顺序，等待超过剩余有效期即具备同类条件，不声称本轮等待了生产60秒。

影响：违背有效lease/token后发布的明确契约，可将过期执行结果标记成功。本轮未观察到双worker同时执行或半套chunk；这些不是本问题的必要前提，也不夸大为已发生其他故障。

最小修复要求：在获得可能阻塞的发布所需锁之后、发布提交前，重新确保同一物理锁连接、worker/token、run取消状态及有效租约；任何检查失败必须回滚整笔chunks/version/success事件。必须考虑该事务内后续SQL耗时，不仅把第一次检查挪动几行；短事务/合理等待上界可辅助，但不能靠放宽租约或削弱断言掩盖过期发布。保留原advisory互斥、取消优先和尝试预算，不扩建通用工作流。

定点复核：保留本反例，实际观察PG锁等待和DB时钟；解锁后0 chunk且无run.succeeded，失效尝试不能发布，释放锁后新合法worker可恢复且只发布一套。补受影响的取消、发布SQL回滚及正常ingest成功回归即可；不默认重跑前端、第二环境或重开整包审核。

## SSE首次超时的专项结论

读取原full-after-collection-fix.txt/xml：168通过、1 ReadTimeout失败；原sse-targeted和final-targeted为随后一次单项和一次组合通过（约16.984/17.156秒），只作引用，未改写为原全量通过。

本轮完整入口原用例通过，API PID29308，约17.015秒结束；15秒注释心跳、跨owner404和认证过期关闭断言均真实执行，另一个SSE用例重放/终态/注销关闭通过。**本轮未复现，首次根因未确认。** 不称已修复或偶发环境问题。

检查stream：每轮auth.get，短UnitOfWork取事件，资源在调用返回前关闭，再sleep；前序fixture正常结束路径关闭client、终止其自建子进程、dispose store。本轮全入口中前序资料/worker测试同样运行后该用例成功，未发现足够证据归咎前序资源泄漏。首次日志仅到GET events 200，没有逐轮DB耗时/心跳发出/认证关闭时序，无法定位当时哪一步停滞。

原失败和本轮服务端日志复制到新证据目录，child-log-manifest.json记录源路径/哈希；原文件未覆盖。剩余风险是过去一次读超时未解释；若无ISSUE-001，现有一次完整通过加原定点记录足以支持限定WP-04功能范围通过，但不支持稳定性或性能保证。本报告拒绝接受的依据是已复现ISSUE-001，不因这项残余疑问扩张整改范围。

## B. 非阻断建议与未验证项

- 后续增加不含内容/凭据的SSE阶段耗时、心跳发出、关闭原因观测，便于再次出现时定位；不因本建议扩大本包。
- 文件孤儿巡检、上传时长/并发配额、复杂PDF资源隔离、性能/监控属于后续改进；本轮无证据要求建设全局平台。
- 未重新执行前端构建、第二环境、真实性能压测或真实私人语料；未把探针及合成文件通过扩展成正式索引、检索、诊断、生产恢复或维修效果。
- E10仍**NOT_VERIFIED**，模型/范围/预算另行授权，最迟WP-09收口。真实资料门槛仍**NOT_MET**，来源/许可、精确车型/发动机、规格、电路、拆装/复核章节与缺图最迟WP-10/真实效果验收前补齐。

## 交付与停止

仅新增本报告和evidence/wp-04-review-r1审核工件；本轮隔离库/临时目录保留可复核。没有修改实现或STATUS，没有接受记录、提交/推送、付费请求。WP-05未启动。

建议用户先安排ISSUE-001最小整改与定点验证，再决定是否接受；D207/D209和已通过回归证据保留，不因一般建议反复扩大范围。

报告生成时间：2026-09-18T14:13:55.888856+08:00
