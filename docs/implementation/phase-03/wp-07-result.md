# WP-07 五业务工具与执行器交付

状态：**IMPLEMENTED_NOT_ACCEPTED**。完成时间：2026-09-18T17:50:41.831430+08:00。仅执行者实现与自测，等待一次集中审核及用户决定；没有自行生成审核通过或接受结论，未进入WP-08。

## 现在能做什么

可信应用入口可执行五工具：冻结资料检索、同版本邻块上下文、当前case有效规格候选、持久化精确比较、真实数据库观察只读查询。结果有来源与大小限制；无记录为空，权限/配置/失效/超时/预算错误分别表达。LangChain实际适配器已调用，不是只画JSON外形。比较结果不等于维修结论；没有LLM、正式Agent、业务MCP或观察提交API。

用户按README创建全新测试库并迁移head后执行 `uv run --frozen python -B scripts/demo_tools.py`。演示实际HTTP/独立worker准备合成资料，再经可信上下文执行五工具，展示来源、空观察、拒绝、预算耗尽与撤销后拒绝。所有规格为synthetic；生产无观察返回空。见[工具说明](../../api/wp-07-tools.md)、[契约](wp-07-contract.md)。

## 依据、基准和改动

已读取STATUS、WP06接受/契约/r1审核、依赖矩阵、旧P3说明与验收清单、总指南WP07工具/权限/预算/重放条款。项目及E:/、E:/Work上级未发现适用AGENTS。WP06接受后的STATUS和新增接受记录属于用户授权差异，不重验已接受包。

baseline.json固定2114项文件、main无HEAD、暂存/未暂存/未跟踪与diff；Git index SHA256 `c451d6e78b8f29fc818002923a19fb1a888139ced20679ad545f75e9692a9ec6`。结束旧项目63项、迁移0001—0006、原报告/证据/接受记录与db_target均未变。实际差异见protection-final.json和delivery-hashes.json。完整入口前封存119项源码/测试/脚本/依赖；之后只有tests/README.md说明变更，没有未验证实现改动。

新增：tools/context.py、schemas.py、registry.py、manual_tools.py、executor.py；repositories/observations.py；0007_tools；contract/test_tools.py、integration/test_business_tools.py、tests/wp07_reserve_process.py；scripts/demo_tools.py；契约/工具文档/schema及本报告。

既有扩展：UOW允许外层事务，EvidenceService.compare可加入该事务；DocumentService同版本邻块读取；RetrievalService内部narrow_scope（默认保持原行为）；ORM/health统一0007、迁移测试接续0006；pyproject/uv.lock/requirements直接声明原锁已含LangChain。README/CHANGELOG/STATUS/矩阵/测试说明同步。没有工具HTTP端点，原OpenAPI不新增虚假接口。

## 实现边界

- ContextFactory用真实AuthStore/cookie，服务端冻结actor/case/revision/manifest/profile/allowlist/预算，capability只存哈希。模型extra=forbid，省略scope继承case，不能抹去精确约束。
- 冻结索引与当前资格同时检查，chunk/evidence ID分离；规格限当前case有效approved，多个候选不任取。quantity由规格读取，经WP06服务比较。
- 0007增加tool_executions/tool_calls/observations。execution+call_key唯一；异参数冲突，预算行锁原子预留。失败/超时计数，只读明确瞬态最多重试1次。预留前拒绝不新增审计行/预算，重放不新增尝试。
- 比较、幂等响应和成功receipt同一事务；发布SQL后用DB clock_timestamp检查原deadline，取消/超时整笔回滚。call行锁决定取消与成功先后，无后台迟到覆盖。未承诺网络提交瞬间的实时性或外部系统exactly-once。
- 进程死亡running过deadline转uncertain，不盲目重做；新进程预算仍保留。只读推理无硬实时抢占，晚返回不得成功。入口鉴权/预留锁等待不计处理deadline。
- 审计保留hash、必要结构化值与引用，不保存chunk正文、观察payload、cookie/capability；重放授权后按不可变源ID重装。观察旧行不可改删，supersedes同case/area/step且revision递增，未来WP12写入须复测。

## 环境和依赖

复用已确认xiutu-v5-postgres-1 project/service标签及loopback5433，见environment.txt。新库`xiutu_test_wp07_fee89df04e514aecb45c`；fixture新owner/临时存储，不复用旧业务库。PostgreSQL16.14/vector0.8.2、迁移0007_tools，导入当前backend路径和SHA见runtime-facts.json。未重建容器、停止未知服务、删除库卷或读取旧.env。

langchain-core==1.6.3成为直接依赖，原版本不变；uv lock --check、pip check及锁导出一致通过。StructuredTool.invoke/ToolCall→ToolMessage、参数拒绝/schema实测。SDK默认转换丢对象配置，导出保留actual args_schema的extra=forbid及conditions类型映射，不宣称远程provider strict兼容。schema摘要SHA256：`d021233b0daa64b58ab8610349ffb1247fd1cc283cf12fb3e09b552471b84868`。固定本地384维E5沿用，不重选模型/跑留出评测，本地embedding不等于E10。

