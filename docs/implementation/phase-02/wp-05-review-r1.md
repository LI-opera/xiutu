# WP-05 集中审核 r1

结论：**REVIEW_PASS（限定 WP-05 本地 embedding、持久索引与混合检索技术范围）**。本轮没有发现必须整改的正确性、所有权隔离或索引原子性问题，建议用户带列明限制接受；审核通过不等于用户已经接受，也不等于真实维修效果达标。

审核时间：2026-09-18T15:39:36.754053+08:00 开始，2026-09-18T15:51:05.155538+08:00 完成。工作目录 E:/Work/xiutu-v5。

**角色披露：本任务参与了 WP-05 实施；本轮切换为审核者，实际检查代码并重新运行验证，但不是不同任务独立审核。** 未在审核中修改实现、STATUS或接受记录。唯一新增交付是本报告和 `evidence/wp-05-review-r1/`；隔离测试数据和进程工件另保留。

## 依据和基准

核对适用 AGENTS（项目、上级及所涉目录未发现适用文件）、STATUS、WP-04 接受/契约/r2、WP-05 result/contract、README、依赖矩阵、ADR 0002、P2 实施说明/验收清单及总指南 WP-05、索引/适配/检索/事务/评测契约。验收按 D210—D212；没有重新接受既有包或开展 WP-06。

- Git 根 E:/Work/xiutu-v5，main；HEAD 不存在，`rev-parse --verify HEAD` 退出128属预期。
- 开始完整核对执行者 `evidence/wp-05/delivery-hashes.json` 的1537文件，以及该清单自身和 protection-final，共1539项；无差异。暂存、未暂存、全部未跟踪文件清单与 diff stat 均在本轮 baseline.json，不只依据 git diff。
- Git index SHA256 `c451d6e78b8f29fc818002923a19fb1a888139ced20679ad545f75e9692a9ec6`。结束再次核对1539项、旧项目63项和index，均无变化；历史报告、接受记录、0001—0005迁移、db_target、STATUS包含于清单。详见本轮 protection-final.json。没有add/commit/reset/push或全局safe.directory修改。
- 执行者旧证据：192项完整测试及最终4项定点、模型选型/加载内存探针、eval-freeze、旧评测等，仅用于历史对照。**本轮全量194项是对当前最终基准的新运行，不转抄192或4项。** 旧model-probe内存0错误及v2修正均保留，未以本轮名义重测其加载内存值。
- 仅复用已确认的 xiutu-v5-postgres-1，Compose project=xiutu-v5/service=postgres，loopback5433，镜像sha256:00ba258a66dac104fd5171074a0084462a64a1369d8513f3d0a634e2f24d15bc。没有重建/停止既有服务或改密码。
- 新建本轮库 `xiutu_test_wp05r1_6600b5d90ab3484da1`。完整入口的迁移测试另建其唯一测试库并保留；只删除自身临时schema，结束自身子进程。凭据仅静默读取本项目受保护文件，无旧.env或付费请求。

## 本轮命令、时间与原始证据

所有命令cwd均为 E:/Work/xiutu-v5；包装器 `evidence/wp-05-review-r1/run.py` 设置隔离目标、当前backend导入路径和新输出，拒绝重复证据标签。workspace.json记录临时目录和解释器；runtime.json核对导入当前源码。命令无密码/连接串，实际连接参数不写入证据。

| 操作 | 本地起止时间 | 退出码 | 证据（均本轮目录） |
|---|---|---|---|
| create | `2026-09-18T15:39:59.167463+08:00` — `2026-09-18T15:39:59.747406+08:00` | 0 | `create.json` / `create.txt` |
| migrate | `2026-09-18T15:39:59.836707+08:00` — `2026-09-18T15:40:00.819298+08:00` | 0 | `migrate.json` / `migrate.txt` |
| full | `2026-09-18T15:40:00.899577+08:00` — `2026-09-18T15:45:35.191146+08:00` | 0 | `full.json` / `full.txt` |
| targeted | `2026-09-18T15:45:54.340157+08:00` — `2026-09-18T15:46:32.568260+08:00` | 0 | `targeted.json` / `targeted.txt` |
| evaluation | `2026-09-18T15:46:32.656556+08:00` — `2026-09-18T15:48:37.517091+08:00` | 0 | `evaluation.json` / `evaluation.txt` |
| verify-evaluation | `2026-09-18T15:48:51.003512+08:00` — `2026-09-18T15:48:52.137552+08:00` | 0 | `verify-evaluation.json` / `verify-evaluation.txt` |

实际子命令（由上述包装器运行）：

