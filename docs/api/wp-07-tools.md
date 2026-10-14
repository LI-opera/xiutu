# WP-07 五工具应用接口

本包新增Python应用接口及LangChain适配器，没有新增HTTP/MCP端点。HTTP API继续由既有服务提供，OpenAPI未新增工具路由。正式Agent、观察提交/修订、前端均未实现。

入口：`ToolExecutor(engine, settings)` → `executor.contexts.open(auth_store, current_cookie, case_id, …)` → `executor.execute(context, name, arguments, logical_call_key)`。AuthStore/cookie来自已认证应用入口，case先校验owner。仅可信服务可设置allowlist及预算；模型只提交五工具各自schema中的参数。可选run_id必须属于该case；本包演示不伪造Agent run。

| 工具 | 输入 | 主要输出 |
| --- | --- | --- |
| search_manuals | query、vehicle_scope、top_k 1..10 | frozen index的chunk/version/hash/locator、适配、正文 |
| get_evidence_context | chunk_id、document_version_id、neighbors 0..2 | 同版本中心及左右邻块，最多5块 |
| get_measurement_spec | component_key、quantity、vehicle_scope | 当前case有效approved规格候选、版本及证据ID |
| compare_measurement | spec_id、十进制字符串value/null、unit、conditions | 持久comparison_id、规格版本、换算、结果；diagnosis=false |
| get_case_observations | area_id可选、at_revision | 真实数据库有效记录；无生产记录为空 |

输入、输出完整JSON Schema及摘要SHA256见[wp-07-schemas.json](wp-07-schemas.json)。字符串、集合、邻块及总输出65536 UTF8字节受限，不以截断伪造完整结果。参数extra=forbid；条件映射允许合法动态工况键。上下文、owner/profile/manifest、预算和调用身份不在模型输入中。

统一信封为ok/data/error/provenance/duration_ms。空结果是ok=true且empty=true；配置不可用、授权失效、错误输入、超时和预算耗尽均为ok=false并有不同code。compare未批准或失效不得判within_range。within_range不是部件正常结论。

同execution+call_key同输入重放；异输入CALL_CONFLICT，未完成CALL_IN_PROGRESS/UNCERTAIN。比较记录及成功receipt同事务，失败/超时/取消回滚；迟到结果不覆盖终态。历史响应重放仍检查当前cookie、revision及资料有效性。预算持久预留，每次尝试包括失败均扣除，最多一次有依据的只读瞬态重试；比较不盲目自动重试。

## 可复制演示
先按README创建并迁移全新xiutu_test_*库，静默设置TEST_DATABASE_URL；只复用已确认归属的项目数据库服务。已有固定本地E5需要可用，不联网下载模型。项目根运行：

```powershell
uv run --frozen python -B scripts/demo_tools.py
```

脚本通过项目开发测试harness，使用新owner及合成资料，经真实HTTP上传/解析/审核/索引/会话/证据/规格后，由可信应用上下文逐个调用五工具与真实LangChain adapter。输出独立.test-runs/wp07-demo-UUID下demo.xml、five-tools-*.json、demo-limits-*.json。展示空观察、拒绝、预算耗尽、旧索引固定及撤销后拒绝。观察读库的revision/supersedes非空fixture验证另见集成测试test_real_observation_revision_filter；演示不会写生产观察或维修标准。

依赖开发测试工具是当前演示的明确前置，不是正式用户工作台。不要把同一adapter绑定的call_key用于不同输入；可信调用入口每个新逻辑调用建立一个adapter，重放才复用。真实ToolCall输入返回ToolMessage；普通invoke成功为字典，SDK参数错误为JSON错误信封字符串，直接execute始终返回字典。

完整契约、预算/取消/不明结果边界见[WP07契约](../implementation/phase-03/wp-07-contract.md)。M306—M311留WP08，E10/真实资料门槛不变。


## receipt v2兼容说明（WP07 r1整改）
成功receipt的内部格式升级为v2，公开五工具输入/输出schema不变。只恢复固定chunk/观察引用位置，合法业务键text、payload和_restore_*（含观察嵌套payload）无损保留。旧无版本receipt返回RECEIPT_UNSUPPORTED且不重新执行、不扣预算，原记录与历史HTTP读取保留。
比较重放同时检查原comparison自身有效性及case/spec/原调用关联；撤销后重新批准不会抹掉旧比较的needs_review，此时返回COMPARISON_INVALID。既有GET历史仍可读且显示invalid，新业务调用用新key按正常权限与预算执行。重放不会重新检索或重新比较，chunk仍使用冻结index并检查当前资格，观察仍使用原revision/area筛选。

## WP08接入变化
WP07本身的历史验收范围不变。当前执行器默认`Settings.tool_mode=remote_mcp`，三项资料只读工具通过[真实业务MCP](wp-08-mcp.md)；可信应用配置`mcp_client_config`，模型参数不能指定endpoint或token。要运行WP07本地适配/故障测试，显式`tool_mode=local`。比较/观察仍本地，不暴露给MCP。远端失败不回退；预算/审计/receipt v2仍在应用事务。
