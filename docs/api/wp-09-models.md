# WP-09 factory / gateway 接口

本包没有新增可由浏览器/模型任意选择provider、密钥、模型路径的HTTP端点。现有认证、owner、manifest、revision、工具预算和MCP授权继续由可信应用创建。

- embedding_factory(settings, config=None) -> Embedding；config为已冻结index完整指纹，缺省采用服务器设置。embed_documents(texts)、embed_query(text)返回已验证finite/L2向量；E5=384，BGE=1024。
- llm_factory(settings, paid=False, ...) -> LLM；默认不能联网；generate_structured(schema,messages)返回严格Pydantic实例，invoke_with_tools保持provider调用IDs；run_tools只消费可信ToolContext/Skill元数据并调用既有ToolExecutor。
- health_config不访问模型，configured不等于verified；实例真实验证见独立轨迹，不能通过健康200宣布模型支持。
- SkillRegistry.list_metadata/select/load_body/verify_hash/load_references只读取受控安装目录，正文/引用哈希检查、路径拒绝及权限交集。

兼容变化：POST /api/v2/documents/{id}/versions/{vid}/reindex 的config_version可省略；显式值必须等于当前服务器选定配置，允许字面值e5-small-onnx-v1或bge-m3-onnx-v1。不能请求任意维度/路径。现有幂等key、owner和active资格门禁不变。GET/搜索保持chunk/version/index/locator语义；trace.model从固定单模型字典改为实际参与配置列表。会话固定旧index仍按旧模型编码，不用新active替换。

错误：EMBEDDING_CONFIG_MISMATCH/INDEX_CONFIG_UNAVAILABLE/MODEL_PATH_UNAVAILABLE拒绝错误模型配置；MODEL_CONFIG_UNAVAILABLE缺密钥；PAID_CALL_NOT_AUTHORIZED默认付费拒绝；BUDGET_POLICY_MIGRATION_REQUIRED旧账本尚未显式迁移；MODEL_PRICE_UNVERIFIED未知模型；MODEL_EMPTY/TRUNCATED/SCHEMA_INVALID不伪装成功；401不重试，429/5xx最多一次，usage未知保留unknown及预留。累计¥5拒绝已由后续明确授权取消；历史上限仍记录于原账本。详细范围与运行示例见../runbooks/models.md。

没有WP10语义支持校验器、正式诊断提案发布或Agent图；返回JSON只证明结构/工具结果对应，不是真实维修结论。

实际Pydantic schema、安装Skill元数据与BGE指纹导出见[wp-09-schemas.json](wp-09-schemas.json)。