```text
create:
E:\Work\xiutu-v5\.venv\Scripts\python.exe -B scripts/probes/prepare_database.py --name xiutu_test_wp05r1_6600b5d90ab3484da1

migrate:
E:\Work\xiutu-v5\.venv\Scripts\python.exe -B -m alembic upgrade head

full:
pwsh -NoProfile -File scripts/test.ps1

targeted:
E:\Work\xiutu-v5\.venv\Scripts\python.exe -B -m pytest docs/implementation/phase-02/evidence/wp-05-review-r1/test_audit_index.py -q -s -o cache_dir=.test-runs/wp05-review-466e2a0bb015407b8cab9be84b783443/cache --basetemp=.test-runs/wp05-review-466e2a0bb015407b8cab9be84b783443/targeted --junitxml=E:/Work/xiutu-v5/docs/implementation/phase-02/evidence/wp-05-review-r1/targeted.xml

evaluation:
E:\Work\xiutu-v5\.venv\Scripts\python.exe -B scripts/demo_retrieval.py --evaluate --output E:/Work/xiutu-v5/docs/implementation/phase-02/evidence/wp-05-review-r1/evaluation-results.json

verify-evaluation:
E:\Work\xiutu-v5\.venv\Scripts\python.exe -B docs/implementation/phase-02/evidence/wp-05-review-r1/verify_evaluation.py
```

- 标准完整入口仅运行一次：**194 passed，0 failed，0 error，0 skipped；1 warning，331.58秒**。full.xml与full.txt相互核对。警告为Starlette引用anyio.abc.BlockingPortal的已知弃用警告。
- 补充审核专用用例：**2 passed，0 failed/error/skipped，0 warning，36.98秒**。targeted.xml/txt，test_audit_index.py；未改被审测试。
- frozen标准入口实际使用 `uv run --frozen`；未新建第二venv或重跑未变前端。此处只证明当前锁定环境实际运行，不声称第二环境复现。
- 真实运行HTTP上传→解析/SSE→审核→索引/SSE→检索与原文核对：evaluation-results.json、evaluation-process.log；24次文档链路、12查询两模式。

## D210—D212

| 项目 | 结论 | 代码审查与本轮证据 |
|---|---|---|
| D210 真实embedding | PASS（本地技术范围） | embedding_gateway.py:41、62、83：固定模型revision与权重/tokenizer哈希；CPU ONNX实际推理，query/passages前缀、窗口聚合和L2；数量/维度/NaN/Inf/零向量拒绝。full.xml中的test_retrieval与test_indexes；runtime.json、actual-vector.json、本轮真实评测。缺模型实际应用返回503而非baseline。 |
| D211 混合检索 | PASS（冻结合成评测） | sparse.py:38完整DTC/中文片段TF-IDF；service.py:19所有权/资格/适配先过滤、精确cosine前30、RRF60融合前20再确定性排序。冻结集原哈希不变；原始排名重新核算，结果如下。不是cross-encoder，不生成case_evidence。 |
| D212 原子切换 | PASS（已测故障范围） | index_service.py:14事务创建run/job/event/index，version锁及building部分唯一索引；index_state.py:43/65批次隔离、集合/数量/模型/维度校验、激活前重查审核；job_store.py:210/253物理连接、原租约快照、数据库时钟最终栅栏。完整用例的真实中断/恢复/并发/撤销/取消，加本轮两个末尾SQL反例均通过。 |

### 模型核对

本地 `intfloat/multilingual-e5-small`，revision `614241f622f53c4eeff9890bdc4f31cfecc418b3`，384维，onnxruntime CPU；实际依赖版本、文件字节数与SHA见runtime.json。抽取本轮真实数据库存储向量384个有限值、平方范数近1，见actual-vector.json；不使用随机/硬编码向量冒充真实模型。

