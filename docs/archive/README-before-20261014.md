# 历史首页说明（2026-10-14 整理前）

当前使用说明见仓库根目录 README。下文保持阶段历史，不作为当前快速启动入口。

# 修途下一版

WP-00—12已按各自限定范围接受。WP-13进度/最终报告服务已实施，状态为IMPLEMENTED_NOT_ACCEPTED，待集中审核及用户决定；当前 `unknown` 区域卡只能生成如实列缺项的进度报告，最终报告由服务端门禁阻断。已有模型网关、可信Skills、Windows本地BGE-M3（1024维）及旧E5（384维）兼容。接受记录不代表正式报告已验收或真实维修效果；同任务历史流程限制保留。

实施契约：[WP-02契约](../../docs/implementation/phase-02/wp-02-contract.md)。结果与实际证据见[WP-02结果](../../docs/implementation/phase-02/wp-02-result.md)；状态见[STATUS](../../docs/implementation/STATUS.md)。WP-01历史报告与接受记录保留。

WP-13 报告请求、门禁和历史读取见[API说明](../../docs/api/wp-13-reports.md)与[本地运行说明](../../docs/runbooks/reports.md)。仅用户主动请求才建立报告任务；本包自测使用合成资料与免费 MockTransport，未调用付费报告模型，也未部署到 5180/5196。

## 环境与安装

Python3.12.10、Node24.14.0（.node-version与npm/bootstrap实际检查），uv锁定依赖，前端npm lock。项目根执行：

```powershell
Set-Location E:\Work\xiutu-v5
.\scripts\bootstrap.ps1
.\scripts\test.ps1 -OfflineOnly
npm.cmd --prefix frontend ci
npm.cmd --prefix frontend run typecheck
npm.cmd --prefix frontend run build
```

OfflineOnly包含unit/contract与真实本地MCP，不连接数据库，不调用模型；完整入口还包括integration和PG/vector/跨进程探针。脚本自行安全准备.test-runs父目录，每次生成新的UUID测试目录，不复用或清理历史basetemp；无需手动mkdir。同名普通文件、项目路径或临时父目录的junction/symlink会明确拒绝，不跟随重解析路径写入。

## 数据库与迁移

现有专用服务xiutu-v5/postgres只绑定127.0.0.1:5433；凭据位于被忽略的.local-data/wp01-postgres.json。不输出凭据，不读取旧.env，不改变旧8014服务。先只读检查docker version及容器标签/映射，确认归属；未知端口或资源冲突不得接管。

当前迁移head为0008_model_indexes：0005_indexes→0006_evidence_specs→0007_tools→0008_model_indexes。本包将向量按索引维度隔离并保留旧索引；0001—0007原样保留。WP-05迁移0005_indexes：在0004_documents的资料owner、版本元数据/解析状态、chunk定位/token及审核历史基础上，新增index_versions、chunk_embeddings、review_snapshot及带版本关系约束的active_index_id；0001—0004保留原样。**不要升级WP-01保留验证库**。本次只验证新测试库；开发库迁移由维护者后续明确执行。以下创建唯一新测试库：

```powershell
$localConfig = Get-Content -LiteralPath .local-data/wp01-postgres.json | ConvertFrom-Json
$env:DATABASE_URL = 'postgresql://xiutu:{0}@127.0.0.1:5433/xiutu_dev' -f $localConfig.password
$testName = 'xiutu_test_' + [guid]::NewGuid().ToString('N')
uv run --frozen python scripts/probes/prepare_database.py --name $testName
if ($LASTEXITCODE -ne 0) { throw 'New test database creation failed' }
$env:TEST_DATABASE_URL = 'postgresql://xiutu:{0}@127.0.0.1:5433/{1}' -f $localConfig.password, $testName
$env:DATABASE_URL = $env:TEST_DATABASE_URL
uv run --frozen alembic upgrade head
if ($LASTEXITCODE -ne 0) { throw 'Migration failed' }
.\scripts\test.ps1
```

测试库/合成测试记录保留供审核，不自动删除数据库。迁移集成测试会另建唯一xiutu_test_wp02mig_*库演练升降级；只清理自身sentinel schema。0002降级删除其八表，仅允许在全新隔离测试库演练。health预期0008_model_indexes：空库、旧版本、错误版本均503，匹配数据库+vector+版本才200。

