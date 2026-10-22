# 变更记录

## 2026-10-22 — 区域资料入库流程（第 1 期，后端）

- 迁移 `0024_reference_ingest`：`area_reference_documents` 增加处理状态、来源、小块数、向量模型标识、必带章节、待绑定区域；新表 `area_reference_chunks`（按 `###` 小节切块，编号数组带 GIN 索引，导航章节存但不参与检索）和 `area_reference_chunk_vectors`（pgvector，按模型标识区分）。
- 新接口 `POST/GET /api/v2/area-references`、`GET /api/v2/area-references/{id}/versions/{v}/chunks`：上传 Markdown → 后台任务 `reference_ingest` 切块、提取编号、用本地向量模型计算向量 → 全部成功后才把所选区域切到新版本；同内容重复上传返回原版本，失败的版本可重新上传重试。
- `install_area_references.py` 升级到当前数据库版本，导入清单资料后用同一套处理代码切块、计算向量（`--no-vectors` 只切块）；必带章节从 `reading_documents_v1.json` 写入资料行。
- AI 分析的读取方式不变（第 2 期改为读库里的小块和向量）。

## 2026-10-22 — 保守清理（不改变行为）

- 删除 16 个开发阶段一次性脚本（C 系列重放/审计、WP-00 基线与备份、R1 播种等）和 2 个没有任何引用的后端模块（`report_service.py`、`publish_workbench_b01_topic.py`）。
- `docs/implementation/` 开发证据移出仓库目录（git 历史保留，见 `docs/archive/implementation-evidence.md`）；写入该目录的旧预览工具改写到 `.local-data/evidence/`。
- 前端改名：`FormalWorkbenchB01Page` → `TemplateWorkbenchPage`（当前模板工作台），`FormalWorkbenchV2Page` → `LegacyDemoWorkbenchPage`（旧演示台架只读页）。
- 旧流程（B01/B02 演示专题、C 系列分析、早期诊断流程）及资料中心、MCP 保持不变，旧病例仍可查看。

## 2026-09-21 — WP-15 完整诊断工作台（已实施，待审核）

- 正式工作台接入病例快照、区域/当前检查/证据、四类观察、任务 SSE、保守区域卡、观察更正及报告门禁；服务端事实由查询缓存持有，迟到事件受病例/epoch 上下文保护。
- OpenAPI 增加既有诊断与报告响应声明，观察历史返回原步骤输入 schema/工况；没有复制业务门禁或新增平行诊断后端。
- 免费确定性 E2E 和响应式浏览器路径通过；一次真实合成链路发布首项检查、浏览器保存观察，真实续轮保守收尾为 `unknown`，没有第二项当前检查。未部署 5180/5196，等待集中审核。

## 2026-09-21 — WP-14 正式前端与资料中心（已实施，待审核）

- 在现有 React/Vite 工程增加 workbench/documents/history 可恢复路由，保留已接受预览入口。
- 从服务端 OpenAPI 生成前端类型，增加差异检查、统一 API client、TanStack Query 状态和响应式视觉基础。
- 资料中心真实连接上传、解析、人工审核、索引、原件/切块和试搜；保留 synthetic、needs_ocr、formal_usable 和适配缺项。
- 本包不包含 WP-15 诊断/SSE/观察/报告联调，未调用付费模型，未部署或操作 5180/5196。

## 2026-09-21 — WP-13 报告服务（已实施，待审核）

- 新增 `0012_reports`、用户主动请求的进度/最终报告 API、六项最终门禁、冻结 revision/资料/结论、独立报告任务与事务发布。`unknown` 病例的进度报告列缺项；最终报告未满足条件返回 409，不能借页面提示绕过。历史报告可读且实时标识失效。
- 最终报告的结构化事实和动作须对应当前可信结论卡，来源与规格重验、动作去重和依赖循环检查在发布前执行。自测使用隔离合成资料和免费 MockTransport；尚无真实资料或付费报告模型验证，不代表真实维修效果。

## 2026-09-18 — WP-00（待验收）