本轮在线只读复核固定revision[官方模型卡](https://huggingface.co/intfloat/multilingual-e5-small/raw/614241f622f53c4eeff9890bdc4f31cfecc418b3/README.md)的MIT许可标记。ADR所述BGE-M3未实测仍是未验证候选；不声称本模型优于它。长chunk窗口加权是项目策略，不能推广成作者原模型的长文本质量保证。

### 冻结评测复现

冻结SHA256：`29ab9e0e06c63d77340fc5880a4a7e18ca5808961db2b0b7c59bfd3d08c1d1b1`，与执行者eval-freeze及当前文件一致，冻结时间早于旧评测，本轮没有更换语料、标签、模型或排序参数。24段语料/12留出查询，标签由实施者编写，**没有人工维修真值**；与选型调试样例分列。

| 模式 | N | Recall@5宏平均 | Hit@5 | MRR@10 | 延迟p50/p95 ms | Recall未完整查询 |
|---|---|---|---|---|---|---|
| baseline | 12 | 0.847222 | 0.916667 | 0.861111 | 21.416 / 24.190 | q07, q11, q12 |
| hybrid | 12 | 0.930556 | 1.000000 | 0.881944 | 28.802 / 30.436 | q11, q12 |

本轮verify_evaluation.py从冻结标签和返回排名重新计算三指标，并真实查询24个版本确认每个恰有1块，避免把文档级命中冒称多块召回。核算见evaluation-verified.json；每个失败查询的文本、标签、排名和延迟见evaluation-results.json。本次hybrid改善Recall，达到合成集初始0.85目标，**不等于真实维修Recall>=0.85**。延迟仅小样本暖模型服务调用，不是含上传/冷加载的端到端或并发性能。

### 发布链路与接口检查

- 索引任务复用原队列及独立心跳。推理不持数据库事务；每批写入有效lease/token/run检查和最终校验后提交，但building向量不可检索。恢复只清本次building批次，不覆盖旧active。
- 最终激活锁job/run→version→index；version锁后重新校验；最后全部发布SQL后使用clock_timestamp对保存deadline判断。终态清空lease_until不丢失截止依据；同一物理连接、advisory锁与行锁持续到提交，失效整体回滚。
- 本轮完整test_indexes覆盖独立进程kill/过期/取消/撤销、部分8/20批次中断恢复、实际版本行锁等待与到期、两个并发重建202/409、旧active持续查询、queued取消和实际错误维度SQL。并发用例设置屏障并观察PG锁等待，不仅启动线程。
- 新审核反例deadline：pg pid11510实际advisory等待；数据库now=07:46:10.368030Z，原lease_until=07:46:10.360471Z。解锁后未切active、未将index标ready、未留成功事件；新worker PID23444恢复，成功事件恰1。
- 新审核反例sql_error：在本次run成功事件INSERT触发实际22000；active/ready/run成功事务整体回滚，旧索引仍可查；新worker PID3412恢复且仅1成功事件。同key重建重放原响应也实测。详见late-index-deadline.json、late-index-sql_error.json。
- 写接口重新执行认证/Origin/CSRF，owner取认证上下文，跨owner重建404，搜索仅返回自己资料和排除原因。synthetic需服务端test profile及共享隔离库门禁，公开参数extra=forbid；正式默认排除synthetic/待审/撤销/缺来源许可/needs_ocr。
- 车型各字段独立比较，明确冲突先排除；缺项unknown仅通用参考，engine_family不冒充code；结果返回前再查审核快照和active变化。无候选200空与模型/索引不可用503区分，非静默降级。
- 0005接续0004、冻结DDL/ORM和health版本同步；完整入口真实升降级、外部sentinel、认证/事务幂等、MCP、PG向量与跨进程checkpoint回归均通过。旧包只作为受影响回归，没有重新授予其接受。

## A. 必须整改

本轮未发现必须整改项。无现场修复、无循环重跑直到通过。

## B. 非阻断建议与残余风险

1. **N01 文档一致性，低**：README.md:3仍称等待WP04且无embedding/检索；:41仍称health预期0004，与当前0005及同文档WP05段落矛盾。实际迁移命令为upgrade head、health代码及测试均正确，未形成运行失败。建议后续仅同步旧概述和旧版本说明；复核全文状态/revision是否一致，无需因此重开整包测试。
2. **N02 规模与运维，低/后续**：retrieval/service.py:26逐版本查询、全量载入候选文本计算TF-IDF；index_state.py:79最终检查全量向量，暂存失败数据保留。本轮小规模正确性已验证，未做容量压测、GPU或生产监控/清理。未来有规模依据时优化，不能以本次延迟推广吞吐保证。
3. SSE首次超时**本轮未复现，首次根因未确认**。本轮心跳/鉴权过期实际约17.062秒通过；不能据此称历史根因已修复。保留原待办。
4. 当前没有真实维修语料人工真值、生产恢复/性能保证、跨语言质量保证或任意模型切换验证；模型配置只支持固定384维，换维度需独立迁移/配置，不复用旧列。

## 接受建议与停止点

建议用户接受限定后台本地embedding、索引任务与混合检索技术交付，并保留同任务实施/审核限制及上述待办。**本报告不是用户接受记录**，WP05 STATUS保持IMPLEMENTED_NOT_ACCEPTED，WP06未启动。

E10仍NOT_VERIFIED，必须先另获模型/范围/预算授权，最迟WP09收口；真实资料门槛仍NOT_MET，来源/许可、车型/发动机和正式章节/缺图最迟WP10/真实效果验收前补齐。本地embedding和合成评测不能替代这两项。未调用付费服务，未修改旧项目、原证据、迁移、Git index或接受记录。
