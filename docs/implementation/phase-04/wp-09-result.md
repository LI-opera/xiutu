# WP-09 交付结果

状态：IMPLEMENTED_NOT_ACCEPTED。记录时间：2026-09-19T00:30:25.3580172+08:00。仅WP09，等待集中审核与用户决定；不进入WP10。本任务实施与自测，没有生成审核通过或用户接受结论。

## 现在能用什么

模型factory可使用本机BGE-M3产生真实1024维向量，同时保留E5 384维旧索引及冻结会话查询。新索引继续走持久任务、资格、取消、租约和原子发布门禁；失败不会把半成品切换为当前索引。

DeepSeek已真实执行原生多工具调用，经现有执行器和独立HTTP业务MCP获取来源，再返回经过Pydantic验证的JSON。Skills支持元数据选择、正文/引用hash及工具收窄。演示使用明确synthetic资料与数值，不是正式Agent、真实维修效果或WP10语义支持校验。

## 依据与基准

已读STATUS、WP08接受/r2、P4实施与验收、总指南WP09模型/Skills及相关契约，结合现有Settings/E5/index/MCP和锁定SDK实施。未找到适用AGENTS。main无HEAD；不能只用git diff看新增文件。开始基准baseline.json，当前Git清单git-current.json，完整回归输入full-code-hashes.json。

WP08审核后STATUS与接受记录是用户授权差异，未回写旧接受范围。BGE为用户明确授权的本包扩展。结束核对：旧项目63项、历史报告/接受/证据3324项、0001—0007迁移均未变；Git index保持c451d6e78b8f29fc818002923a19fb1a888139ced20679ad545f75e9692a9ec6，见protection-final.json。

完整回归141项源码/测试/脚本基准封存。回归启动后仅tests/README说明与3份测试lint注释/空行有字节差异，后者AST一致见lint-only-diff.json；没有生产逻辑或断言变化，不隐瞒为字节完全一致。最终文件清单与封存另见delivery-hashes.json、seal.json。

## 实际改动

- config.py/main.py：显式项目.env加载，优先级构造参数>进程环境>项目.env>默认；测试模式/TEST_DATABASE_URL禁止读项目.env。密钥SecretStr，未知provider/维度/路径明确失败，不自动付费或fallback。
- infrastructure/model_factory.py、bge_gateway.py：LLM/Embedding协议及工厂，本地固定ONNX/hash、文档/查询接口、finite/数量/维度/非零向量检查，保留E5原指纹。
- 新0008_model_indexes、ORM及schema_version：按index隔离384/1024维，SQL CHECK触发器验证每行维度；有1024索引时拒绝破坏性降级，health预期0008，不改旧迁移。
- index_service/document_service/index_builder/index_state/retrieval/service及ReindexInput：服务器选型、任务冻结配置、按指纹查询、原发布门禁。trace.model现在为参与配置列表。未对业务资料批量重建。
- model_gateway.py/model_budget.py：锁定LangChain DeepSeek真实调用、原生ID/ToolMessage、JSON严格验证/一次修复、明确错误、有限重试、持久共享5元预留。
- skills/registry.py及skills/cooling-system-diagnosis：方法型受控Skill、版本/hash、引用路径、工具交集。上传资料不自动成为Skill；examples不作为evidence。
- MCP配置/生成脚本增加BGE路径；可选deploy/compose.mcp-bge.yaml只读挂载示例。无授权算法或工具预算放宽。native独立进程+BGE已实测，新增Linux覆盖配置未做动态验证。
- 新unit/integration/live回归；原维度拒绝测试精确改为0008 SQLSTATE23514。更新契约、API说明、运行文档、ADR0003、README/.env.example、CHANGELOG、STATUS、测试说明和依赖矩阵。无前端/正式Agent/观察写入改动。

## 实际模型、预算与E10

BGE-M3固定revision5617a9f61b028005a4858fdac845db406aefb181，1024维，CLS/L2，无前缀，480内容token窗口及加权聚合，bge-m3-onnx-v1；只dense，不称完整M3 sparse/ColBERT。官方来源/MIT及取舍见ADR0003，文件hash见bge-files.json与指纹。