建立独立 Git、范围 ADR、旧版测试与哈希基线、SQLite 一致备份/独立恢复脚本和证据、来源与缺章清单。没有迁移业务代码，没有新增运行中的产品能力。

## 2026-09-18 — WP-00 接受与 WP-01 部分实施

- 核对 32 文件及审核报告/暂存区哈希后记录用户接受 WP-00；历史审核不改写，资料风险未解决。
- 新增 Python/前端锁文件、最小 health 服务、环境迁移、独立探针及运行脚本。第二虚拟环境复现成功；前端 typecheck/build 通过；真实 MCP 与模型离线契约通过。
- Docker Desktop 自身初始化失败；完整数据库探针 3 errors，WP-01 为 BLOCKED。PG/vector、ready=200、图跨进程恢复未验证，E10 无付费授权。
- 实际命令、失败保留及版本记录见 wp-01-result.md 和 evidence/wp-01。未修改旧项目、暂存区，未提交/推送，未开始 WP-02。

## 2026-09-18 — WP-01 r1整改与真实补测

- 统一迁移、连接池、fixture、图进程、建库的有效目标校验，拒绝query/hostaddr/PG环境/service等绕过；35个无连接门禁用例通过。
- 修复HTTP启动等待，验证延迟、超时、提前退出和端口占用；声明Node24.14.0并接入npm与bootstrap实际前置检查。
- 澄清初始53项/当前63项旧项目保护范围。Docker由用户修复后，本轮新建专用服务和两个唯一测试库；迁移、pgvector、schema清理、跨进程恢复与真HTTP就绪通过。
- 两个隔离Python环境完整测试各66 passed/1 warning；前端锁复现、类型检查和构建通过；镜像digest已固定。WP-01=IMPLEMENTED_NOT_ACCEPTED，等待r2复核。
- 原result/review/接受记录/证据保留，E10及资料门槛未满足，未进入WP-02；详见wp-01-remediation-r1.md。

## 2026-09-18 — WP-02 数据库、领域与会话 API（待审核）

- 保留0001_environment，新增0002_core八表及可验证降级；健康版本统一为0002_core，旧/缺/错误迁移仍未就绪。active_index_id延至WP-05，不建无约束伪引用。
- 本地操作员登录、会话Cookie、同源/CSRF、退出和统一脱敏错误；稳定owner来自认证上下文。会话仅create/get/list，空资料快照，报告门禁明确未实现。
- PostgreSQL事务内幂等写入与原响应重放、owner隔离、签名游标、revision服务检查；并发幂等、活跃run部分唯一、jobs.run_id唯一及回滚均真实验证。
- 默认入口纳入unit/integration；最终新venv默认102 passed、离线85 passed，各1条已知弃用警告；真实HTTP、OpenAPI、前端独立构建证据见WP-02结果。早期测试及lint失败记录保留。
- WP-02=IMPLEMENTED_NOT_ACCEPTED；没有任务执行/worker/SSE、资料上传检索、Agent、报告或新业务页面。E10与资料门槛保留；未开始WP-03，未修改旧项目、历史接受/审核或暂存区。

## 2026-09-18T10:50:59.942222+08:00 — WP-02 r1整改

仅ISSUE-001/002：测试父目录安全准备；自由文本NUL事务前拒绝；按SQLSTATE/明确异常类型区分数据库故障、争用、确定性错误和未知错误。增加21项单测及独立真实HTTP/数据库验证。详情见docs/implementation/phase-02/wp-02-remediation-r1.md；保持IMPLEMENTED_NOT_ACCEPTED，等待r2，不进入WP-03。

## 2026-09-18T12:30:18.640047+08:00 — WP-03 持久任务、租约、事件与取消（待审核）