共享目标门禁仍只接受显式localhost/127.0.0.1:5433及允许库名；query仅connect_timeout=1..5。拒绝hostaddr、service、多主机、目标覆盖及所有非空PG*环境项；验证后重建驱动参数。测试缺配置不得回退开发库。

## 本地认证和亲自验证

单进程本地操作员认证；不使用多worker。OPERATOR_TOKEN为32..512字符的受保护环境配置；OPERATOR_ID默认固定UUID，配置更改意味着另一个业务身份。不同登录cookie仍属同一操作员。缺token时health可用，业务认证失败关闭。

当前终端可创建仅用于此次本地验证的随机token（命令输出直接赋值，不打印）：

```powershell
$env:OPERATOR_TOKEN = (& .venv\Scripts\python.exe -c 'import secrets; print(secrets.token_urlsafe(32))')
$env:APP_ORIGIN = 'http://127.0.0.1:8020'
# DATABASE_URL使用上面已迁移的新测试库；先确认8020空闲，不停止未知进程。
uv run --frozen uvicorn app.main:app --host 127.0.0.1 --port 8020
```

令牌应由本地受保护配置管理；不要复制进Git、URL或日志。服务器和调用客户端使用同一令牌。查看 http://127.0.0.1:8020/openapi.json 或 /docs。客户端按如下顺序：

1. POST /api/v2/auth/login，Origin: http://127.0.0.1:8020，JSON {"token":"从受保护配置取得的令牌"}。保留响应Cookie和csrf_token，不打印凭据。
2. POST /api/v2/cases，携带Cookie、相同Origin、X-CSRF-Token及唯一Idempotency-Key。JSON示例：{"vehicle":{"model":"Synthetic","engine_code":"CODE","engine_family":"FAMILY"},"fault_description":"Synthetic local test","fault_codes":["P0001"]}。
3. 预期201、revision=0、draft、corpus_manifest=[]、active_run=null、report_gate.available=false。GET /api/v2/cases/{id}及/cases?limit=20可读取。相同key/规范化请求重放原响应；不同请求同key返回409。
4. POST /api/v2/auth/logout携带Cookie/Origin/CSRF，随后读取应401。登录过期、重启或轮换登录时旧会话失效。

Cookie为HttpOnly、SameSite=Strict，默认1小时；HTTPS配置时Secure，HTTP仅允许loopback。GET /auth/session可在已认证时获取CSRF；写请求包括登录都检查Origin，业务写入另检查会话绑定CSRF。默认无CORS跨源访问。登录响应不进入业务幂等缓存；幂等业务响应至少保留7天，本包无清理worker。

统一错误含error.code/message/retryable/trace_id，可选details，验证错误不回显输入秘密。非本人和不存在会话统一404。列表稳定游标分页，limit<=50；无修改/删除/诊断运行API。

## 范围和保留门槛

八张基础表保持；WP-04另增document_reviews历史表；WP-05新增index_versions/chunk_embeddings以及带版本关系FK的active_index_id，后台任务支持no_op、本地ingest和index。WP-02时的报告门禁尚未实现；现有 WP-13 门禁见本文件开头的接口说明。空资料快照仍不表示正式资料已授权。

E10在WP09已获共享5元授权并完成真实DeepSeek多工具/MCP/结构化输出自测，待本包集中审核；详见WP09结果，旧报告NOT_VERIFIED是历史状态，不回写。真实资料NOT_MET，来源/许可、车型/发动机、规格/线路/拆装/复核章节与缺图最迟WP10/真实效果验收前补齐。WP00—08限定接受，WP09实施待审核，WP10—17未开始；不承诺生产恢复或维修效果，同任务历史流程限制保留。

## WP-02 r1整改

历史说明：WP-02已完成r1/r2整改、r3定点复核并由用户限定接受；同任务审核限制已明确接受。见[整改记录](../../docs/implementation/phase-02/wp-02-remediation-r1.md)。原result与r1 review保留为历史。

会话自由文本中的实际NUL在事务前返回422 VALIDATION_ERROR，不替换用户字符；字面量\u0000、正常中文/Unicode及正文换行仍按原契约处理。确定性数据库数据/约束错误为安全的非重试500，未知内部错误500；明确连接不可用才按契约503 DATABASE_UNAVAILABLE，瞬态事务争用503 DATABASE_BUSY。不要据500反复重发不变的输入；幂等业务冲突仍409。具体分类边界见实施契约。

