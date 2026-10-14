# WP-08 业务 MCP

独立服务Streamable HTTP `/mcp`，SDK mcp1.30.0 / protocol2025-11-25。不会把MCP工具塞入FastAPI OpenAPI；协议发现用tools/list，真实输入输出见[导出schema](wp-08-mcp-schemas.json)。主应用HTTP OpenAPI本包未增业务端点。

| 工具 | 输入 | 返回与权限 |
| --- | --- | --- |
| search_manuals | query, vehicle_scope, top_k1—10 | case冻结索引、当前资格+收窄scope的chunks；empty不同于故障 |
| get_evidence_context | chunk_id,document_version_id,neighbors0—2 | 同版本中心/相邻块，当前owner/manifest/index/epoch检查 |
| get_measurement_spec | component_key,quantity,vehicle_scope | 当前case有效approved规格列表/来源，不任取一个、不比较或写库 |

统一ok/data/error/provenance/duration_ms；extra=forbid、输出65536 UTF8字节。公开请求无owner/case/profile/预算参数；授权来自受保护服务端映射。服务token、用户cookie、capability独立；无Origin的CLI仍认证。旧session ID不能作为身份。本包使用stateless并拒绝session header。

应用ToolExecutor默认remote_mcp，三只读调用确实走SDK HTTP；另外两工具本地执行。显式local测试模式无自动fallback。远端返回仍经本地输出/大小/来源校验，receipt v2不改变；应用预算记录每次尝试，客户端自身不重试。详见[契约](../implementation/phase-03/wp-08-contract.md)和[运行手册](../runbooks/mcp.md)。

仅后端适配器及CLI，不声称业务UI、Agent、远程模型strict兼容或真实维修效果完成。M306—M311实际自测结果见[交付](../implementation/phase-03/wp-08-result.md)，等待审核及用户决定。
