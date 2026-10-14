# WP-04 ISSUE-001 定点复核 r2

**ISSUE-001：RESOLVED（关闭）。结合r1未变部分的证据，WP-04达到限定范围REVIEW_PASS。** 本轮未发现具体残留的必须整改问题，建议用户在保留缺项和流程限制的前提下接受限定范围交付；本报告不是用户接受。

**角色披露：本任务参与过WP-04实现及本次整改，本次为同任务切换审核角色的定点复核，不是不同任务独立审核。** 未修改实现、STATUS、接受记录或历史证据。

## 基准、实际差异与保护

读取STATUS、r1审核、r1整改、现行契约及其原始证据。适用AGENTS检查覆盖E:\、E:\Work及项目/相关子目录，未找到适用文件。检查实际job_store、ingest_state、worker、事件写入及取消/重试锁路径，并读取新增正式回归与原审核反例。

- 整改delivery-hashes.json的**1279项全部匹配**，其清单哈希与final-check一致。加入原清单和final-check，本轮固定1281项；开始无非预期变化。
- 对照整改前baseline、四份before快照、change-manifest及当前文件，实际差异仅：backend/app/infrastructure/job_store.py、backend/app/infrastructure/ingest_state.py、tests/integration/test_document_ingest.py、docs/implementation/phase-02/wp-04-contract.md。本轮生成的独立diff保存在新证据目录。原测试文件内容作为前缀完整保留，只追加新用例，未弱化旧断言。
- 根E:\Work\xiutu-v5，main，无HEAD（退出128）。Git root/branch/head、暂存diff、未暂存diff及所有未跟踪记录见[evidence/wp-04-review-r2](evidence/wp-04-review-r2/)的baseline.json及对应.txt。
- index固定为c451d6e78b8f29fc818002923a19fb1a888139ced20679ad545f75e9692a9ec6。结束复核1281项、旧项目63项及index均与开始一致；原迁移、db_target、STATUS、历史报告/接受记录及原审核反例保持原样，见final-protection.json。
- 新增仅本报告、本轮审核证据及忽略的隔离测试工件。没有add/commit/reset/push或全局Git配置修改。

## 五项复核判断

| 重点 | 结论与代码依据 |
| --- | --- |
| 版本锁取得后复验 | PASS。ingest_state.py:29—41先执行version SELECT FOR UPDATE，再执行必需的validate_lease回调；job_store.py:240—242绑定原_valid，没有可省略默认值。实测原反例及version_lock通过。 |
| 全部SQL后最终校验 | PASS。job_store.py:273—275在所有finish分支及事件写入之后调用_finish_valid；207—229使用clock_timestamp()、当前worker/token/PID及先前job映射中的lease_until快照。没有改用事务时间、重读已清空的deadline或延长租约。 |
| 整体回滚 | PASS。两个检查都在同一个connection.begin事务内；LeaseLost先触发事务回滚，再被Worker.once捕获处理。success_event_sql证明job清空lease_until、chunk/version/终态都已执行后仍能回滚；独立连接确认零chunk、零成功事件，version/parser及job/run恢复发布前状态。 |
| 判定至提交的连续保护 | PASS（明确下述边界）。首次_valid持有job/run行锁，publish再取version行锁；没有中途commit、rollback、close或unlock。NullPool专用会话的advisory锁由claim获取，直到Worker.finally中的lease.close才释放；finish.mutex覆盖整个事务。最终检查拒绝lost/closed/invalidated及PID变化。其后只退出事务提交，没有其他应用发布SQL。 |
| 共享finish回归 | PASS。正常ingest/no_op完成、取消两个提交顺序、失败/耗尽、自动重试与显式预算、旧token和断锁路径均由本轮选择的用例实际执行。取消优先与三次总尝试没有变化。 |

### 契约是否降低要求

没有。原契约关于有效租约、非取消、原子发布的段落保留，只追加明确的最终判定点。原问题是在发布SQL等待期间已过期却无条件成功；现在所有发布SQL结束后必须再次通过数据库实时时钟校验，三个等待窗口不能靠“开始时有效”获准提交。

