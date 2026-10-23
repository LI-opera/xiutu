# WP-01 实测依赖兼容矩阵

记录时间：2026-09-18T03:12:45.742118+08:00。WP-01 r1整改后实测，等待独立r2审核；历史结果保留在原result/review。

Python 3.12.10 / Windows amd64；uv 0.11.28；Node v24.14.0（.node-version + 实际前置检查）；npm 11.9.0。
`uv.lock` 是 Python 唯一解析锁，requirements 文件由 `uv export --frozen --no-emit-project` 导出。
前端由 `frontend/package-lock.json` 锁定，使用 npm ci 复现。

| Python 包 | 实装版本（两个环境一致） | 验证 |
| --- | --- | --- |
| xiutu | 0.1.0 | 锁定安装、第二环境同版本；适用边界见下表 |
| fastapi | 0.141.1 | 锁定安装、第二环境同版本；适用边界见下表 |
| pydantic | 2.13.5 | 锁定安装、第二环境同版本；适用边界见下表 |
| pydantic-settings | 2.15.0 | 锁定安装、第二环境同版本；适用边界见下表 |
| uvicorn | 0.53.0 | 锁定安装、第二环境同版本；适用边界见下表 |
| sqlalchemy | 2.0.54 | 锁定安装、第二环境同版本；适用边界见下表 |
| psycopg | 3.3.5 | 锁定安装、第二环境同版本；适用边界见下表 |
| psycopg-pool | 3.3.1 | 锁定安装、第二环境同版本；适用边界见下表 |
| alembic | 1.20.0 | 锁定安装、第二环境同版本；适用边界见下表 |
| pgvector | 0.5.0 | 锁定安装、第二环境同版本；适用边界见下表 |
| langchain-core | 1.6.3 | 锁定安装、第二环境同版本；适用边界见下表 |
| langchain-deepseek | 1.1.0 | 锁定安装、第二环境同版本；适用边界见下表 |
| langgraph | 1.2.11 | 锁定安装、第二环境同版本；适用边界见下表 |
| langgraph-checkpoint-postgres | 3.1.2 | 锁定安装、第二环境同版本；适用边界见下表 |
| mcp | 1.30.0 | 锁定安装、第二环境同版本；适用边界见下表 |
| pytest | 9.1.1 | 锁定安装、第二环境同版本；适用边界见下表 |
| ruff | 0.16.8 | 锁定安装、第二环境同版本；适用边界见下表 |

| 组合/能力 | 本轮实测 | 证据与边界 |
| --- | --- | --- |
| Python锁与第二独立环境 | PASS | second-frozen.txt、second-pip-check.txt、primary/second-versions.txt；没有复制旧环境 |
| FastAPI/Pydantic/Uvicorn | PASS | 两环境真实HTTP ready200，无DB配置503；启动前无5433监听时故障503；缺迁移/错版本反例通过 |
| SQLAlchemy2/psycopg3/Alembic | PASS（环境迁移） | 共享目标门禁35个无连接用例通过；最终实际driver参数相同；迁移仅vector+alembic_version |
| PostgreSQL16.14 / vector0.8.2 / Python pgvector0.5.0 | PASS（技术探针） | 真向量顺序[1,2,3]、schema清理；不是维修语义检索效果 |
| LangGraph1.2.11 / Postgres checkpointer3.1.2 | PASS（跨进程探针） | A/B不同PID、相同workflow恢复count=1、错误ID退出4；不代表生产fencing/事务恢复完成 |
| MCP1.30.0 Streamable HTTP | PASS | 两环境SDK真初始化/list/call、协议2025-11-25、停服后有界连接错误 |
| DeepSeek适配器1.1.0 + LangChain | PASS（仅离线） | 实际适配器、schema、tool_call_id/结果和模拟超时；MockTransport，无真实模型调用 |
| DeepSeek live | NOT_VERIFIED | E10无付费授权；不计为核心通过项 |
| React/ReactDOM19.3.0 + TS5.9.3 + Vite7.3.6 | PASS | 主目录及全新前端副本npm ci/typecheck/build；Node版本门禁2测试通过 |
| Docker29.4.0 / Desktop4.69.0 / Compose5.1.1 | PASS（本轮可用） | 用户自行修复；本轮只核对并启动xiutu-v5专用服务，未改全局设置 |
| pgvector/pgvector:0.8.2-pg16-bookworm | PASS | 实测并固定digest sha256:00ba258a66dac104fd5171074a0084462a64a1369d8513f3d0a634e2f24d15bc；image-and-resource.json |

以上证据位于 `../implementation/phase-01/evidence/wp-01-remediation-r1/`。主环境和全新第二环境完整tests/contract + tests/probes各66 passed、0 failed/errors/skipped、1 warning；一次Starlette/AnyIO弃用警告保留，不屏蔽。两座独立测试库结束后无wp01_* schema，public仅alembic_version。首次完整65 passed后追加真实拒绝重复库回归，最终为66；不是复用历史22统计。

共享连接策略是WP-01本地隔离限制，拒绝原始DSN覆盖项与非空PG*，不代表生产任意数据库配置已支持。Node版本来自.node-version并与package.json engines核对，安装、构建、类型检查实际执行门禁。

详见[逐ISSUE整改](../implementation/phase-01/wp-01-remediation-r1.md)。资料仍NOT_MET，E10仍NOT_VERIFIED。技术通过不等于用户接受或维修能力完成。