## WP-03 持久任务与演示

契约及状态图：[WP-03契约](../../docs/implementation/phase-02/wp-03-contract.md)。结果：[WP-03结果](../../docs/implementation/phase-02/wp-03-result.md)。API文档：[任务接口](../../docs/api/wp-03-runs.md)，实际OpenAPI为运行服务的/openapi.json。

完成上方新测试库创建与`alembic upgrade head`、令DATABASE_URL指向该库后，一条命令演示：

```powershell
uv run --frozen python -B scripts/demo_tasks.py
```

脚本使用新owner提交no_op测试任务，启动自己随机loopback端口的API与指定任务worker，经真实HTTP查看状态/SSE并取消，最终显示cancelled。只结束它创建的进程；合成任务与事件保留供查看，进程日志保存在系统临时目录xiutu-wp03-demo-*。它不是导入或汽车诊断；不读取旧.env、不打印凭据，不自动迁移既有数据库。

常规本地操作员提交：`uv run --frozen python scripts/submit_no_op.py --seconds 20`（沿用受保护DATABASE_URL与OPERATOR_ID；可指定--case-id和--expected-revision）。启动worker：`uv run --frozen python -m app.worker`；仅执行一次使用`--once`。API仍单进程内存认证，不启用多API worker；后台任务worker可以多个进程。

默认租约60秒/独立心跳15秒。仅租约到期不能越过旧advisory lock；进程断开后锁释放，新worker按累计预算恢复。自动最多3次总尝试，2/8秒加抖动等待，30秒档不使用；显式retry不重置预算。达到上限需维护者排查，不能无限创建重试链。只保证本包数据库内任务/事件原子性，不承诺外部调用exactly-once。

GET case/list中的active_run现为真实活跃摘要或null；创建幂等响应保持原快照。GET run/SSE及cancel/retry接口见契约；没有start/reassess诊断入队API。运行中取消先cancel_requested，worker下一心跳或完成边界确认，转cancelled；失进程后由取得锁的回收者确认。事件初版不清理。

## WP-04 上传、解析、人审与版本

契约：[WP-04契约](../../docs/implementation/phase-02/wp-04-contract.md)；接口：[资料API](../../docs/api/wp-04-documents.md)；交付：[结果与证据](../../docs/implementation/phase-02/wp-04-result.md)。API和worker必须使用同一个本项目DATA_PATH（不得指向旧项目/重解析路径），且数据库已升级当前head（当前为0006_evidence_specs）。

沿上文静默加载凭据、新建唯一测试库并迁移后，一条命令演示：

```powershell
uv run --frozen python -B scripts/demo_documents.py
```

脚本仅接受xiutu_test_*库；新建owner与临时存储，启动随机loopback端口的API和只处理演示任务的worker。上传明确synthetic的Markdown、两页文本PDF和扫描PDF，实时打印SSE、原文/切块定位，询问是否记录一次**合成资料演示人审**。WP-05当前默认formal profile下，输入yes后合成资料显示approved、blocked（synthetic）、index_implemented=true、formal_usable=false；扫描件为needs_ocr。当前索引演示请使用下方demo_retrieval。它不代替真实材料专业审核。自动化演示可加`--demo-approve-synthetic`，含义仅是记录合成测试操作；本次自测采用该选项。仅结束自己创建的进程，保留合成记录和文件，输出临时目录供查看。

真实使用时POST /api/v2/documents的multipart包含file和metadata（UTF-8 JSON）；已有资料在metadata传document_id新增版本。默认文件上限25MiB，实际接收时限额；只支持UTF-8 Markdown和未加密PDF。不信浏览器MIME、不访问外部链接。使用UUID原文key与SHA256；同文档同hash+metadata复用，元数据不同409；不同内容创建新版本。旧版原文/定位保持可读。

默认600/900/80为cl100k_base BPE token目标/硬上限/重叠；词表随项目封存，运行时不下载，不代表任何模型计费。可设置UPLOAD_MAX_BYTES、CHUNK_TARGET_TOKENS、CHUNK_MAX_TOKENS、CHUNK_OVERLAP_TOKENS；须满足0<=overlap<target<=max<=900。解析/人审不等于索引或维修资格。纯扫描/含图页会记录逐页缺项；复杂PDF布局未校验，尚无OCR。损坏/加密PDF拒绝，PDF最多1000页及1000万抽取字符，超限明确失败。

