# WP-08 真实业务 MCP 契约

仅三项只读工具：search_manuals、get_evidence_context、get_measurement_spec。SDK mcp 1.30.0，Streamable HTTP /mcp，协议2025-11-25。stateless HTTP，每次连接重新initialize，不以session ID授权；本服务拒绝携带Mcp-Session-Id，不复用有状态session。

## 权限及事务
服务端受保护JSON将token的SHA256映射到actor/case/revision/manifest/profile/allowlist/过期时间；CLI与应用各自独立token。每个HTTP请求认证，工具执行前后重新加载映射和当前资料资格。正文只接收WP07的工具参数，不能选择身份或profile。Host精确白名单，Origin出现时必须精确匹配白名单，无Origin的CLI仍须Bearer认证。配置变化失效token立即拒绝。配置文件不公开、不记录；未实现OAuth授权服务器。
只读角色只授予指定业务表SELECT，不授予审计、预算、写入；显式readonly事务保留现有owner advisory锁，与撤销写事务串行化。检索推理不持长事务，最终重新检查范围和来源。应用侧依旧ContextFactory/原cookie/capability，预算及成功receipt同原发布事务。数据库内部只读目标仅固定postgres:5432，调试仅127.0.0.1:5433；禁止PG环境覆盖及任意DSN。synthetic只允许xiutu_test_*数据库。

## 应用适配及返回
ToolExecutor显式mode=local或remote_mcp，默认remote_mcp；旧测试/演示明确local。远端仅上述三工具，另外两项仍应用本地服务。remote_mcp配置缺失/错误直接失败，无fallback。客户端凭据绑定必须与可信execution的actor/case/revision/manifest/profile一致。发现仅接受三个工具及精确输入/信封schema。返回继续校验类型、65536字节、当前授权来源、文本hash/locator及规格关联；不信任远端UUID或正文作为授权。
SDK客户端connect/discover/call/close，单次transport尝试无内部重试；执行器仅明确连接/断连瞬态最多重试一次，每次扣总预算及search预算。认证、schema及权限不重试。默认10秒，超时终止等待，远端只读计算可能继续但应用最终deadline/取消守卫禁止迟到receipt。MCP request ID是单连接SDK身份；本地execution/call_key及attempt保持持久逻辑身份，两者不混用。重连重新initialize。receipt v2及旧格式安全拒绝保持。

## 部署与边界
无新业务表/迁移；0007_tools不改。Compose新增manual-mcp，不默认发布端口；调试覆盖仅loopback。原文、模型及配置挂载只读，容器非root、根文件系统只读，临时目录tmpfs。health仅检查DB只读角色及0007/vector，不调用模型。角色初始化仅创建新角色，已存在即拒绝，不修改既有密码。
本包不是正式Agent/UI或远程模型strict验收。E10 NOT_VERIFIED最迟WP09；真实资料NOT_MET最迟WP10/真实效果验收前；SSE首次根因未确认及既有待办保留。

## 兼容和边界补充

成功receipt重放遵守WP07：不重做检索、不新增一次MCP尝试、不扣预算；在应用当前cookie/capability/revision/冻结范围及来源校验后恢复已保存引用。这不属于远端失败后的fallback；新的逻辑读取必须走选定transport。CLI凭据有独立授权生命周期，不因应用浏览器logout自动轮换，管理员须分别撤销；应用logout立即阻断应用调用和重放。

MCP公开outputSchema使用每工具实际OUTPUTS嵌入信封（包含错误时data=null），发现时精确比对；应用额外检查正文、hash、locator、适配结果、规格原定义/候选条件及重复引用。无权或输出错误不当作empty。原文/模型的内核强制只读挂载是在Compose验证，本地调试进程不声称具备容器mount隔离。

预算边界：本地上下文/参数/allowlist在预留前拒绝仍不新增tool_calls；预留后才发现的远端配置、认证或权限错误消耗该次尝试，但不自动重试。协议initialize/list不另算业务尝试。CLI独立只读调用不冒充应用execution预算或审计。

## ISSUE-001 整改：最终授权判定点

成功响应在最终owner锁与全部来源校验SQL完成、信封schema/大小和JSON数据准备完毕后，仍持有原owner事务锁时重新读取受保护配置并authenticate。此时要求token仍存在且当前期限未到，完整Binding（含allowlist）与本次初始可信上下文相同，工具仍获允许；撤销/到期返回MCP_UNAUTHORIZED，Binding或allowlist变化返回CONTEXT_STALE，均不带成功正文。当前有效期以这次认证的实时时钟判定，不沿用锁等待前缓存结果。

最终认证之后仅做墙钟deadline检查、结束只读事务、SDK序列化/发送；不再读取新业务资料。数据库来源撤销继续由原owner锁保护。这个最终判定点不承诺网络发送后即时撤回。错误交给原应用执行器按非瞬态失败记录一次尝试，无成功receipt、无自动授权重试或local fallback。旧receipt当前权限规则不变。