实测加载3.861秒、两中文短文档0.0972秒、查询0.0370秒；工作集1547829248字节、峰值1560555520字节（进程整体，非压测）。原bge-probe.json内存0是Windows HANDLE采集失败，保留；采用检查系统调用成功后的bge-probe-v2.json。未重做模型选型或检索质量评测，不能声称BGE优于E5。

用户授权本轮所有窗口合计最多5元，含E10/失败/重试/后续复核，并明确批准本轮使用deepseek-flash。未修改私有.env旧chat值，真实探针显式覆盖flash。真实4请求含首次截断失败，usage均返回；保守预留¥0.198184，usage按峰时/未命中价估算¥0.024582，非平台账单实付确认。后续复核必须共用.local-data/wp09-budget.json，不得重置或每窗口重新5元。

官方核价与有效期见price-verification.json：输入2/输出8元每百万token，UTF8字节×4+4096保守输入上界，max_tokens768；2026-09-20 UTC后明确要求重新核价。SDK重试关闭；网关仅429/5xx最多一次额外尝试，每次预留。失败/崩溃/缺usage都不退预留，unknown不记0。单turn最多5模型请求/120秒门禁、6工具/3搜索；同步调用非硬实时抢占，迟到响应拒绝继续使用，详见契约。

| 项目 | 执行者自测结果 | 证据与范围 |
| --- | --- | --- |
| A401 | 通过，待审核 | live-2.xml、deepseek-live-*.json；同一provider答案两原生tool_calls，经真实remote_mcp执行search_manuals/get_measurement_spec，不是模型自述 |
| A402 | 实测及离线通过，待审核 | 两ID对应ToolMessage，结构化返回的chunk/spec IDs来自真实provenance。4次usage记录；缺usage、JSON、空响应、截断、429/503/401及重复ID/预算反例为离线测试，不声称真实服务端故障注入 |
| A403 | 自测通过，待审核 | Skill正文hash篡改、越界/未允许引用、工具交集拒绝；代码拒绝symlink/junction，HTTP/model不能指定根或安装上传文档；examples不作证据 |
| E10 | 真实契约自测完成，待审核收口 | 授权、调用/usage/费用、真实工具及JSON齐备；不是HTTP200替代，不回改历史NOT_VERIFIED，不证明远程strict所有特性 |
| BGE扩展 | 实测通过，待审核 | 真实向量、PG新旧路由、独立worker取消/失租约/中断恢复、冻结E5不变及激活SQL整体回滚 |

live-persistent-receipts.json进一步只读核对两条成功receipt，每条1尝试、execution used=2/search_used=1。没有用新的付费请求补做该核对。

## 运行结果及失败记录

本轮专用xiutu_test_wp09_5881de5029b6，迁移回归另建唯一子库；全部为合成数据和新临时目录。只清理本轮进程/schema，不删除已有数据库或卷。完整入口仅运行一次：**328通过、0失败、0错误、0跳过、1条既有Starlette/anyio弃用警告，exit0，969.25秒**。

以下各轮有重叠，不能相加为不同功能覆盖数：

- offline.xml：8通过/2失败；SDK截断异常映射及预算夹具预留误算。修正后offline-fix.xml 3通过。
- phase-fix.xml：工具收集后直接JSON路径2通过。
- indexes.xml：真实BGE新旧代际/取消/失租约/中断与迁移5通过。
- live.xml：首轮1失败。两真实工具已成功，额外自由文本总结截断；保留首次源码快照及费用。改为工具阶段直接进入JSON，不扩大输出上限，live-2.xml 1通过。
- final-targeted.xml：17通过/1夹具注册错误；只补pytest跨模块fixture导入后rollback-fix.xml 1通过。完整入口再次覆盖。
- lint.txt保留7条测试导入/fixture告警；纯注释/空行调整后lint-final.txt通过，AST一致，无断言弱化。
- bge-probe-v2.json修正内存采样方式，不覆盖旧测量。全程保留原失败，不循环重跑完整入口。