原文与数据库不是跨介质原子存储：独占写入/fsync后再创建数据库引用，回滚/并发输家只清理本次无引用文件；数据库提交不明确或硬中断可留下孤儿。不要按时间盲删storage文件；先由维护者在停写条件下对照document_versions.storage_key及SHA256，只读核对后另行授权清理。存储目录应仅允许运行用户写入；本包不提供抵御本机特权用户并发改写目录的沙箱，也不承诺生产灾备。


## WP-05 本地真实向量、索引与检索

现可对已审核且满足服务器资料资格的MD/PDF切块建立真实向量索引，通过故障码关键词+中文TF-IDF+精确cosine混合检索返回chunk与原文locator。没有Agent、诊断生成、OCR或正式前端；返回chunk_id，绑定到case后由WP-06另行返回evidence_id。见[契约](../../docs/implementation/phase-02/wp-05-contract.md)、[API](../../docs/api/wp-05-retrieval.md)、[模型ADR](../../docs/adr/0002-local-embedding.md)、[结果](../../docs/implementation/phase-02/wp-05-result.md)。

在本项目根安装并下载公开免费模型（约470MB；不会上传资料）：

```powershell
uv sync --frozen
uv run --frozen python -B scripts/fetch_embedding.py
```

E5-small固定revision、FP32 ONNX、CPU、384维，权重与tokenizer哈希不符则拒绝。默认路径`.local-data/models/multilingual-e5-small/614241f622f53c4eeff9890bdc4f31cfecc418b3`；EMBEDDING_PATH可指向同一固定文件副本，API和worker须一致。运行时完全本地、不自动下载；缺文件时503/任务失败，不悄悄回退。可用GPU尚未纳入本包验证。

沿前文静默加载本项目数据库凭据，创建**新且唯一xiutu_test_***库，设DATABASE_URL并`uv run --frozen alembic upgrade head`。然后一条命令：

```powershell
uv run --frozen python -B scripts/demo_retrieval.py --output .test-runs/wp05-demo-unique.json
```

输出路径必须未占用。脚本校验测试库、显式synthetic服务器profile，新建owner/存储，启动自己随机端口API和指定run worker，完成上传→解析/SSE→合成演示审核→真实索引/SSE→检索→原文哈希/locator核对。只停自己创建的进程，不删库/卷或原文；JSON和临时日志可查看。脚本自动记录的是**合成演示审核**，不代表用户对真实维修资料的专业审核。

复现已冻结24段/12查询合成留出比较：同一命令加`--evaluate`，使用新的输出名。baseline/hybrid共享语料、标签和配置哈希；标签为实施者编写，未有人类维修真值。首次Recall@5为0.8472/0.9306；不能写成真实维修召回达标。

正常服务仍默认formal profile：批准、无解析缺页、非synthetic、来源verified及许可private_use/permitted才会入队索引。审核必须如实，不因文件本地存在而虚报来源。approved不自动等于ready；重建API见API文档。同version一个building，不覆盖旧active；取消/失租约/失败保留旧可用索引；撤销资料立即从下一次搜索快照排除。building失败暂存向量保留用于审计，不自动清理。

synthetic模式仅服务端RETRIEVAL_PROFILE=synthetic、APP_MODE=test且通过测试库门禁可启用；公开搜索参数不能打开它。未知精确适配只通用参考，明确冲突排除，engine_family不等同具体engine_code。正式语料不足时搜索为空是预期结果。

回归入口仍`scripts/test.ps1`（必须TEST_DATABASE_URL），新增integration真实模型文件是前置，不缺配置静默skip；OfflineOnly只运行无数据库/无模型推理部分。本轮不重跑前端或第二venv。SSE首次超时根因未确认，既有非阻断待办、E10/WP09和资料/WP10门槛继续保留。


## WP-06 证据快照与测量规格（待审核）

当前迁移head为`0006_evidence_specs`，新增case_evidence、measurement_specs、measurement_spec_reviews、measurement_comparisons及资料authorization_epoch；旧0001—0005不改。新case自动冻结当前owner/profile/资格/适配允许的ready版本索引；旧空manifest不扩范围。撤销或资格/范围改变会标记复核，重新批准不会静默恢复旧依据。

