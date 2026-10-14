# WP-15 正式诊断工作台本地运行

## 隔离启动

使用新的 `xiutu_test_*` PostgreSQL 数据库、独立 storage 和 `localhost` 端口。先执行迁移和图 checkpoint 初始化，再启动 API、worker 与前端。不要复用或操作 5180/5196。

```powershell
cd E:\Work\xiutu-v5
$env:PYTHONPATH = "$PWD\backend"
$env:DATABASE_URL = '<isolated test database URL>'
$env:TEST_DATABASE_URL = $env:DATABASE_URL
$env:DATA_PATH = '<isolated storage directory>'
$env:APP_MODE = 'test'
$env:RETRIEVAL_PROFILE = 'synthetic'
$env:APP_ORIGIN = 'http://localhost:5215'

.\.venv\Scripts\python.exe -B -m alembic upgrade head
.\.venv\Scripts\python.exe -B scripts\setup_graph_checkpoint.py
.\.venv\Scripts\python.exe -B -m uvicorn app.main:app --host 127.0.0.1 --port 8215
```

另开终端启动项目 worker；其数据库、storage、模型与 MCP 配置必须与 API 相同。正式前端：

```powershell
cd E:\Work\xiutu-v5\frontend
$env:XIUTU_API_TARGET = 'http://127.0.0.1:8215'
npm.cmd run dev -- --host localhost --port 5215 --strictPort
```

浏览 `http://localhost:5215/` 即进入正式 `/workbench` 入口；旧 `/preview`、`/design/workbench-v2`、`/#diagnosis`、`/#dkvb` 入口已退役，统一进入正式工作台；资料查看使用 `/documents`。本地隔离演示脚本 `scripts/wp15_workbench.py` 只管理其登记的 5215/8215 进程；`stop` 不清数据库或 storage。

### 当前本机 5215 自动登录

已配置的 WP-15 本地实例优先使用 `python -B -m scripts.wp15_workbench start` 启动。该脚本默认仅在无真实模型授权的 `stub` / `paid=false` 启动中开启 `LOCAL_DEV_AUTO_IDENTITY=1`，并继续使用 `.local-data/wp15-workbench/runtime.json` 中原有的稳定 `actor`；不会改写病例所有者。浏览器访问 `/auth/session` 时，API 仅对实际回环客户端与回环监听端点签发短期 HttpOnly cookie 和 CSRF 值。Chrome 与内置浏览器各自建立会话；刷新、重新打开页面或 API 重启后自动补发，不需要复制令牌，也不在前端代码或浏览器存储中保存管理员密钥。

关闭该模式：停止本脚本登记的服务后，用 `python -B -m scripts.wp15_workbench start --manual-login` 启动；无 cookie 的 `/auth/session` 将恢复 401 和原令牌登录。要重新启用则按默认 `start` 启动。手工运行上方 API 命令或生产实例默认**不开启**自动身份；此标志只允许非生产、回环 HTTP 配置，仍须把 Web/API 均绑定回环。不要将 5215/8215 发布到局域网或放在可远程访问的转发代理后。本功能只省去本机手动登录，病例归属、写入 Origin/CSRF、真实模型付费授权及最终报告门禁均不变。

### 病例分析输出预算

唯一服务端配置为 `CASE_ANALYSIS_MAX_OUTPUT_TOKENS`（严格整数 256–16384）。API 创建分析时把它写入冻结快照；预检、worker 网关的 `max_tokens` 与调用账本随后使用同一值。`wp15_workbench.py start` 的本地替身实例固定为 1536，已有受限一次性真实启动路径为 4096，均不因本配置能力提高而自动扩大付费预算。旧 `XIUTU_C03_OUTPUT_TOKENS` / `XIUTU_C05_OUTPUT_TOKENS` 已不再读取；手工启动服务时可统一设置新变量，API 与 worker 必须一致。高于 4096 的真实输出预算需另获用户授权，不能仅改环境变量就调用；实际提供方和输入上下文限制仍需在调用前核对。截断回复只作为受限诊断留存，不会补齐 JSON 或自动重试。

## 用户路径

1. 登录后在病例入口创建病例，或从历史页主动选择病例。
2. 在 `/workbench/{case_id}` 启动或恢复诊断。
3. 查看区域、当前检查和实际引用；按服务端 input schema 提交观察。
4. 运行中的任务通过 SSE 更新；断线时页面先恢复 HTTP 快照再重连。
5. 区域结束后查看服务端保存的结论卡。`unknown` 表示待补。
6. 用户可主动请求进度报告；最终报告按钮仅在服务端 gate 允许时启用。

## 构建与检查

```powershell
cd E:\Work\xiutu-v5\frontend
npm.cmd run api:generate
npm.cmd run api:check
npm.cmd run test:wp14
npm.cmd run typecheck
npm.cmd run build:wp14
```

构建输出为 `frontend/dist-wp14`，不覆盖既有 `frontend/dist`。真实 DeepSeek 探针是显式 live 测试，不属于常规命令；不得因失败自动创建新业务 turn。

## 已知边界

真实资料仍 `NOT_MET`。本包没有部署 5180/5196，没有证明真实维修效果、生产恢复或真实报告语义。真实续轮可能按现有资料保守生成 `unknown`，不能解释为第二项检查、确诊或最终报告就绪。