依赖无新增：沿用langchain-deepseek1.1.0、langchain-core1.6.3、httpx0.28.1、onnxruntime1.30.0、tokenizers0.23.2、numpy2.5.3。uv lock --check --offline及uv pip check通过，97解析/96安装；锁和导出无需制造第二份变更，实际import版本见installed-versions.json。

## 可亲自验证、未验证与停止

见[运行说明](../../runbooks/models.md)：新隔离库→0008→scripts/test.ps1（不付费）；显式live演示准备合成资料上传/解析/审核/BGE索引、可信case与独立MCP授权，再DeepSeek两工具→来源→JSON。真实调用必须使用共享账本及有效核价，不反复运行演示、不覆盖历史basetemp。

- 无当前已知核心阻塞；新增Linux BGE挂载覆盖配置未动态验证，不能借用WP08 E5容器结论。
- 真实资料门槛NOT_MET，来源/许可、车型/发动机、正式规格/线路/拆装/复核章节及缺图最迟WP10/真实效果前补齐。synthetic数值不是维修标准。
- 无WP10语义支持/提案校验、WP11图、正式诊断UI、生产恢复或千问付费embedding；不接受整个P4。
- 未重测未变前端、第二环境、旧包质量评测。SSE本轮通过但首次根因仍未确认；Compose历史启动底层原因未确证。
- owner粗锁、性能/监控/清理/uncertain、旧receipt安全拒绝和旧比较复核待办保留。同任务历史流程限制保留，本报告仅执行者自测。

停止在IMPLEMENTED_NOT_ACCEPTED，等待集中审核和用户决定。WP10—17保持NOT_STARTED；未提交/推送、修改旧项目/Git index或生成接受记录。


## 命令索引

cwd均为E:\Work\xiutu-v5；每项起止时间（已有记录项）、exit、原始输出及JUnit均在evidence/wp-09对应文件。数据库配置由run.py静默注入，未把敏感URL写入命令。