## WP-04 当前增量（单现有环境）

uv add解析锁、uv export --frozen导出requirements；uv sync --frozen及uv pip check实测。未重建第二venv，不将WP-01双环境结论套用新增包。

| 新增直接依赖 | 实装版本 | 本包用途 |
| --- | --- | --- |
| pypdf | 6.19.0 | 本地PDF结构校验/逐页抽取，扫描/含图页缺项；不做OCR |
| markdown-it-py | 4.2.0 | Markdown语义块与源行范围；不渲染/执行HTML |
| python-multipart | 0.0.32 | 低层流式回调，先限实际接收字节再写盘 |
| tiktoken | 0.14.0 | 本地封存cl100k_base词表，SHA256核验、可复现BPE计数 |

真实测试证据见[WP-04目录](../implementation/phase-02/evidence/wp-04/)。没有模型调用；token不是DeepSeek计费或embedding验证。参考：[Starlette请求资源限制](https://www.starlette.io/requests/)、[tiktoken官方实现](https://github.com/openai/tiktoken)、[pypdf官方文档](https://pypdf.readthedocs.io/)。没有直接使用会先spool完整文件的request.form，文件限额在流式回调实施。


## WP-05 当前增量（单现有环境）

| 组件 | 实装固定版本 | 实测边界 |
| --- | --- | --- |
| onnxruntime | 1.30.0 | CPUExecutionProvider真实FP32推理，无CUDA依赖 |
| tokenizers | 0.23.2 | 本地固定tokenizer.json；480内容token窗口，不联网 |
| numpy | 2.5.3 | 有限值/维度/范数验证及向量聚合 |
| intfloat/multilingual-e5-small | 614241f622f53c4eeff9890bdc4f31cfecc418b3 | 官方ONNX固定SHA256，384维，CPU真实向量；不是E10 |
| PostgreSQL16.14/vector0.8.2 | 沿用专用服务 | vector(384)精确cosine，0005索引表与激活FK，真实恢复测试 |

uv add解析锁，uv export --frozen --no-dev --no-emit-project导出；uv pip check通过。模型约470MB，运行进程工作集约765MiB、峰值约1126MiB。已核对官方模型MIT及运行时许可，见[ADR0002](../adr/0002-local-embedding.md)。实际model-probe-v2、冻结评测及测试日志见[WP05证据](../implementation/phase-02/evidence/wp-05/)。未重建第二venv或重跑未改前端，不把历史复现范围套用到新增依赖。


## WP-07 当前增量（单现有环境）

直接声明langchain-core==1.6.3（原锁已包含同版本，不升级运行时）。通过uv add解析、uv export --frozen --no-dev --no-emit-project导出，不维护第二份手写依赖真相。实际StructuredTool.from_function / invoke、ToolCall→ToolMessage及参数拒绝在真实五服务演示验证。导出parameters保留实际Pydantic schema，未宣称远程模型strict或付费调用通过。uv lock --check与uv pip check见WP07证据；未重建第二环境，未变前端不重跑。

PostgreSQL16/vector0.8.2、E5固定384维配置沿用，0007_tools增加持久预算、调用receipt和只读观察存储；M306—M311业务MCP待WP08。历史WP01 MCP探针不是本包正式业务MCP。

## WP-08 当前增量

固定直接依赖mcp==1.30.0、httpx==0.28.1（原锁相同版本），uv lock --offline解析、uv export --frozen --no-dev --no-emit-project导出；不是手写第二份依赖。SDK真实StreamableHTTPSessionManager(stateless,json_response)、ClientSession/streamable_http_client，protocol2025-11-25；三业务schema发现与实际调用都通过HTTP。官方依据：[SDK v1.30.0](https://github.com/modelcontextprotocol/python-sdk/tree/v1.30.0)、[HTTP传输规范](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports)。无SDK升级到v2，不证明远程模型strict。

Python3.12.10 Windows原venv、Linux python:3.12.10-slim-bookworm固定digest镜像均有本包实际三工具证据。Linux安装requirements所有hash校验，非root/只读挂载。PG16/vector0.8.2、固定384维本地E5沿用；无模型选型/检索评测重跑。0007不变，新增专用只读role及受保护授权配置，审计/预算留应用侧。没有新前端或第二venv；容器实际兼容不冒充完整生产部署。


## WP-09 当前增量（2026-09-19）

沿用锁定langchain-deepseek1.1.0、langchain-core1.6.3、httpx0.28.1、onnxruntime1.30.0、tokenizers0.23.2、numpy2.5.3，无新增依赖、无手写requirements分叉。uv lock --check --offline、uv pip check通过（97解析/96安装）。真实ChatDeepSeek工具调用及JSON在官方deepseek-flash实测；无远程strict保证。SDK错误/重试/usage缺失在离线MockTransport单列验证。

本地BAAI/bge-m3固定5617a9f61b028005a4858fdac845db406aefb181、MIT、ONNX dense1024；旧E5固定384保持。0008以可变维vector+按index维度CHECK触发器，真实PG16/vector0.8.2验证切换/取消/失租约/旧冻结路由及发布SQL回滚。模型文件与预处理指纹/耗时/内存见[ADR0003](../adr/0003-model-factory-and-dimensions.md)。未重测前端、第二环境或模型质量留出集；新增BGE Linux覆盖配置未做容器动态验证，不套用WP08 E5容器结论。
