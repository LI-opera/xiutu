# 测试边界

2026-10-12 当前入口说明：下方 WP-06 段落保留阶段交付时的历史记录；`integration/test_evidence_measurement.py` 现默认只收集合成历史证据及规格的读取和不可变性检查。旧公共病例创建、证据绑定成功等用例已归档于规划资料，不代表当前模板工作台行为；`scripts/demo_measurement.py` 也已转为运行该历史读取检查。其他早期阶段的测试声明仍须按当前迁移清单逐项复核，不把旧执行链成功预期算作当前产品验收。

WP-09 索引切换测试已改用内部合成历史病例冻结清单，保留五项索引及恢复断言；公共旧病例创建与病例级证据检索不再作为该文件的成功条件。

WP-07 `integration/test_business_tools.py` 已改用内部合成历史病例及证据夹具；工具调用、预算、并发和权限用例仍在隔离库运行。其他导入原旧写入夹具的测试仍需逐文件迁移。

WP-08 `integration/test_manual_mcp.py` 的 MCP 测试夹具也已改用相同内部合成历史引用；远程只读、授权、断线、超时和回执用例仍在隔离库运行。

工具回执 `integration/test_tool_receipts.py` 与 WP-10 四份集成测试已改用内部合成历史夹具准备病例和证据；前者 18 项、后者 47 项在隔离库通过。旧公共病例与证据写入口仍保持退役；这些历史能力测试不等于当前模板工作台的 AI 验收。迁移前测试原文见规划资料中的旧执行链历史测试归档。

WP-13 旧报告生成测试原已整文件跳过，现已完整归档并移出默认集成测试目录。历史报告读取及旧写入口拒绝继续由 `integration/test_legacy_report_reads.py`、`unit/test_legacy_case_policy.py` 验证。WP-11 两份纯旧执行测试现保留为可显式指定的 `integration/legacy_wp11_graph.py` 和 `integration/legacy_wp11_candidate_diagnostics_integration.py`，不再进入默认文件名收集；混合资料校验的 `test_wp11_contract_alignment.py` 仍待分类。WP-12 两份检查点隔离测试也保留为 `integration/legacy_wp12_quarantined_observation.py` 与 `integration/legacy_wp12_recovery_isolation.py`，其余 23 项旧区域／观察测试仍默认收集。WP-11 封存资料包有 1 个文件与清单哈希不符，未为使旧测试通过而修改资料。

WP-00/01历史证据保留。WP-02默认pytest与scripts/test.ps1均收集tests/unit、integration、contract、probes，不默认运行tests/live。

- scripts/test.ps1 -OfflineOnly：unit、contract、真实localhost MCP；排除integration及整个PG探针模块（包括需要真实连接失败的DB-down用例）。不连接数据库、不调用付费模型。
- scripts/test.ps1：必须显式TEST_DATABASE_URL，使用共享loopback:5433/xiutu_test_*门禁；先在新的测试库upgrade head。缺DB必须失败，不skip。集成升降级用同凭据从xiutu_dev管理入口CREATE另一唯一测试库，不DROP DATABASE。
- 四线程幂等和双事务活跃run测试使用真实PostgreSQL约束；回滚测试包括真实SQL约束错误，未用SQLite替代。
- 测试身份为独立UUID owner，不只是不同cookie。所有资料/车辆字符串均synthetic，不能用作维修依据。
- 每次脚本新建UUID basetemp，-B及no:cacheprovider避免旧目录缓存。无清理worker；测试库与合成记录保留供审核。
- unit/auth时间模拟仅用于会话过期；模型MockTransport仅证明离线契约。PG/vector/checkpoint/MCP均真实运行。
- E10 NOT_VERIFIED，tests/live原未授权占位不当作通过。证据见docs/implementation/phase-02/evidence/wp-02/。

## WP-02 r1整改验证

