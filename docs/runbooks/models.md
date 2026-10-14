# WP-09 模型配置、预算与验证

范围：模型网关/Skills与本地向量 factory。不是 Agent 图、诊断提案校验器或生产恢复承诺。用户额外授权本包加入 BGE-M3，不回写 WP05 的 E5 接受范围。

## 配置及启动

`Settings()`不读项目.env；API显式设置 `XIUTU_LOAD_PROJECT_ENV=1` 后调用 `load_settings(project_env=True)`。优先级：构造参数 > 进程环境 > 固定项目.env > 默认值。APP_MODE=test 或 TEST_DATABASE_URL存在时，禁止加载项目.env；测试凭据只从隔离启动器传入。不会自动调用付费模型。

私有.env不复制、不打印、不纳入交付清单。当前私有.env旧deepseek-chat不修改；本轮真实验证显式选择用户批准的deepseek-flash。新应用接口不接收provider、路径、密钥或可信工具上下文。

- `LLM_PROVIDER=deepseek`、`DEEPSEEK_MODEL=deepseek-flash`、`DEEPSEEK_BASE_URL=https://api.deepseek.com`、`DEEPSEEK_API_KEY`。旧 `LLM_BUDGET_CNY=5` 已废止，不再决定账本策略；普通请求不能指定策略。
- `EMBEDDING_PROVIDER=local_bge_m3`、`EMBEDDING_MODEL=BAAI/bge-m3`、`EMBEDDING_REVISION=5617a9f61b028005a4858fdac845db406aefb181`、`EMBEDDING_DIMENSION=1024`。
- `EMBEDDING_MODEL_PATH=E:/AI_Cache/huggingface/models--BAAI--bge-m3/snapshots/5617a9f61b028005a4858fdac845db406aefb181`。只离线读取已有文件，启动验证模型/外置权重/tokenizer哈希。
- `EMBEDDING_PATH`继续表示旧E5 ONNX目录（保留默认路径即可），不能用BGE路径覆盖它，否则旧冻结索引无法查询。
- worker/index_builder使用相同显式加载方式；测试worker通过进程环境获得BGE路径。MCP独立授权配置生成器可传`--bge-path`，不读取用户.env或放宽授权。

Embedding factory输出embed_documents/embed_query/config，LLM factory输出generate_structured/invoke_with_tools/health_config及受控run_tools。缺路径、未知指纹/维度、未知provider安全失败；不会自动下载、付费fallback或本地MCP fallback。

## 索引兼容

新增0008_model_indexes，head/ready预期0008。保留旧迁移。vector列支持按行384/1024维，SQL触发器将维度错误作为CHECK违反（23514）；数量、有限值、配置及来源仍由发布门禁核验。降级时有非384索引明确拒绝，不能自动丢弃新数据。

索引任务入队冻结配置。POST documents/{id}/versions/{vid}/reindex的config_version可省略（服务器选择默认）或必须匹配当前服务器默认；接受e5-small-onnx-v1与bge-m3-onnx-v1实际字符串以OpenAPI为准，不允许任意provider参数。approved调度采用同一factory。查询按每个固定index配置分组分别编码/计算cosine，不做跨维度距离；trace.model现在是实际配置列表。会话manifest及旧原文不被重建改写。

只升级本轮新隔离库，未对开发库/业务资料执行批量重建。模型内存缓存每进程独立；只用BGE dense，不实现M3 sparse/ColBERT。Linux BGE额外挂载示例deploy/compose.mcp-bge.yaml；本包已实测Windows独立MCP进程+BGE，未重新构建/动态验证新增Linux BGE覆盖配置，不能沿用WP08 E5容器证据宣称已通过。

## DeepSeek调用及预算

真实模式必须由可信代码传paid=True，默认拒绝联网；测试只允许MockTransport+隔离账本。真实账本仍固定在`.local-data/wp09-budget.json`，**不得重置、删除调用或另建额度账本**。用户于2026-09-20明确取消旧人民币5元累计拒绝上限；原授权与5元值以v2账本的`authorization`、`historical_limit_cny`保存，新策略`metered_no_cumulative_cap`持续计量、不因累计值拒绝。预算初始化不是运行自动操作。旧v1账本须显式运行`PYTHONPATH=backend .venv/Scripts/python -B scripts/migrate_model_budget.py --apply`（PowerShell应先设置`$env:PYTHONPATH`）；迁移在原文件锁内先于同一私有目录写入字节一致的`wp09-budget.json.v1-backup-*.json`，再原子替换原账本。命令只输出版本、聚合预留、条数和哈希；再次运行不重复迁移。若必须回退，应先停止本轮付费调用，核对备份哈希，在受控维护窗口恢复原文件并回退相应代码；v2代码对未迁移的v1账本安全拒绝。每次调用仍先跨进程加锁、原子持久预留，崩溃/失败/unknown usage都不退预留。仅记录参数hash、调用ID、usage、耗时、模型和错误码，不记录提示词、密钥或隐藏推理。