最终授权判定发生在最后一条校验SQL，而不是宣称COMMIT的网络回包/WAL确认时间一定早于deadline。该判定后行锁和专用会话advisory锁仍持续持有：取消/重试遵循相同job→run锁顺序；其他worker即使看到旧租约过期也不能拿到该advisory锁接管。因而这是可检查的提交前授权边界细化，不是放行已经过期的发布SQL。原始任务也未承诺精确到物理提交确认时刻的实时期限保证；此处不增加该保证。COMMIT通信故障结果不明确仍不等于生产恢复已验证。

## 本轮真实运行

Docker只读inspect确认原容器running，project=xiutu-v5、service=postgres、127.0.0.1:5433映射，镜像sha256:00ba258a66dac104fd5171074a0084462a64a1369d8513f3d0a634e2f24d15bc。没有重建/停止服务、改密码或删除既有库/卷。

新库xiutu_test_wp04r2_75d1e4a2cce04890bc67，PG16.14、vector0.8.2、0004_documents。只为新库运行upgrade head准备环境，不重复迁移演练。复用既有.venv；environment-summary.json确认导入当前backend/app的job_store/ingest_state。静默加载本项目凭据，无旧.env、无敏感连接串输出。

先创建新的临时父目录.test-runs/wp04-r2-b9e4d89910394b5bb6d09da00e851c78，再执行pytest；本轮没有父目录准备错误。子目录tests及JUnit输出均为全新路径。run.py的REVIEW_EVIDENCE指向本轮目录，因此运行原test_audit_wp04.py没有覆盖旧lease-lock-window.json。

所有命令cwd=E:\Work\xiutu-v5，完整命令数组、开始/结束时间和退出码见同名.json，原输出.txt，JUnit为targeted.xml。

| 命令 | 退出码 / 结果 |
| --- | --- |
| docker --context desktop-linux inspect xiutu-v5-postgres-1（限定format） | 0，归属、镜像与端口确认 |
| .venv/Scripts/python.exe -B scripts/probes/prepare_database.py --name xiutu_test_wp04r2_75d1e4a2cce04890bc67 | 0 |
| .venv/Scripts/python.exe -B -m alembic upgrade head | 0，仅新库准备 |
| .venv/Scripts/python.exe -B -m pytest -p no:cacheprovider（targeted.json的10个选择，展开15项）-q -s --basetemp E:/Work/xiutu-v5/.test-runs/wp04-r2-b9e4d89910394b5bb6d09da00e851c78/tests --junitxml=E:/Work/xiutu-v5/docs/implementation/phase-02/evidence/wp-04-review-r2/targeted.xml | **0；15 passed、0 failed/error/skipped，无警告** |
| .venv/Scripts/python.exe -B docs/implementation/phase-02/evidence/wp-04-review-r2/environment.py | 0，版本与导入路径确认 |

测试开始14:34:23，结束14:36:05（2026-09-18，+08:00），pytest耗时100.46秒。JUnit核对15个唯一classname/name，无重复用例。本轮只执行这一次测试命令，未转抄整改者14+1统计。

选择复用整改的9个nodeid：三窗口参数化、正常资料HTTP、四种fenced recovery、发布SQL回滚、双worker竞争、旧锁/旧token、取消竞争、重试预算、断锁禁止发布；另加原审核反例文件，合计15项。没有重跑完整入口、前端、第二环境或SSE超时专项。

## 原反例、三窗口及恢复证据

所有窗口均由真实HTTP入队、独立worker进程、真实PG行锁或测试专用trigger中的advisory等待形成；不是mock、仅线程启动或客户端时钟推测。下面时间均UTC，原始观察保存在publication-windows.json、lease-lock-window.json及targeted.txt。