见[契约](../../docs/implementation/phase-02/wp-06-contract.md)、[API](../../docs/api/wp-06-evidence-measurements.md)、[执行结果](../../docs/implementation/phase-02/wp-06-result.md)。规格先pending，人审批准且适配matched后比较；Decimal字符串输入输出和受控单位，支持温度偏移及开闭/单边界。within_range只表示输入值符合该规格条件，不是部件正常或维修结论。旧比较与引用可读，但必须同时查看current_validity/needs_review。

沿上方创建唯一`xiutu_test_*`并升级head，复用WP-05本地模型。在项目根执行：

```powershell
uv run --frozen python -B scripts/demo_measurement.py
```

该CLI使用已安装开发测试工具，实际启动自己的HTTP/worker，使用新owner和隔离存储。完整演示上传→解析/审核/真实索引→新会话冻结→检索/绑定/原文→规格创建/审核→范围内/超限/缺工况→撤销后阻断且历史可读；输出新`.test-runs/wp06-demo-*`的JSON与JUnit。样例1..2 V、engine=off均为**合成测试值，不能用于维修**。不会自动取得真实资料专业批准。未实现诊断图、正式报告生成或新页面。

固定384维本地配置与性能/清理/监控待办、SSE首次根因未确认、E10最迟WP-09和真实资料最迟WP-10门槛继续保留。WP-06已按[接受记录](../../docs/implementation/phase-02/wp-06-acceptance.md)限定接受；该节保留其技术边界。


## WP-07 五工具与执行器

见[工具接口和演示](../../docs/api/wp-07-tools.md)、[严格schema及哈希](../../docs/api/wp-07-schemas.json)、[契约](../../docs/implementation/phase-03/wp-07-contract.md)。新库升级head后：`uv run --frozen python -B scripts/demo_tools.py`。演示无LLM，合成资料/规格不是维修标准；正式观察无记录返回空。使用固定本地E5，不重做模型选型。

五工具复用会话冻结资料、当前资格及规格服务；scope只能收窄。应用可信入口注入身份/allowlist/预算，模型不能决定。成功receipt与比较同事务，重放不重复比较，撤销/身份失效后重放仍拒绝；超时、取消及预算不足明确区分。进程不明调用不自动重做；只读模型推理不保证硬实时抢占，但超时后不发布成功。WP-08当前提供三项只读MCP；WP-09—17未启动，E10/真实资料/SSE既有门槛保留。

## WP-08 真实业务 MCP

默认ToolExecutor三只读工具使用`remote_mcp`模式；必须设置受保护`MCP_CLIENT_CONFIG`，缺配置明确失败，无本地fallback。原本地演示/测试明确`tool_mode=local`。compare/observations继续在应用侧；预算、调用记录和receipt不放到只读服务。

[运行手册](../../docs/runbooks/mcp.md)含角色/独立凭据生成、Host/Origin策略、真实Compose及独立CLI命令；[工具协议](../../docs/api/wp-08-mcp.md)及[契约](../../docs/implementation/phase-03/wp-08-contract.md)说明绑定范围、输出复核与故障边界。沿用0007_tools，无新迁移。Compose默认不发布端口，debug仅loopback，原文/模型/配置只读。合成三工具端到端演示可直接执行运行手册的pytest入口，不依赖LLM，也不等于正式UI。

标准完整入口新增真实业务MCP集成用例，需要本地E5和隔离PostgreSQL；OfflineOnly仍只运行不依赖数据库的契约及基础协议测试，不能替代三业务工具证明。WP08实际统计与失败日志见[交付结果](../../docs/implementation/phase-03/wp-08-result.md)，状态等待审核/接受，不自动进入WP09。


## WP-09 模型与Skills

配置优先级、真实调用门禁、共享5元账本、BGE/E5兼容及可复制隔离演示见[模型运行说明](../../docs/runbooks/models.md)。标准完整入口不收集付费live测试；`.env`存在不代表已经联网或E10通过。实际首次失败、后续成功与费用见[WP09结果](../../docs/implementation/phase-04/wp-09-result.md)。本地BGE只使用dense能力，不宣称重新完成真实维修检索质量评测。

## WP-10 合成提案与免费技术演示