- 前置WP-02已由用户限定接受，核对其接受后基准；保留历史迁移与所有审核/接受记录。
- 新增0003_jobs任务owner与索引，health预期同步；实现原子入队、SKIP LOCKED领取、稳定advisory会话锁、独立心跳、fencing及恢复，最多三次累计尝试。
- 新增GET run、持久SSE、幂等cancel/retry及真实active_run摘要；只注册no_op测试处理，ingest/未知处理器明确失败，无诊断start/reassess接口。
- 实际完整入口146 passed/1既有警告，追加断锁反例1 passed；真实独立进程、HTTP/SSE、取消演示通过。详见[WP-03结果](docs/implementation/phase-02/wp-03-result.md)。未重建双venv或前端，未付费调用。
- WP-03=IMPLEMENTED_NOT_ACCEPTED；等待一次审核与用户接受，WP-04—17未开始。

## 2026-09-18T13:26:26.514368+08:00 — WP-04 资料上传、解析、人审与版本（待审核）

- 新增0004_documents及资料owner/不可变metadata/当前run/审核历史；流式multipart资源限额、UUID原文和SHA256、所有权/安全/幂等接口、版本复用和原文/切块定位。
- 接入真实ingest处理器；解析在事务外，有效lease/token且未取消时原子发布全部chunk/版本/成功事件；失败、取消、回收耗尽、显式重试同步资料状态。
- 本地Markdown/PDF解析、cl100k_base真实token切块；扫描/混合缺项needs_ocr，人工approved仅index_pending，不生成索引任务。新增合成HTTP/SSE演示与真实PG/独立进程测试。
- 完整入口首次收集同名模块失败已修正；实跑168 passed/1 SSE读取超时，原失败单项及随后SSE两项定点均通过，根因未确认，不称全量零失败。资料门禁补强两项通过；详见[结果](docs/implementation/phase-02/wp-04-result.md)。原始失败证据保留。
- WP-04=IMPLEMENTED_NOT_ACCEPTED，待一次审核；WP-05—17未开始。未改旧项目、0001—0003、历史/接受记录或Git index；无付费调用，E10与真实资料缺项保留。


## 2026-09-18T15:32:07.887149+08:00 — WP-05（待集中审核）

- 新增0005索引迁移、固定本地E5-small FP32 ONNX/384维及哈希校验、index任务分批暂存/租约最终校验/原子active切换；既有迁移与接受记录未改。
- approved资格合格自动调度、显式reindex、版本构建状态与错误可见；默认formal排除synthetic和来源许可缺项；独立测试profile严格限test库。
- 新增受认证/CSRF保护的evidence/search，适配先过滤、TF-IDF完整DTC、精确cosine、RRF60及确定性排序；返回chunk/locator，未实现WP06快照。
- 冻结合成24段/12查询：Recall@5 .8472→.9306；真实worker/PG故障恢复定点通过。一次完整192通过/1警告，最后小幅状态/ORM收尾4项通过，未重新全量；详见wp-05-result.md。
- WP-05=IMPLEMENTED_NOT_ACCEPTED；E10/真实资料/SSE既有缺项保留，无付费调用或WP06。全目录lint的未变WP00脚本风格问题作为非本包发现保留，不顺带修复。


## 2026-09-18 — WP-06（待审核）

- 新会话由服务端冻结版本/ready索引/授权代次；旧manifest不扩范围，会话检索保持固定索引。
- 新增0006迁移、不可变证据及规格版本、审核历史与比较记录；资料资格变更同步标记复核，owner级事务锁串行化撤销与使用。
- 新增精确十进制/单位/工况比较，真实HTTP演示和数据库竞争测试；引用门禁为可调用服务，无报告发布流程。
- 仅WP-06，未改旧迁移或接受记录。证据与结果见wp-06-result.md；E10/真实资料/SSE及既有待办保留。


## 2026-09-18T17:50:41.831430+08:00 — WP-07 五业务工具与执行器（待审核）

- 复用冻结资料/规格/精确比较服务，真实LangChain适配和严格schema；可信上下文隔离身份、资料范围及预算。
- 0007工具预算/审计与观察只读；调用幂等、原子扣额、受限重试、不明结果不盲重做；比较/receipt同事务，超时/取消/迟到回滚。
- 当前标准完整入口一次260通过/1既有警告，CLI演示1通过；真E5/PG/HTTP/worker与可控错误注入分列。早期失败修正和证据保留。
- IMPLEMENTED_NOT_ACCEPTED等待审核；无业务MCP/Agent/观察写入/前端。旧迁移/项目/历史/index不变，E10/资料/SSE待办保留。