| 记录 | 实际命令 | exit |
| --- | --- | --- |
| bge-metrics.json | `E:\Work\xiutu-v5\.venv\Scripts\python.exe -B docs/implementation/phase-04/evidence/wp-09/bge_probe_v2.py` | 0 |
| create.json | `E:\Work\xiutu-v5\.venv\Scripts\python.exe -B scripts/probes/prepare_database.py --name xiutu_test_wp09_5881de5029b6` | 0 |
| dependencies.json | `uv pip check` | 0 |
| final-targeted.json | `E:\Work\xiutu-v5\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider tests/unit/test_wp09_contracts.py tests/integration/test_wp09_models.py::test_bge_activation_sql_rollback tests/integration/test_indexes.py::test_queued_cancel_and_dimension_guard -q --basetemp .test-runs/wp09-final-targeted-596a --junitxml=docs/implementation/phase-04/evidence/wp-09/final-targeted.xml` | 1 |
| full.json | `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/test.ps1` | 0 |
| indexes.json | `E:\Work\xiutu-v5\.venv\Scripts\python.exe -B -m pytest tests/integration/test_wp09_models.py tests/integration/test_migrations.py -q -s --tb=short -p no:cacheprovider --basetemp .test-runs/wp09-indexes-01 --junitxml=E:/Work/xiutu-v5/docs/implementation/phase-04/evidence/wp-09/indexes.xml` | 0 |
| lint-final.json | `E:\Work\xiutu-v5\.venv\Scripts\ruff.exe check tests/integration/test_indexes.py backend/app/infrastructure/schema_version.py tests/live/test_deepseek_probe.py backend/app/domain/retrieval.py backend/app/main.py backend/app/services/index_service.py backend/app/services/index_builder.py backend/app/mcp_server/config.py scripts/configure_manual_mcp.py backend/app/services/document_service.py backend/app/config.py backend/app/infrastructure/index_state.py backend/app/infrastructure/orm.py backend/app/retrieval/service.py tests/integration/test_manual_mcp.py backend/app/infrastructure/bge_gateway.py backend/app/infrastructure/model_budget.py backend/app/infrastructure/model_factory.py backend/app/infrastructure/model_gateway.py backend/app/skills/registry.py backend/app/skills/__init__.py migrations/versions/0008_model_indexes.py tests/integration/test_wp09_models.py tests/live/test_deepseek_tools.py tests/unit/test_wp09_contracts.py` | 0 |
| lint.json | `E:\Work\xiutu-v5\.venv\Scripts\ruff.exe check tests/integration/test_indexes.py backend/app/infrastructure/schema_version.py tests/live/test_deepseek_probe.py backend/app/domain/retrieval.py backend/app/main.py backend/app/services/index_service.py backend/app/services/index_builder.py backend/app/mcp_server/config.py scripts/configure_manual_mcp.py backend/app/services/document_service.py backend/app/config.py backend/app/infrastructure/index_state.py backend/app/infrastructure/orm.py backend/app/retrieval/service.py tests/integration/test_manual_mcp.py backend/app/infrastructure/bge_gateway.py backend/app/infrastructure/model_budget.py backend/app/infrastructure/model_factory.py backend/app/infrastructure/model_gateway.py backend/app/skills/registry.py backend/app/skills/__init__.py migrations/versions/0008_model_indexes.py tests/integration/test_wp09_models.py tests/live/test_deepseek_tools.py tests/unit/test_wp09_contracts.py` | 1 |
| live-2.json | `E:\Work\xiutu-v5\.venv\Scripts\python.exe -B docs/implementation/phase-04/evidence/wp-09/live_launch_2.py` | 0 |
| live-receipts.json | `E:\Work\xiutu-v5\.venv\Scripts\python.exe -B docs/implementation/phase-04/evidence/wp-09/read_live_receipts.py` | 0 |
| live.json | `E:\Work\xiutu-v5\.venv\Scripts\python.exe -B docs/implementation/phase-04/evidence/wp-09/live_launch.py` | 1 |
| lock-check.json | `uv lock --check --offline` | 0 |
| migrate.json | `E:\Work\xiutu-v5\.venv\Scripts\python.exe -B -m alembic upgrade head` | 0 |
| offline-fix.json | `E:\Work\xiutu-v5\.venv\Scripts\python.exe -B -m pytest tests/unit/test_wp09_models.py::test_response_errors tests/unit/test_wp09_models.py::test_budget_atomic_restart_and_duplicate -q --tb=short -p no:cacheprovider --basetemp .test-runs/wp09-offline-fix --junitxml=E:/Work/xiutu-v5/docs/implementation/phase-04/evidence/wp-09/offline-fix.xml` | 0 |
| offline.json | `E:\Work\xiutu-v5\.venv\Scripts\python.exe -B -m pytest tests/unit/test_wp09_models.py -q --tb=short -p no:cacheprovider --basetemp .test-runs/wp09-offline-01 --junitxml=E:/Work/xiutu-v5/docs/implementation/phase-04/evidence/wp-09/offline.xml` | 1 |
| phase-fix.json | `E:\Work\xiutu-v5\.venv\Scripts\python.exe -B -m pytest tests/unit/test_wp09_models.py::test_tool_phase_direct_to_json tests/unit/test_wp09_models.py::test_multicall_ids_and_skill_narrow -q --tb=short -p no:cacheprovider --basetemp .test-runs/wp09-phase-fix --junitxml=E:/Work/xiutu-v5/docs/implementation/phase-04/evidence/wp-09/phase-fix.xml` | 0 |
| rollback-fix.json | `E:\Work\xiutu-v5\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider tests/integration/test_wp09_models.py::test_bge_activation_sql_rollback -q --basetemp .test-runs/wp09-rollback-fix-c45d --junitxml=docs/implementation/phase-04/evidence/wp-09/rollback-fix.xml` | 0 |