[实施契约](../../docs/implementation/phase-04/wp-10-contract.md)、[接口/演示](../../docs/api/wp-10-proposals.md)、[结果与原始证据](../../docs/implementation/phase-04/wp-10-result.md)。模型候选不是已发布业务状态；不新增公开HTTP提案API或数据库迁移。未知、未检查、资料不足不等于暂时排除。

使用本页隔离测试库准备步骤设置TEST_DATABASE_URL后：

```powershell
$env:PYTHONPATH = "$PWD/backend"
uv run --frozen python -B scripts/demo_proposals.py
```

仅导入用户授权的虚构冷却文档副本，经过真实HTTP/数据库/既有worker，再展示资料、候选与拒绝/待补理由；本地E5仅用于演示资料索引，无付费模型请求。附加1—2 V台架规格单独标为新增合成fixture，不是用户原文，不是维修标准。输出位于新的.test-runs/wp10-demo-*目录。

真实资料仍NOT_MET：原WP10/真实效果验收前的来源、许可、精确适配及正式章节要求尚未满足，本包不把期限顺延或视为通过。以上WP-10演示仅为合成技术能力，当时尚未包含WP-11图；WP-12现已有隔离合成范围的观察写入，但尚未审核、接受或提供正式报告。E10沿用WP09限定deepseek-flash证据；Linux BGE、历史SSE/Compose根因及既有非阻断待办保留。

## WP-11 持久诊断图（限定范围已接受）

以下为当时的阶段交付记录。当前模板工作台不走这条诊断执行链；两份纯旧执行测试已改为 `tests/integration/legacy_wp11_*.py`，默认回归不收集。`scripts/demo_wp11.py` 仅保留为显式历史合成夹具入口。

[WP-11契约](../../docs/implementation/phase-04/wp-11-contract.md)、[基础接口](../../docs/api/wp-11-diagnosis.md)、[隔离运行说明](../../docs/runbooks/diagnosis.md)和[交付证据](../../docs/implementation/phase-04/wp-11-result.md)记录本包范围。新增`0009_graph`：单步检查、区域与发布记录以数据库为权威；LangGraph检查点独立放在`wp01_wp11`，升级迁移后需显式运行`python -B scripts/setup_graph_checkpoint.py`。worker沿用原run/job租约、物理advisory锁、心跳与取消保护。业务发布与revision/run事件在同一事务，等待输入后释放worker；恢复只接受已保存观察的UUID。`python -B scripts/demo_wp11.py`是**免费合成fixture**验证，不代表DeepSeek生成。

WP-12新增的观察写入/更正接口见[契约](../../docs/implementation/phase-04/wp-12-contract.md)及[API说明](../../docs/api/wp-12-observations.md)。当前没有正式观察前端或最终报告。确定性合成夹具不代表DeepSeek产生有效维修建议，技术性`waiting_input`也不是诊断结论。本包不部署5180/5196，不修改其资料、会话和索引。

## WP-14 正式前端（限定范围已接受）

正式入口为 `/workbench`、`/documents`和 `/history`。它们使用生成的 OpenAPI 类型、cookie/CSRF 会话和 TanStack Query，连接真实病例与资料 API。运行方法见[前端运行说明](../../docs/runbooks/frontend.md)，接口绑定见[WP-14 API 说明](../../docs/api/wp-14-frontend.md)，证据见[实施结果](../../docs/implementation/phase-05/wp-14-result.md)。

WP-14 的接受范围与限制见 `docs/implementation/phase-05/wp-14-acceptance.md`。

## WP-15 正式诊断工作台（已实施，待审核）

正式 `/workbench/:caseId` 已连接真实 snapshot、区域、当前检查、引用、四类观察、SSE 恢复、保守区域卡、观察更正及报告门禁。接口绑定见 `docs/api/wp-15-frontend.md`，隔离运行见 `docs/runbooks/frontend-diagnosis.md`，实际证据见 `docs/implementation/phase-05/wp-15-result.md`。

真实验证仅使用 `synthetic=true`、`formal_usable=false` 的台架资料：首项检查发布、浏览器观察保存及续轮 `unknown` 卡读回成功；续轮没有发布第二项当前检查。真实资料仍 `NOT_MET`，本包未部署 5180/5196，也不代表真实维修效果或最终报告就绪。