本轮采用官方峰时/未命中缓存上限：输入2元/百万token，输出8元/百万token；输入按UTF8字节×4+4096保守界，WP-09普通网关默认max_tokens=768，单payload<=100000字节。WP-11诊断服务可由受信服务端配置`DIAGNOSIS_MAX_OUTPUT_TOKENS`在768—1536间选择，默认1536；SDK请求与预算预留使用同一个值，病例请求/模型参数不能提高。2026-09-20核对[DeepSeek官方人民币价格表](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/)：`deepseek-flash`高峰、缓存未命中输入2元/百万token，输出8元/百万token，现有保守计价系数未变。固定日期不单独阻断调用；后续仍应操作前核价，已知价格变化须更新系数和测试。代码仅允许已核价模型及原API目标，原账本逐请求原子预留；usage超过预留上界会标记异常并保留真实累计值。预留与usage估算均非平台账单；新无累计拒绝策略**不保证平台实际扣款上限**，操作者应另外监控平台账单。

WP-09普通网关默认每turn最多5次模型请求；WP-11由可信runner固定传入4次上限，包含工具调用、最终JSON、一次业务修复和429/5xx重试，worker恢复沿用同一turn既有调用记录。两者保留120秒门禁、最多6工具调用/3搜索；SDK重试关闭，网关仅429/5xx最多再试一次，每次仍预留。结构JSON修复最多一次；原生工具收集最多3轮，然后独立JSON阶段，实际探针用1轮两工具。所有tool_call_id原样回传ToolMessage，稳定逻辑key经既有执行器/MCP/权限/预算/receipt。模型不能传actor/case/profile或增加预算。网关不是硬实时抢占器，正在进行的同步请求受HTTP timeout约束，晚于turn期限的响应拒绝使用。

## 可复制验证（不默认付费）

先按README创建全新xiutu_test_*库并迁移，静默配置DATABASE_URL=TEST_DATABASE_URL。不加载旧.env、不复用业务库。标准完整入口包含BGE/旧E5真实索引、五工具、MCP等；不收集tests/live。

```powershell
Set-Location E:\Work\xiutu-v5
$env:PYTHONPATH='E:/Work/xiutu-v5/backend'
# 已配置本轮专用 TEST_DATABASE_URL；不会加载项目.env
.\scripts\test.ps1
```

单独重现本包真实工具演示（需要仍有效的共享授权/价格，命令会付费，不能当离线回归运行）：

```powershell
$env:XIUTU_WP09_LIVE='1'
$env:WP09_EVIDENCE=Join-Path $PWD ('.test-runs/live-evidence-'+[guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $env:WP09_EVIDENCE | Out-Null
$base=Join-Path $PWD ('.test-runs/live-'+[guid]::NewGuid().ToString('N'))
uv run --frozen python -B -m pytest tests/live/test_deepseek_tools.py -q -s --basetemp $base
Remove-Item Env:XIUTU_WP09_LIVE
```

该演示在隔离库上传合成资料、解析/审核/BGE索引、建立可信case和MCP授权，通过独立MCP进程执行search_manuals/get_measurement_spec，保持两调用ID，再返回受Pydantic约束的合成JSON。不接触私人手册，不是真实维修效果；首轮截断日志与最终成功轨迹分别封存。执行前必须准备.test-runs父目录且指定全新目录，勿覆盖历史。

## Skills

skills/cooling-system-diagnosis为方法示例，不是维修证据。registry仅加载受控安装目录，元数据选择→按需正文/引用哈希→工具allowlist交集；上传资料不能注册Skill。manifest及正文/引用需由可信维护者共同更新，不提供模型写入接口。路径越界、重解析、hash错误、未知工具都拒绝。后续WP10校验语义支持，WP11才接诊断图。
