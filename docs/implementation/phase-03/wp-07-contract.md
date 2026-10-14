# WP-07 五业务工具与执行器契约

本包只有可信应用/CLI与LangChain适配器，不新增HTTP、MCP、Agent turn或观察写入API。0007_tools接0006；观察为真实只读存储，测试fixture不冒充生产观察。

## 可信上下文与输入
ContextFactory由应用持有的AuthStore和当前cookie创建上下文，服务端固定actor/case/revision/manifest/profile/allowlist。数据库保存预算会话及随机capability的哈希；ToolContext不出现在模型schema，不能由模型参数构造。调用时重新认证并检查revision、manifest和当前source资格；重启可由同一actor重新登录后持capability恢复，不能提高已保存预算。run_id可选且验证归属，无Agent时用独立execution_id，不伪造run/turn。
vehicle_scope只收窄：非空精确字段冲突拒绝，未给字段继承case约束；补充case未知字段只过滤候选，不能把原本unknown来源升级为可用规格。所有schema extra=forbid。query<=2000，top_k1..10，neighbors0..2（中心两侧各最多2），结果<=65536 UTF8字节，不截断成虚假完整。

## 五项工具
search_manuals(query,vehicle_scope,top_k)：调用现有混合检索，强制冻结manifest，返回chunk而非evidence。
get_evidence_context(chunk_id,document_version_id,neighbors)：同版本相邻ordinal，通过资料服务和当前资格校验；无权不等于empty。
get_measurement_spec(component_key,quantity,vehicle_scope)：只读当前case有效approved且matched的规格，最多20候选，不能任取一个；超限明确错误。
compare_measurement(spec_id,value,unit,conditions)：从已验证规格推导quantity，调用WP06服务，持久比较记录；key=tool-call UUID。与工具成功receipt在同一个事务，不能迟到单独提交。
get_case_observations(area_id?,at_revision)：0<=at_revision<=上下文revision；按case/area与created_revision读取，截至该revision已被supersedes的新记录替代者排除。area可空，不建立正式区域/步骤流程；无记录为空，后续真实写入接入须复测。

## 返回、审计与重放
统一ok/data/error{code,message,retryable}/provenance/duration_ms。五种输出模型分别校验，错误不抛秘密。无匹配ok=true且empty；权限、参数、配置、超时、预算、失效分开。
逻辑身份execution_id+call_key唯一；同身份异参数/工具冲突，进行中不并行重做；终态重复重新鉴权与有效性检查后返回保存结果。审计只保存hash、状态、耗时、attempts、结果引用/必要结构化摘要；chunk正文和观察payload全文不入tool_calls，重放按固定受信位置的引用从已授权不可变源重新装配，不重做检索/比较。条件及规格等必要结构化业务数据中的text/payload键不属于上述全文引用。

## 预算、超时与提交
预算按execution_id持久化，总尝试最多20（默认8）、search最多10（默认3）、瞬态重试最多1。每次尝试先短事务锁预算行原子预留；失败/超时消耗，重复/校验拒绝不消耗，搜索重试同时扣两种预算。额度由可信入口固定，模型不能指定。只重试明确TOOL_TRANSIENT/DATABASE_BUSY；比较写入不自动重试，提交不明返回CALL_UNCERTAIN，先读取持久receipt，不盲目重做。
执行同步且有deadline；不以后台future超时假装终止。耗时只读推理可晚返回，但不得发布成功。比较加入外层事务，输出校验后写成功receipt，再以数据库clock_timestamp复查原deadline并提交；超时/取消整体回滚比较/幂等记录/成功receipt，另写失败终态。deadline到提交之间保持同物理连接/行锁；不是网络提交耗时的实时保证。statement_timeout限制SQL等待。
取消由可信入口设置tool_call.cancel_requested；最终发布锁call行检查，取消先提交则回滚，成功先提交则取消不覆盖成功。进程死亡留下running，截止后标CALL_UNCERTAIN；不自动重跑，成功receipt与副作用原子性用于判定。对未结束数据库事务的恢复还须等待其行锁释放，不强杀未知进程。

## 观察存储
observations：case/area/step UUID、kind、payload JSONB、created_revision、supersedes_id、actor、created_at，旧行不可修改/删除；替代只能同case/area/step且revision递增，唯一后继。area/step尚无实体表，本包仅可空关联标识；明确不实现WP12提交或修订入口。输出限制50条/总大小，超限不静默漏记录。

E10 NOT_VERIFIED最迟WP09，真实资料NOT_MET最迟WP10/真实效果验收前；SSE首次根因未确认。同任务审核历史和非阻断待办保留。M306—M311不在本包。


