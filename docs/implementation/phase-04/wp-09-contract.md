# WP-09 实施契约

本包：ModelGateway、可信 Skills、用户额外授权的模型配置 factory 与本地 BGE-M3 接入。不是 WP10 提案校验器、WP11图、观察写入或正式UI；不回写旧接受范围。

## 文件、调用顺序及配置

新增 infrastructure/model_factory.py、bge_gateway.py、model_gateway.py、model_budget.py、skills/registry.py、受控 skills/cooling-system-diagnosis、相关离线/集成/live测试及探针。调整 Settings、index_service/index_builder/index_state/retrieval/service、MCP配置/Compose模型挂载说明。新增0008_model_indexes，更新ORM/health，不改0001—0007。

Settings()不自动读.env；load_settings(project_env=True)显式读取固定项目.env，测试模式/TEST_DATABASE_URL禁止读取项目.env。优先级：显式调用参数 > 进程环境 > 项目.env > 默认值。只导入已知设置，API key为SecretStr；缺配置明确失败，不自动付费、下载或fallback。真实.env不进证据/哈希清单。APP加载入口显式开关，隔离启动器不带开关。

Embedding协议：embed_documents(list[str])->list[list[float]]、embed_query(str)->list[float]、config完整指纹。E5保持旧指纹，BGE固定本机revision/ONNX文件哈希、1024维、CLS/L2、无前缀、480内容token窗口及加权聚合版本。只用dense分量，不称完整M3 sparse/ColBERT。模型工厂拒绝未知provider/config/路径/维度，旧索引使用旧E5路径；队列入队冻结config，worker按冻结config选择，不按当前默认偷换。

## 索引兼容

0008将向量列改为不固定维度的vector，索引只允许384/1024；DB触发器核对向量维度与索引dimension，应用发布继续检查完整指纹、数量、来源与有限值。降级遇1024索引明确拒绝，不删新数据。现有384数据原样保留。按index指纹分别编码查询、分别计算cosine后合并dense候选；不跨维度计算。新旧冻结manifest不变，active原子切换与租约最终校验继续复用WP04/05路径；不批量重建业务资料。

## LLM及共享预算

LLM协议generate_structured(schema,messages)、invoke_with_tools(messages,tool_schemas)、health_config。锁定LangChain DeepSeek，SDK max_retries=0；网关仅429/5xx有限重试，所有尝试先预留费用。工具收集与最终JSON阶段分开，多tool_calls按原ID逐个经既有executor（前三工具remote_mcp），模型不能提交可信身份。结构修复最多一次，含在每轮最多5模型调用/120秒内；工具限额由已有持久execution控制（默认6/搜索3）。调用身份稳定，重复/不明确调用不盲目重做。

预算账本固定项目私有.local-data/wp09-budget.json，所有真实调用（含后续审核）共用，跨进程文件锁、原子替换、总额5元不可由调用参数提高。每次按已核实价格及保守输入上限/明确max_tokens先预留；失败或usage缺失保留整个预留，usage记unknown而非0。崩溃reserved不释放。真实模式只允许核实价格的官方HTTPS目标/模型，不跟随重定向；费用为保守峰值上界，实际账单另有usage估算。未获明确真实调用开关不联网。隔离测试账本/MockTransport与真实账本分离，不能自动消耗授权。

## Skills与边界

受控安装目录只读加载，manifest含name/version/sha256/allowed_tools/applicable_systems/required_context/output_schema/status及引用hash白名单。frontmatter只有name/description。list_metadata/select/load_body/verify_hash/load_references拒绝越界、符号链接/junction、hash篡改；正文和引用按需加载。工具权限取既有可信上下文与skill白名单交集，不扩权；上传目录不允许作为Skill根。examples仅方法示意，不是evidence。冷却技能只描述方法和缺项，不写固定诊断树。

## 验证与停止

先离线错误/多调用/预算/技能用例，再真实BGE与PG索引兼容/故障发布，最小DeepSeek→真实工具/MCP→JSON轨迹，最后标准完整入口一次。记录A401—403/E10实际能力，未知不冒充通过。保留真实资料NOT_MET（WP10/真实效果前）、SSE/Compose未确认根因及同任务限制。完成IMPLEMENTED_NOT_ACCEPTED；核心依赖受阻则BLOCKED，停止等待集中审核。


## 实装补充

真实调用使用用户明确批准的deepseek-flash，不修改私有.env。固定max_tokens768，tool_round_limit由可信应用选择1—3，工具收集结束直接进入JSON阶段；不需要额外自由文本总结。模型请求只允许tools/response_format选项，不能覆盖输出上限。费用预留输入上界为UTF8字节×4+4096，峰时2/8元每百万token；有效核价期限2026-09-20 UTC，之后明确要求重新核价。文件账本不退款不重置；同步HTTP非硬实时抢占，但迟到响应不用于后续执行。

标准完整入口不收集tests/live，真实probe额外要求XIUTU_WP09_LIVE=1、独立库与已授权共享账本。E10证据为原生多调用经现有remote_mcp执行并对应返回，再Pydantic JSON验证；截断、429/5xx、无usage等错误以离线契约测试证明，不刻意付费触发故障。当前BGE本地nativeMCP通过，新增Linux BGE挂载示例未动态验证，旧包Compose历史不替代它。


## r1定点整改：出站载体与预留后期限

发送前复制消息，不原地改写输入、可信上下文或业务记录。支持字符串content、仅含type/text的文本块和函数tool_calls.arguments JSON对象；SDK可将多个文本块规范化为换行连接字符串。在SDK转换之前拒绝图片、音频及未知块/附加字段，返回MODEL_MESSAGE_UNSUPPORTED，尚不预留预算或调用transport。历史工具参数解析为JSON，递归脱敏字符串值，保留数字/布尔/null/容器结构；敏感JSON键拒绝而不改名。电话/邮箱/VIN按既有规则脱敏，不保证通用PII识别。角色、函数名、call ID是协议身份，不对整包做替换；相关ToolMessage正文同样脱敏。非有限JSON数值拒绝。

reserve可能跨进程等待；返回后紧邻SDK发送前重新检查120秒turn期限。若过期，MODEL_TURN_TIMEOUT，终态not_sent、dispatched=false，保留预留金额与usage=null/unknown，不退款、不重试、不发送。若终态持久化自身失败仍不发送，可能留下原reserved供核查。发出后迟到响应仍记录received/usage但拒绝后续使用；received不代表应用接受结果。同步执行不是硬实时抢占，检查到发送之间仍有不可消除的调度边界。本补丁不改共享总额门禁或SDK零重试策略。

E10原审核限定结论保留；Linux BGE未验证部署仍排除。仅执行者定点自测，等待差异复核，不构成接受。