## M301—M305 执行者自测

| 项 | 结果和证据 |
| --- | --- |
| M301 | 五工具真实服务+LangChain调用，demo exit0/1通过；five-tools-*.json、schema。非空观察fixture真实读DB/revision/supersedes，生产空结果不硬编码 |
| M302 | 伪cap、跨owner/case、越界corpus/错误chunk版本、allowlist、未知工具、scope冲突/省略、注销/revision变化拒绝；撤销阻断重放，重建不替换冻结索引 |
| M303 | 真空观察、真缺模型路径、权限拒绝、超时/取消/预算不足分离；错误schema/瞬态注入只证明对应契约，不冒充真实服务 |
| M304 | 工具与WP06直接HTTP相同边界符合独立预期；pending/其他case/撤销规格拒绝；比较重复/并发一条记录 |
| M305 | 两连接真实PG锁等待/屏障，最后预算只给一次；重放不重复；搜索重试总/子预算准确；子进程预留退出返回uncertain；比较超时/取消/receipt SQL延迟整体回滚 |

最终当前版本标准完整入口 **260通过，0失败/错误/跳过**，1条既有Starlette/AnyIO弃用警告。包含认证/幂等、迁移/health、WP04三发布窗口和WP03锁/租约、PG/vector/checkpoint/旧MCP基础探针；不等于M306—M311业务MCP完成。未变前端和第二环境未复跑。

各轮有重叠，不相加为独立功能数。实际cwd均E:/Work/xiutu-v5，命令/起止/退出码json、txt/JUnit原始输出保留：

| 批次 | tests/failures/errors/skipped | 秒 |
| --- | --- | --- |
| boundaries | 9/0/0/0 | 10.749 |
| full | 260/0/0/0 | 569.320 |
| gates-response-shape | 1/0/0/0 | 10.365 |
| gates | 3/1/0/0 | 19.470 |
| integration-fixture-fix | 16/0/0/0 | 89.113 |
| targeted-collection-fix | 16/1/0/0 | 52.206 |
| targeted-final | 23/0/16/0 | 15.565 |
| targeted-first | 1/0/1/0 | 0.664 |

CLI另1项通过，demo.txt/demo-artifacts保留。失败与修正：同名test_tools收集冲突（exit2，集成改名）；SDK默认schema缺additionalProperties（15通过1失败，保留args_schema）；import整理误删跨文件fixture（7通过16setup errors，定义本地fixture）；新增测试将证据响应误当chunk字段（2通过1失败，使用真实citation后1通过）。均保留原失败，按原因修正后仅复跑影响项，标准完整入口只运行一次。整理脚本曾有字符串嵌套语法错误，未写入交付或改变实现/测试，改用直接文件写入；不计测试失败。

