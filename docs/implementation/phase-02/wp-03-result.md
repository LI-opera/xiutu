# WP-03 实施结果

状态：**IMPLEMENTED_NOT_ACCEPTED**。完成记录：2026-09-18T12:30:18.640047+08:00。仅持久任务、租约、事件与取消；等待一次审核和用户接受。未生成review或接受结论，未进入WP-04。

## 前置、基准和范围

用户明确授权WP-03及轻量流程。读取STATUS、WP-02接受/契约、P2实施/清单、总指南第6/7节和WP-03。项目、上级及相关目录未发现AGENTS.md。

Git根E:/Work/xiutu-v5，main，无HEAD（退出128），按完整文件清单固定基准，不仅依赖diff。evidence/wp-03/baseline.json记录686份接受后输入及index；接受后只有STATUS和新增WP-02 acceptance相对于r3的授权差异，原r3的661项中其余文件、22项审核工件、原报告、index及旧63项哈希均匹配。root/branch/head/status/cached/unstaged.txt记录开始状态。

新增实现：domain/tasks.py、infrastructure/job_store.py/event_store.py、services/run_service.py/event_service.py、worker.py、api/runs.py、0003_jobs.py、测试与CLI/演示。必要修改：ORM/health版本、main/OpenAPI、case_service/CaseSnapshot真实active_run、迁移回归。文档为本契约/结果/API、README、CHANGELOG、STATUS及tests说明；完整修改及新增列表见changes.json。0001/0002、db_target、WP-02错误分类及所有历史报告/接受/证据不改。

## 可用能力和衔接决定

- 入队以事务原子写run/job/run.queued，复用owner、幂等、revision及case活跃唯一约束。无case使用持久owner_id；历史无归属任务对用户404。0003仅加owner和队列/事件索引，不建立后续业务表。
- 稳定SHA256派生64位case/run advisory锁；专用NullPool物理连接先拿锁，再短事务SKIP LOCKED领取。attempt/token递增，60秒租约/15秒独立心跳。锁竞争不消耗attempt，租约过期不越过旧锁。执行期间不持长事务。
- 同一持锁连接串行心跳/发布，验证worker/token/有效租约/run状态；连接断开后不重连接管，迟到结果不能成功。finally只关闭本次专用连接和进程资源。
- queued取消直接cancelled；running取消先cancel_requested，持锁worker/回收者确认。取消不改变case revision。job→run锁顺序裁决取消和成功，事件与状态同事务。
- 总尝试3次（初次+2次），自动等待2/8秒加抖动，30秒档在此预算下不使用。只有明确TransientTaskError自动重试；no_op正常不调用网络/模型。用户retry创建parent_run_id新run且继承attempt/turn/workflow，父run superseded防分叉；不能重置预算。永久/未知/未实现错误不自动重试。
- 唯一成功处理器no_op，内容仅0..300秒等待；ingest及未知类型明确HANDLER_NOT_IMPLEMENTED。故障注入/屏障仅隔离测试入口，无生产请求字段或CLI开关；未开放start/reassess假诊断。
- GET run/SSE/cancel/retry均owner保护；写接口认证、Origin、CSRF及幂等。case get/list返回真实active_run摘要，原创建幂等响应不回写。report_gate继续NOT_IMPLEMENTED。
- 事件先锁run再取identity，保证同run提交顺序；SSE短查询循环消除重放切实时窗口，不占连接等待用户；Last-Event-ID校验归属，15秒注释心跳，终态发送完关闭，注销/过期下一轮关闭。只发送实际任务概要事件。

准确请求/响应、错误和状态图见[契约](wp-03-contract.md)、[API说明](../../api/wp-03-runs.md)和evidence/wp-03/openapi.json。

## 环境和实际命令

只读docker version/inspect确认现有xiutu-v5/postgres，127.0.0.1:5433，Server29.4.0，镜像ID sha256:00ba258a66dac104fd5171074a0084462a64a1369d8513f3d0a634e2f24d15bc。未重建容器、删除卷或停止旧服务。

本轮新库：`xiutu_test_wp03_9946ac2ee08747d9acd2bc62`。prepare_database拒绝覆盖；本轮新库执行alembic upgrade head。完整迁移回归另建xiutu_test_wp02mig_1894e1d9f1924716972b4af1，保留供审核，不删除。复用现有解释器/项目.venv，未创建两套新环境；PYTHONPATH明确指向当前backend，loaded-source.txt确认当前JobStore导入路径。凭据仅从本项目受保护配置静默读入子进程环境，不读取旧.env、不保存完整连接串。

所有标准命令cwd为E:/Work/xiutu-v5，实际argv、开始/结束、退出码在setup-commands.json、*-command.json及final-lint.json；JUnit均为本轮新路径、正斜杠引用，没有覆盖旧输出。