## LangChain 与错误边界
固定直接依赖 langchain-core==1.6.3，实际 StructuredTool.from_function(args_schema=…) 和 invoke 已验证。导出使用SDK函数工具外壳，parameters保留该工具实际Pydantic输入schema（SDK默认tool_call_schema会丢对象extra配置）。conditions是有类型的字符串映射，不能用provider strict把全部键禁止；本包不声明远程模型厂商strict兼容，也不发LLM请求。普通invoke成功返回字典，ToolCall输入返回保留tool_call_id的ToolMessage(JSON)；SDK自身参数校验拒绝返回同错误信封的JSON字符串。应用可直接调用ToolExecutor获得统一字典。

工具不存在/allowlist/上下文/参数拒绝发生在预算预留前，不新增tool_calls；记录针对已接受执行的逻辑调用。原始参数只留SHA256；比较必要数值/工况及规格定义保留为可复核结构化摘要，chunk正文、观察payload和凭据不存入审计。元数据与总返回上限仍适用。调用者不得在call_key内放凭据；它是应用生成的1..100位ASCII逻辑标识。capability仅可信进程持有，数据库只存哈希；不得把cookie/capability传给模型或写入日志。

常见错误：TOOL_UNKNOWN、TOOL_FORBIDDEN、CONTEXT_INVALID/STALE、UNAUTHORIZED、REVISION_CONFLICT、PARAM_INVALID、SCOPE_CONFLICT、CORPUS_NOT_ALLOWED、NOT_FOUND、SPEC_NOT_APPROVED、SOURCE_INVALID、EMBEDDING_UNAVAILABLE、OUTPUT_INVALID、RESULT_TOO_LARGE、TOOL_TIMEOUT、TOOL_CANCELLED、BUDGET_EXHAUSTED、CALL_CONFLICT/IN_PROGRESS/UNCERTAIN。只有明确TOOL_TRANSIENT/DATABASE_BUSY标记可重试；既有数据库无SQLSTATE/认证等错误不通过文本猜测瞬态。客户端不得通过新execution或call_key绕过同一逻辑调用；新execution创建权仅在可信应用，后续Agent整轮预算尚未实现。

发布锁顺序为owner→execution（预留时）→call；比较复用owner→WP06领域锁→call发布，cancel仅短事务锁call，不拿owner锁。预留以后的每次尝试有持久deadline；入口鉴权/预留锁等待不计入处理deadline。只读推理同步返回，deadline不是硬实时抢占线程/CPU的保证；过期结果不能发布成功。owner粗锁性能和进程不明调用人工处置是后续非阻断待办，不宣称通用任务框架或跨外部系统exactly-once。


## r1整改：receipt v2与历史比较门禁

成功result_summary采用独立顶层结构 `{receipt_version: 2, tool: 工具名, answer: 信封摘要}`。工具名来自执行器注册表，格式版本不从模型参数读取。只有search_manuals/get_evidence_context的answer.data.chunks[*].text、get_case_observations的answer.data.observations[*].payload被省略并在原位置恢复；不使用递归标记解释。conditions、definition、locator及观察payload内的text、payload、_restore_note、_restore_text等合法键（包括任意嵌套）均按业务数据保留，不删除、不作为指令执行。输入conditions仍遵循既有字符串映射规则，并未放宽为任意嵌套对象；观察payload可以包含嵌套JSON。

重放先做原有cookie/capability/execution/case/revision/冻结manifest门禁，在owner锁和同一事务下：chunk调用WP06 source复核owner、version/index、profile、authorization_epoch及当前资格，并验证index成员、hash/locator；上下文还复核原请求中心与neighbors，search复核收窄scope。观察按原case/area/at_revision及supersedes规则重新筛选，恢复仅限已保存ID的payload，不补入后来出现的记录。恢复后仍执行工具输出schema、信封及65536字节限制。固定索引不会被当前active替换。

无版本的旧receipt及不支持的格式返回不可重试RECEIPT_UNSUPPORTED；原成功审计状态、摘要、比较及预算保留。不会递归解释旧_restore_*、猜测修复、删除旧记录或重新执行副作用。调用者可经既有HTTP历史接口查看比较；不要用新key冒充旧调用恢复。若业务明确发起一个新比较，才使用新的逻辑身份及正常预算。

compare重放使用WP06 get_comparison的当前有效性逻辑（复用外层事务），检查comparison与当前case/spec、原tool-call幂等记录ID及请求hash、不可变结果对应。比较自身needs_review会返回不可重试COMPARISON_INVALID，即使规格已重新批准；不得修改旧outcome或清除复核标记。历史GET继续保留原内容并标invalid。新key的新合法比较允许执行。重放成功、失效或旧格式拒绝均不追加比较/幂等记录，不增加attempts或预算。该读取扩展不改变原HTTP入口自行建立事务的行为。