test.ps1自行检查并创建本项目.test-runs父目录，拒绝普通文件和重解析点，历史目录不清理；每次UUID子目录，真实pytest退出码透传。完整入口仍强制TEST_DATABASE_URL；OfflineOnly不需要数据库配置。

新增unit/test_wp02_remediation.py：12个字段/位置NUL反例均断言业务service未进入；9种数据库异常分类通过实际HTTP错误处理器检查脱敏响应。真实数据库和Uvicorn扩展检查见phase-02/evidence/wp-02-remediation-r1，含A/B两个干净副本首次入口、普通文件/junction/哨兵、12个NUL HTTP案例的独立事务计数和行数，以及真实SQL错误/数据库不可用。统计以本轮JUnit为准，不固定102/85。E10仍不运行。

## WP-03 验证

integration/test_job_recovery.py使用真实PG及tests/wp03_worker_process.py独立进程；文件屏障标明提交前后/发布前，进程证据含PID与时间。测试启动器先验证xiutu_test_*，生产CLI不开放故障注入。短租约仅允许测试库。新UUID owner/key、本轮唯一新库、仅终止本次子进程，不停止数据库服务。

覆盖双worker互斥、耗时心跳、前后提交中断、旧锁保留/过期token、物理锁连接断开、取消竞争、持久2/8秒退避/三次总尝试、显式retry继承预算、未实现处理器、入队回滚、事件提交锁等待、实际HTTP/SSE断线/终态/心跳/过期/跨owner。迁移测试衔接0002→0003并检验旧版未就绪。

完整入口本包运行一次146项通过；其后补充断锁专用用例1项通过（最终收集将多1项，不伪称同次147项全量）。未改变的前端不重建。具体命令、JUnit和进程时序在evidence/wp-03；完整/离线均不收集tests/live付费占位。

## WP-04

默认scripts/test.ps1已通过tests/unit与tests/integration目录自动收集WP-04，无需新入口。先创建并迁移全新xiutu_test_*库，设置TEST_DATABASE_URL；每个HTTP fixture使用新owner和tmp_path存储，worker为独立进程，只有隔离测试启动器带屏障。单元文件test_documents.py与集成test_document_ingest.py使用不同模块名，避免pytest收集冲突。

覆盖合成MD/长表/超长Unicode、文本/扫描/混合/损坏/加密PDF、上传字节限制/存储junction拒绝、真实HTTP所有权和审核、两个HTTP请求真实行锁等待、取消/旧锁/过期token/中断/耗尽、入队和发布阶段真实SQL错误回滚。所有测试库保留；只删除本轮probe schema和关闭自己子进程。迁移回归包含0004→0003→0004以及原环境升降级，旧迁移未改。

本包无前端改动，不重复前端构建或双venv。首次完整入口收集失败与后续结果分开保留在evidence/wp-04；统计来自本次JUnit，不沿用WP-03历史数字。


## WP-05

完整入口新增真实ONNX、真实HTTP和独立worker索引恢复用例；先执行scripts/fetch_embedding.py、在新xiutu_test_*库迁移0005。没有模型/数据库不能用skip替代。unit中的畸形向量是输出校验反例，不是生成假embedding的替代品。前端未改不重复构建。
新增测试涵盖首批8/20中断、旧active保留、恢复一套完整向量、租约/版本锁窗口、取消/撤销、并发重建真实PG锁等待、缺模型503不降级、错维度数据库拒绝、owner和synthetic门禁。完整入口还覆盖WP04三窗口回滚及WP03共享完成路径。合成留出evals/retrieval-synthetic-v1.json在首次运行前冻结；不要为指标改标签或删除失败查询。


## WP-06

unit/test_measurement.py覆盖字符串Decimal、温度偏移、精确边界/开闭/单边、NaN/Inf/bool拒绝、单位与工况。integration/test_evidence_measurement.py使用真实HTTP/固定E5/独立worker；新owner隔离，真实PG事务锁等待证明撤销与绑定/比较/审核/新case/新spec的串行边界；含旧索引、不可变数据库记录、引用与正式发布门禁。所有数值为synthetic，非维修标准。

