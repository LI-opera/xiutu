# 资料 MCP 操作手册（WP-08）

这是后台三项只读业务 MCP，不是正式Agent、UI或维修结论。真实数据资格未齐时正式检索允许为空。成功演示使用独立xiutu_test_*库、synthetic资料和本地E5；不会上传私人资料。

## 实际协议与权限

固定mcp==1.30.0（[官方版本](https://github.com/modelcontextprotocol/python-sdk/tree/v1.30.0)），Streamable HTTP /mcp，协议2025-11-25（[官方传输契约](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports)）。不是自制JSON API，也不是旧echo探针。stateless服务不发放session身份；带Mcp-Session-Id请求拒绝。每个请求Bearer认证，精确Host白名单；带Origin请求只接受配置白名单（默认空，即不接受浏览器来源），无Origin CLI仍必须认证。默认HTTP只用于loopback/私有Compose网络，不能直接暴露互联网；未实现OAuth/远程TLS网关。

公开工具仅search_manuals/get_evidence_context/get_measurement_spec。compare/observations、任意SQL/路径/命令均不暴露。输入复用WP07，输出schema见[wp-08-mcp-schemas.json](../api/wp-08-mcp-schemas.json)。readonly DB角色只允许cases/documents/document_versions/chunks/index_versions/chunk_embeddings/case_evidence/measurement_specs/alembic_version的SELECT；没有tool_calls、budget、写权限。保留owner事务advisory锁和执行后资格复查；READ COMMITTED下最终授权校验不是互联网交付期间的实时撤回保证。

## 准备与生成受保护配置

先按README准备唯一测试库/0007迁移及合成资料→解析→审核→索引→新case→证据→规格。不要把旧业务库用于演示。已有WP06/07测试工具可创建这些合成fixtures。DATABASE_URL仅在当前进程环境静默设置，不打印。E5模型仍为固定本地revision，不联网下载。

管理员在项目根执行（case UUID由自己的已授权会话取得）：

```powershell
$cfgDir = Join-Path (Get-Location) ('.local-data/mcp-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $cfgDir | Out-Null
$identity = [Security.Principal.WindowsIdentity]::GetCurrent().Name
icacls $cfgDir /inheritance:r /grant:r "${identity}:(OI)(CI)F" 'SYSTEM:(OI)(CI)F'
# Linux用权限700目录，生成文件为600；不能将secret放在Git或公开共享目录。
uv run --frozen python -B scripts/configure_manual_mcp.py --case-id <自己新case的UUID> --directory $cfgDir --profile synthetic --port 8031 --model-path .local-data/models/multilingual-e5-small/614241f622f53c4eeff9890bdc4f31cfecc418b3 --data-path <该合成资料存储目录>
```

脚本只接受空受保护目录，读取DB真实case/owner/revision/manifest，创建全新xiutu_mcp_*角色及随机密码，不修改既有角色密码；生成server-secret、compose-server-secret、application-secret和cli-secret文件。应用/CLI各自随机token、8小时过期，服务器只存token SHA256；token与应用cookie、capability互不替代。配置文件是管理员授权，不是模型输入。独立`scripts/provision_mcp_role.py --output <新文件>`只完成新只读role，运行前同样静默配置DATABASE_URL。配置失败后检查本次新文件/角色，不覆盖旧文件或反复修改既有密码。

权限来源由服务端配置固定，工具body不能提供case/owner/profile/manifest。凭据轮换/撤销通过受保护配置的grants更新，每次请求和工具发布前重新读取；不要删审计记录。DB/profile/mount/Host等非grant配置改变需重启自己服务。应用登录注销由应用入口检查；CLI的独立服务凭据不依赖浏览器cookie，需分别到期/撤销。

## 本地进程与双客户端

确认8031没有未知占用。只启动本次新进程：

```powershell
$env:MANUAL_MCP_CONFIG = Join-Path $cfgDir 'server-secret.json'
uv run --frozen python -B -m uvicorn app.mcp_server.main:create_app --factory --host 127.0.0.1 --port 8031 --no-access-log --log-level warning
```

health在`http://127.0.0.1:8031/health`只检测配置、当前role、数据库/vector/0007，不调用模型、不输出秘密。三业务调用通过SDK initialize→tools/list→tools/call，输出含固定资料来源。独立CLI在另一终端运行：

```powershell
# query.json只含工具参数：{"query":"voltage","vehicle_scope":{},"top_k":3}
uv run --frozen python -B scripts/probes/manual_mcp_client.py --config <cfgDir>/cli-secret.json --tool search_manuals --arguments <新的query.json> --output <新的result.json>
```

CLI结果不覆盖既有文件。文档context及规格参数见工具说明。应用端设置`TOOL_MODE=remote_mcp`（默认）和`MCP_CLIENT_CONFIG=<cfgDir>/application-secret.json`，以真实AuthStore/cookie建立ToolContext，再调用既有ToolExecutor。可信execution必须匹配该配置actor/case/revision/manifest/profile，不能把CLI token当capability。只有三只读工具走HTTP；compare与observations仍在应用侧。显式`TOOL_MODE=local`用于本地测试/故障定位，**远端失败不会自动切换local**。

应用侧逻辑execution/call_key关联持久tool_calls；每次SDK连接的JSON-RPC请求ID仅为transport身份。应用每次尝试重新initialize，只有执行器负责最多一次明确瞬态重试，搜索同时扣总额及搜索额度。认证/schema/超时不重试。默认10秒；同步只读推理可能继续至返回，但当前deadline/取消/来源校验不允许迟到成功receipt。比较事务和receipt v2保持旧保护；旧receipt/比较invalid限制不变。

## Compose（数据库服务保持原状）

默认不发布宿主端口，服务内部DB目标固定postgres:5432，不能用任意DSN或PG环境覆盖。模型/原文/配置只读，根只读、非root用户、drop ALL capabilities和no-new-privileges。基础Python镜像digest及require-hashes依赖安装固定。

```powershell
$env:MANUAL_MCP_CONFIG_FILE = Join-Path $cfgDir 'compose-server-secret.json'
$env:MANUAL_MCP_MODEL_PATH = (Resolve-Path .local-data/models/multilingual-e5-small/614241f622f53c4eeff9890bdc4f31cfecc418b3).Path
$env:MANUAL_MCP_DATA_PATH = <该合成资料存储目录绝对路径>
# XIUTU_DB_PASSWORD仅静默加载本项目本地配置；不要打印docker compose config（可能展开密码）。
docker compose -f deploy/compose.yaml --profile manual-mcp build manual-mcp
docker compose -f deploy/compose.yaml --profile manual-mcp up -d --no-deps manual-mcp
```

仅需宿主调试时增加`-f deploy/compose.mcp-debug.yaml`，设置`MANUAL_MCP_DEBUG_PORT=8031`，只绑定127.0.0.1。常规容器内应用客户端改用`http://manual-mcp:8031/mcp`，此配置属于可信管理员，不由模型提供。先核对已有容器标签/端口归属再启动；不要接管未知资源。本包实际Compose验证见wp08 evidence的compose-results/commands，非纸面配置。

停服只对自己创建的manual-mcp使用`docker compose ... stop manual-mcp`，不停止postgres，不使用down -v，不删既有库/卷。只读角色没有自行更改密码/授权的步骤。

## 可复制的全链路合成演示

已有全新已迁移TEST_DATABASE_URL和本地E5时，项目根：

```powershell
$demo = '.test-runs/wp08-demo-' + [guid]::NewGuid().ToString('N')
New-Item -ItemType Directory -Force .test-runs | Out-Null
$env:WP08_EVIDENCE = <一个新的、已创建的输出目录绝对路径>
uv run --frozen python -B -m pytest tests/integration/test_manual_mcp.py::test_real_dual_clients_and_readonly -q -s -p no:cacheprovider --basetemp $demo
```

该用例实际上传/worker解析/审核/索引/新case/证据/合成规格，通过独立MCP进程、应用执行器及独立CLI三工具往返，比较chunk/version/index/hash/locator和规格来源，再验证只读role写入拒绝。需要dev测试依赖，是可复制的后端演示，不是假UI；合成1—2V不是维修标准。

## 错误和恢复

MCP_CONFIG_UNAVAILABLE/CONTEXT_INVALID：检查受保护文件和绑定，不能以扩大manifest补救。MCP_UNAUTHORIZED/HTTP_REJECTED：检查有效期、token、Origin/Host/session规则，不重试猜测认证。MCP_SCHEMA_INVALID/OUTPUT_INVALID/SOURCE_INVALID：发现工具漂移、篡改或撤销，失败且不fallback。TOOL_TRANSIENT：明确连接/读断连，最多一次预算内重试；TOOL_TIMEOUT：不发布结果，不自动再做副作用。数据库SQL异常不解析秘密文本来猜瞬态。

恢复服务后新逻辑只读调用会重新initialize；失败的旧逻辑key保持审计终态，不能通过重放重扣预算。未完成调用仍遵循WP07 uncertain处置，不能盲目重做比较。无共享远端会话池/性能压测、OAuth或生产高可用保证；这些不等于本地三工具未实现。E10/资料门槛及既有待办保留。