## 2026-09-18 — WP-08 真实业务MCP（待审核/接受）

- 新增SDK1.30.0 Streamable HTTP服务，只暴露三个只读资料工具；受保护独立凭据绑定case/revision/冻结资料，精确Host/Origin与当前资格复查。
- 应用执行器默认remote_mcp，实际SDK HTTP适配与独立CLI；预算/审计/receipt留应用事务，失败不本地fallback，最多一次明确瞬态重试。显式local模式保留本地测试。
- 新增只读role/配置生成脚本、固定digest镜像及Compose只读原文/模型挂载。复用现有owner锁/领域服务，0001—0007和db_target不变，无新迁移。
- 最终完整301 passed/1既有warning；三工具双客户端、实际Compose/写入拒绝、冻结索引、断连/取消/超时及来源复核证据保留。初次测试方法名、Compose验证脚本语法及完整收集重名错误均保留并定点修正；不转写为审核结论。
- WP-08=IMPLEMENTED_NOT_ACCEPTED，见wp-08-result.md；未推进WP09、付费调用或修改历史验收记录。E10/真实资料/SSE及既有待办保留。


## 2026-09-19 — WP-09（待审核）

新增显式LLM/Embedding工厂、DeepSeek原生工具/JSON与共享费用门禁、可信Skills；按用户授权接入本机BGE-M3 1024，0008多维索引保留旧E5/冻结会话。真实工具/MCP/JSON链路通过，完整328通过/1警告，首次截断及定点失败保留。4次真实请求usage峰时估算¥0.024582，保守预留¥0.198184，共享上限5元不重置。E10自测完成待审核，真实资料NOT_MET。未实施WP10，无前端/第二环境/模型质量重评；新增Linux BGE配置未动态验证。详见wp-09-result.md。

## 2026-09-19 — WP-10 合成提案与证据校验（待集中审核）

- 新增五类型候选schema、可信应用上下文、证据/版本/适配/规格硬门禁、保守支持判定、反重复与有依据复测、最多一次修复；不新增迁移、正式图、观察写入、报告或前端。
- 用户指定虚构源按字节复制并标注来源/hash/synthetic；独立数值夹具明确是新增虚构数据。原项目未改，formal/synthetic门禁未放宽，真实资料截止要求仍未满足。
- 首次夹具单位错配、测试收集/启动错误及收尾引用截断反例均保留。一次完整364通过/1警告后，针对上下文风险修正并定点35通过；不能称为最终实现重新全量通过。实际CLI与详细命令见wp-10-result.md。
- 无真实付费调用、不读真实费用账本、不重置授权；WP11未启动，历史限制保留。

## 2026-09-19 — WP-11 持久诊断图（待审核）

- 接续0008新增0009诊断区域/步骤/候选/发布/progress表；LangGraph PostgresSaver使用独立schema及显式setup，不改旧迁移。
- 在原worker的物理advisory锁、租约与取消门禁下运行单步图；可信上下文与既有工具/模型/提案服务衔接，事务发布case revision、当前步骤、run等待与事件。发布后检查点中断以数据库publication恢复。
- 新增诊断启动、只读当前检查及已保存观察引用恢复API；不包含WP-12正式观察写入、报告或前端。确定性夹具、真实模型和费用证据分别见[结果](docs/implementation/phase-04/wp-11-result.md)，不得混作真实维修效果。
## 2026-09-20 — WP-12 观察事务与事实修订（已实施，待审核）

- 新增当前检查的观察提交、不可用原因、更正与区域只读/激活/保守结论 API；数据库迁移接续 `0010_observation_turns`。提交原子写观察、步骤状态、下一 run/job、事件及幂等响应，更正追加历史并提升 graph epoch。
- 公开的旧 UUID 直接恢复入口改为拒绝；内部 WP-11 恢复仍从已保存事实读取。合成资料与确定性夹具验证和真实模型能力分别记录，不代表真实维修诊断或 WP-13 报告。