| 窗口 | worker OS PID / PG PID / 阻塞PG PID | lease_until → 数据库观察时间 | 结果 |
| --- | --- | --- | --- |
| 原审核反例 | 29292 / 3461 / 3462 | 06:36:04.602863 → 06:36:04.924193 | transactionid等待后解锁；chunks=0、version=parsing、run=running，原断言通过 |
| version_lock | 28888 / 3182 / 3183 | 06:34:30.694090 → 06:34:31.020372 | 过期发布整体回滚，恢复成功一次 |
| chunk_sql | 28140 / 3211 / 3212 | 06:34:38.667797 → 06:34:38.989012 | 后续chunk插入语句advisory等待，过期整体回滚，恢复成功一次 |
| success_event_sql | 21204 / 3230 / 3231 | 06:34:46.741771 → 06:34:47.070344 | 终态已在未提交事务内清空lease_until后，事件插入等待；最终校验仍使用原快照并整体回滚，恢复成功一次 |

三项正式回归逐项断言：解锁且失效worker退出后，零chunk、parser_version仍空、parse_status=parsing、job/run仍running、原lease_until/token/attempt保持、零run.succeeded。新进程随后取得已释放锁，attempt/token从1增至2，发布2个合成chunk及仅1个成功事件；再运行worker不会追加结果。这不是把失败留成永久parsing的声明，而是失效尝试可由合法worker按原预算回收。

实际SQL错误在第二chunk的既有测试也通过，确认整笔回滚后恢复只发布一次。共享finish正常分支通过，说明最终检查没有错误依赖清空后的lease_until；失败/自动重试/取消路径也通过。触发器绑定本轮特定run/version，在finally删除；probe schema清理及其他schema不变断言通过。只结束本轮自建子进程；日志源路径和哈希见child-log-manifest.json。

## 结合r1的范围结论与引用边界

| 项目 | 更新结论 | 依据范围 |
| --- | --- | --- |
| ISSUE-001 | **RESOLVED** | 当前代码审查及本轮15项真实复跑，无具体残留问题 |
| D207 上传/版本 | PASS，维持 | 引用r1原证据；相关上传/存储/API服务哈希未变。本轮正常ingest HTTP有部分覆盖，不声称重跑全部D207 |
| D208 解析/发布保护 | PASS，关闭原阻断 | 解析器/chunker未变部分引用r1；发布保护由本轮原反例、三窗口和受影响回归补齐 |
| D209 审核门禁 | PASS，维持 | 引用r1未变资料服务/安全字段及原证据；approved仍index_pending，formal_usable=false |
| WP-04限定范围 | **REVIEW_PASS** | r1未变部分 + 本轮定点证据；不代表用户接受 |

已实际解析r1 full.xml并核对哈希e7727935d56182d93ab555bed4226ef5d2692fa12a0c0874f9542aa0fe9836ee：169项、零失败错误跳过。这是**整改前r1基准的完整测试证据**，不是当前版本重新全量通过。referenced-evidence.json列出引用文件及未变代码哈希。

SSE保留“首次根因未确认”。r1完整运行未复现，当前没有新证据要求重新定位；本轮不将其写成已修复。性能、监控和清理等既有非阻断建议继续保留，不扩大验收。

## 接受建议与停止

建议用户接受WP-04限定的本地资料上传、版本、解析与人工审核能力，并知悉同任务审核的流程限制。扫描/混合缺页仍needs_ocr，没有OCR、embedding、索引、检索、正式诊断或真实维修效果验证；批准不是索引就绪。生产恢复和COMMIT通信故障结果不明确不在本轮保证内。

E10继续NOT_VERIFIED，模型/范围/预算另行授权，最迟WP-09收口；真实资料门槛继续NOT_MET，来源许可、精确车型/发动机及正式规格、电路、拆装/复核章节和缺图最迟WP-10/真实效果验收前补齐。

没有修改STATUS或接受记录，没有旧项目/历史证据/迁移/index变更，没有提交推送或付费调用。WP-05未启动。完成后停止，由用户决定是否接受。

报告时间：2026-09-18T14:39:25.929506+08:00