脚本demo_measurement.py通过同一测试工具执行完整API演示，新建UUID工件目录，保留原文/日志/JSON/JUnit。完整入口仍scripts/test.ps1，需新xiutu_test_*库升级0006，不能用旧业务库。本包未重新选型模型或复跑WP05留出评测，不需要前端或第二venv。


## WP-07

标准入口自动收集contract/test_tools.py、integration/test_business_tools.py以及0007迁移回归。先用新xiutu_test_*库升级head，固定E5本地文件须存在，缺配置不是skip。测试会经真实HTTP准备合成资料/人工规格、独立worker解析索引，再执行五工具；不调用LLM。上下文和调用参数分离，拒绝owner/case/manifest/profile/预算注入。

新增验证包含真实PG预算/比较锁等待、最后名额、相同调用身份、重放撤销、冻结旧索引、规格门禁、纯数据库观察revision/supersedes、跨进程预留后退出的uncertain处理、超时/取消/成功receipt SQL延迟整体回滚。错误schema和瞬态重试采用可控注入，只证明错误/预算契约；真实缺模型路径与业务服务调用分别验证。已有WP06十进制比较器继续使用，工具输入为十进制字符串。

`uv run --frozen python -B scripts/demo_tools.py`通过同一开发测试harness运行真实五工具演示，输出独立UUID目录。它不生成生产观察、正式MCP或Agent turn。完整/定点执行日志、JUnit与失败修正记录见phase-03/evidence/wp-07；各轮重叠测试不相加为独立功能数。M306—M311不在本包验收。


## WP-09

标准完整入口仍scripts/test.ps1，隔离新库升级0008；新增unit/test_wp09_contracts.py、integration/test_wp09_models.py。真实BGE/E5文件必须在配置路径存在，缺依赖不静默skip。覆盖factory/配置、原生多工具ID/JSON错误/计费未知（离线MockTransport），以及真实PG和独立worker的新旧维度、旧manifest、取消/失租约/中断恢复、激活SQL回滚。原维度反例改为检查SQLSTATE23514，与0008触发器一致。

付费tests/live/test_deepseek_tools.py不被标准入口收集。需要显式XIUTU_WP09_LIVE=1及已有共享预算账本/有效核价；真实MCP进程+BGE合成资料，由DeepSeek调用两工具再返回JSON。该路径仅选取.env模型字段，不加载其数据库配置。不要把live测试添加到普通CI，不新建第二份5元账本。耗时/费用/首次失败及最终轨迹分别留在WP09证据，不合并重复测试统计。
# WP-11 测试说明（2026-09-19）

历史 WP-11 交付说明：原 `tests/integration/test_wp11_graph.py` 在真实隔离 PostgreSQL 上覆盖诊断启动/发布、租约、回滚、取消及观察恢复；现保留为 `tests/integration/legacy_wp11_graph.py`，标准 `scripts/test.ps1` 不再收集，只有显式指定该文件才会收集。旧流程用例不能作为当前模板工作台回归成功条件。

`tests/live/test_wp11_dkvb.py`是**显式开关的单次付费探针**，只可在共享5元费用账本、官方现价、私有凭据和独立测试库核准后单独运行；不得放进标准入口或反复跑到模型生成预期答案。探针的测试临时目录可能含隔离MCP凭据，只存`.test-runs`，不可复制进公开证据。`scripts/demo_wp11.py`使用确定性合成测试夹具，不调用付费模型，也不等于WP-12观察API。

WP-12 的 `tests/integration/test_wp12_turns.py`、`test_wp12_area_closure.py`、`test_wp12_area_activation.py` 仍在标准 `scripts/test.ps1` 收集范围；其旧观察与区域写入预期尚待分类。旧 `scripts/demo_wp12.py` 只使用隔离合成夹具，不调用 DeepSeek，不能当作当前模板工作台或真实维修效果验收。