| 标签 | 实际命令 | exit | 起止 |
| --- | --- | --- | --- |
| environment | `docker inspect xiutu-v5-postgres-1 --format {{json .Config.Labels}} {{json .State.Status}} {{json .NetworkSettings.Ports}}` | 0 | 2026-09-18T17:20:55.201500+08:00 — 2026-09-18T17:20:55.370296+08:00 |
| create | `E:\Work\xiutu-v5\.venv\Scripts\python.exe -B scripts/probes/prepare_database.py --name xiutu_test_wp07_fee89df04e514aecb45c` | 0 | 2026-09-18T17:20:55.451966+08:00 — 2026-09-18T17:20:56.115967+08:00 |
| migrate | `E:\Work\xiutu-v5\.venv\Scripts\python.exe -B -m alembic upgrade head` | 0 | 2026-09-18T17:20:56.188866+08:00 — 2026-09-18T17:20:57.285135+08:00 |
| targeted-first | `E:\Work\xiutu-v5\.venv\Scripts\python.exe -B -m pytest tests/contract/test_tools.py tests/integration/test_tools.py -q -s -p no:cacheprovider --basetemp E:/Work/xiutu-v5/.test-runs/wp07-targeted-5928b08b --junitxml=E:/Work/xiutu-v5/docs/implementation/phase-03/evidence/wp-07/targeted-first.xml` | 2 | 2026-09-18T17:23:23.033308+08:00 — 2026-09-18T17:23:25.345281+08:00 |
| targeted-collection-fix | `E:\Work\xiutu-v5\.venv\Scripts\python.exe -B -m pytest tests/contract/test_tools.py tests/integration/test_business_tools.py -q -s -p no:cacheprovider --basetemp E:/Work/xiutu-v5/.test-runs/wp07-targeted-92a091cc --junitxml=E:/Work/xiutu-v5/docs/implementation/phase-03/evidence/wp-07/targeted-collection-fix.xml` | 1 | 2026-09-18T17:23:47.652741+08:00 — 2026-09-18T17:24:41.867444+08:00 |
| targeted-final | `E:\Work\xiutu-v5\.venv\Scripts\python.exe -B -m pytest tests/contract/test_tools.py tests/integration/test_business_tools.py tests/integration/test_migrations.py -q -s -p no:cacheprovider --basetemp E:/Work/xiutu-v5/.test-runs/wp07-targeted-c6d23f10 --junitxml=E:/Work/xiutu-v5/docs/implementation/phase-03/evidence/wp-07/targeted-final.xml` | 1 | 2026-09-18T17:27:35.969505+08:00 — 2026-09-18T17:27:53.164410+08:00 |
| integration-fixture-fix | `E:\Work\xiutu-v5\.venv\Scripts\python.exe -B -m pytest tests/integration/test_business_tools.py -q -s -p no:cacheprovider --basetemp E:/Work/xiutu-v5/.test-runs/wp07-targeted-74f807d5 --junitxml=E:/Work/xiutu-v5/docs/implementation/phase-03/evidence/wp-07/integration-fixture-fix.xml` | 0 | 2026-09-18T17:28:48.875657+08:00 — 2026-09-18T17:30:19.936113+08:00 |
| boundaries | `E:\Work\xiutu-v5\.venv\Scripts\python.exe -B -m pytest tests/contract/test_tools.py tests/integration/test_business_tools.py::test_real_missing_model_configuration tests/integration/test_business_tools.py::test_last_budget_slot_pg_wait -q -s -p no:cacheprovider --basetemp E:/Work/xiutu-v5/.test-runs/wp07-boundaries-601bbf83 --junitxml=E:/Work/xiutu-v5/docs/implementation/phase-03/evidence/wp-07/boundaries.xml` | 0 | 2026-09-18T17:34:39.928921+08:00 — 2026-09-18T17:34:52.382419+08:00 |
| gates | `E:\Work\xiutu-v5\.venv\Scripts\python.exe -B -m pytest tests/integration/test_business_tools.py::test_context_allowlist_owner_and_spec_gates tests/integration/test_business_tools.py::test_concurrent_comparison_identity tests/contract/test_tools.py::test_scope_omission_cannot_erase_server_constraint -q -s -p no:cacheprovider --basetemp E:/Work/xiutu-v5/.test-runs/wp07-gates-65f3dde1 --junitxml=E:/Work/xiutu-v5/docs/implementation/phase-03/evidence/wp-07/gates.xml` | 1 | 2026-09-18T17:36:56.352355+08:00 — 2026-09-18T17:37:17.614285+08:00 |
| gates-response-shape | `E:\Work\xiutu-v5\.venv\Scripts\python.exe -B -m pytest tests/integration/test_business_tools.py::test_context_allowlist_owner_and_spec_gates -q -s -p no:cacheprovider --basetemp E:/Work/xiutu-v5/.test-runs/wp07-gate-shape-f4109e1c --junitxml=E:/Work/xiutu-v5/docs/implementation/phase-03/evidence/wp-07/gates-response-shape.xml` | 0 | 2026-09-18T17:37:38.798826+08:00 — 2026-09-18T17:37:50.887883+08:00 |
| demo | `E:\Work\xiutu-v5\.venv\Scripts\python.exe -B scripts/demo_tools.py` | 0 | 2026-09-18T17:38:19.622670+08:00 — 2026-09-18T17:38:38.385068+08:00 |
| lock-check | `uv lock --check` | 0 | 2026-09-18T17:38:33.316172+08:00 — 2026-09-18T17:38:33.367820+08:00 |
| dependency-check | `uv pip check` | 0 | 2026-09-18T17:38:33.456670+08:00 — 2026-09-18T17:38:33.537252+08:00 |
| export-check | `uv export --frozen --no-dev --no-emit-project --output-file docs/implementation/phase-03/evidence/wp-07/requirements-export.txt --quiet` | 0 | 2026-09-18T17:38:33.620145+08:00 — 2026-09-18T17:38:33.663133+08:00 |
| runtime-inspection | `E:\Work\xiutu-v5\.venv\Scripts\python.exe -B docs/implementation/phase-03/evidence/wp-07/runtime_facts.py` | 0 | 2026-09-18T17:42:37.213518+08:00 — 2026-09-18T17:42:38.966099+08:00 |
| full | `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/test.ps1` | 0 | 2026-09-18T17:40:49.476308+08:00 — 2026-09-18T17:50:21.636513+08:00 |

## 剩余限制与停止

无已知必须解决的自测失败，等待审核；本报告不是独立审核。既有同任务实施/审核流程限制保留，不声称另一窗口通过。

非阻断待办：owner粗锁/大集合性能，调用记录保留与不明调用处置，观察后续写入及area/step实体约束，超时硬实时中止，监控/清理。预算是可信execution范围，不是尚不存在的Agent turn；演示依赖开发测试harness，不是用户工作台。

E10 NOT_VERIFIED，另授权模型/范围/预算后最迟WP09；真实资料NOT_MET最迟WP10/真实效果验收前。SSE首次超时根因未确认，本轮通过不能倒推原故障已修复。合成规格/观察不是实际维修标准，within_range不是诊断；引用存在不证明语义支持，未来报告接入仍须重要规格IDs。无观察写入、业务MCP、Agent、前端或生产恢复验收。未改旧项目、历史证据、接受记录、旧迁移、Git index，无提交/推送/付费调用/私人上传。停止，不进入WP08。