| 检查 | 退出码 | 本轮结果 |
| --- | --- | --- |
| docker version/inspect、prepare_database、alembic upgrade head | 0 | setup-commands.json及对应txt |
| pytest test_job_recovery首批 | 0 | targeted-01.xml：9 passed，0失败/错误/跳过，43.59s |
| 增补事件锁等待/回滚/取消回收/SSE过期 | 0 | targeted-02.xml：4 passed、9 deselected，0失败/错误/跳过，23.66s |
| powershell -File scripts/test.ps1（完整入口，仅一次） | 0 | full.xml：**146 passed，0失败/错误/跳过，85.89s，1已知警告** |
| 增补物理锁连接断开反例 | 0 | lock-disconnect.xml：1 passed，0失败/错误/跳过，4.06s |
| scripts/demo_tasks.py | 0 | demo.txt：queued→running→cancel_requested→cancelled，SSE 151—154 |
| 当前源码导入/OpenAPI导出、最终ruff check | 0 | loaded-source.txt、openapi.json、final-lint.json |

完整入口包含当时13个新增任务用例和原WP-02输入/认证/所有权/并发幂等、升降级及health，以及WP-01共享门禁、PG/vector、两个进程checkpoint、MCP实际往返与断连。保留1条Starlette/AnyIO BlockingPortal弃用警告。之后只补充此前缺少的物理断锁用例并定向运行，应用逻辑未改变；最终测试收集为147项，不声称已经执行147项完整运行。没有因未改变前端而重复构建，没有额外环境复现。

开发过程必要修正：初写SSE转义产生语法问题，在首轮测试前修正；ruff初检查指出测试格式问题，经format/check修正；一次README写入因默认GBK读取UTF-8失败，未覆盖文件，随后明确UTF-8完成。无产品测试失败被忽略或转为skip。原始测试输出全部保存，没有拿历史统计作本轮结果。

## D204—D206自测证据（不是审核结论）

| 项目 | 自测结果 | 关键证据 |
| --- | --- | --- |
| D204领取 | 通过 | 两进程在同一gate释放，赢家停after_claim，输家明确idle；attempt=1且仅一组started/succeeded。入队事件故障回滚run/job/event全体 |
| D205租约/锁 | 通过 | 耗时2.5秒处理、1秒测试租约中独立心跳持续续租；提交前杀进程回滚attempt，提交后杀进程attempt=2恢复；旧锁未释放且租约过期时竞争者idle、不消耗attempt；旧token拒绝，锁释放后新token成功；关闭自身物理锁连接后禁止发布并新token恢复 |
| D206事件/取消 | 通过 | queued/运行中/重复取消及取消先提交、成功先提交两种可控顺序；真实HTTP/SSE首条后断开重连无漏、非法/跨run游标拒绝、跨owner四接口404、终态关闭、15秒注释和17秒认证过期关闭、注销关闭 |
| 重试预算 | 通过 | 真实available_at约2/8秒、到期前不能领、第三次终止；永久/ingest/未知无重试；取消后显式retry新run继承attempt并防分叉；死亡重领耗尽仍停止 |
| 事件提交顺序 | 通过 | 两独立连接，同run先写事件事务未提交时第二连接pg_stat_activity实际Lock等待；提交后第二ID更大，重放未跳过未提交事件 |
| WP-02受影响回归 | 通过 | 完整入口认证/CSRF/owner/幂等409/回滚/活跃唯一、0002↔0003健康变化与外部sentinel保留；旧迁移未改 |

进程PID、屏障时间/文件和原始日志已从本轮临时目录复制至process-traces/，来源/哈希在process-traces.json。实际演练仅结束自己启动的worker/API，断锁反例仅关闭自己新建连接，没有杀数据库服务或未知进程。合成测试中的test.first/test.second只用于提交顺序验证，不是生产worker发送的业务事件。

## 用户可亲自执行

在README流程准备已迁移的独立xiutu_test_*库、设置DATABASE_URL后：

```powershell
uv run --frozen python -B scripts/demo_tasks.py
```

本轮已执行此原脚本：提交测试任务→HTTP查看queued→启动本次worker→请求取消→SSE观察queued/started/cancel_requested/cancelled→终态查询cancelled；只清理其子进程，保留合成记录。这是后台任务能力，不是导入或汽车诊断。常规worker/提交CLI及授权cookie操作见README。

## 保护、必须解决项和非阻断建议

结束protection-final.json及delivery-hashes.json记录本包改动与封存清单；原686项除声明的本包实现/当前文档修改外保持一致，旧63项、0001/0002、db_target、历史报告/接受/证据及Git index不变。未提交、推送或修改全局Git配置。测试输出/日志检查实际密码零匹配；HTTP鉴权秘密只留进程内，没有写文档或Git。

目前无已知阻断本包交付的问题；仍须一次审核，用户接受权保留。非阻断建议：未来规模扩大时测量队列轮询/活跃摘要查询开销；事件保留/清理及运营监控另按后续部署包规划，不在本包扩展实现。不声称生产故障/外部收费调用exactly-once保证。

E10继续NOT_VERIFIED，须先授权模型/范围/预算，最迟WP-09；资料门槛继续NOT_MET，来源/许可、精确车型/发动机适配、规格、电路、拆装/复核章节及缺图最迟WP-10/真实效果验收前补齐。无付费调用。WP-04—17未开始。**到此停止，等待一次审核。**
