# WP-09 集中审核 r1

结论：**CHANGES_REQUIRED**。当前不建议接受；先仅整改下述 ISSUE-001、ISSUE-002，再做对应定点复核。不要求重开整包、重跑328项、前端或模型质量评测。

审核时间：2026-09-19T00:49:48.6724585+08:00。工作目录E:\Work\xiutu-v5。范围A401—A403、E10及用户授权factory/BGE扩展；不审核WP10提案语义校验、WP11图或正式UI。

**角色披露：本任务参与过WP09实施和自测，本轮切换审核角色，不是不同任务独立审核。** 新隔离库/测试不能消除该流程限制。本轮没有现场修业务实现、修改STATUS或替用户接受。

## 1. 依据及固定基准

已读适用范围AGENTS检索（E:/、E:/Work及项目/子目录未找到）、STATUS、WP09 contract/result、models运行说明、封存及原始证据、P4实施/验收，总指南9.3/9.4/WP09与P1 E10原要求。以代码和实际证据判断，不直接转抄执行者PASS。

- main，无HEAD；记录root/branch/head/status/cached/diff于本轮baseline.json。
- delivery-hashes的3669项全部匹配；seal匹配；连同seal自身共3670项作为本轮保护输入。开始/结束均无被审文件差异。
- Git index始终c451d6e78b8f29fc818002923a19fb1a888139ced20679ad545f75e9692a9ec6。旧项目63项结束哈希匹配；旧迁移/报告/接受/原证据/STATUS包含在保护集，未修改。
- 执行者完整回归full.json为2026-09-19 00:11:42至00:27:55、标准scripts/test.ps1、exit0；XML核得328测试/0失败/0错误/0跳过，日志1条既有Starlette/anyio弃用警告。
- 完整输入full-code-hashes共141项，当前差异确为tests/README说明及三份测试注释/空行。审核反向还原三份测试，匹配记录的pre-lint SHA256，AST相同、无断言变化，见baseline.json.ast_checks及full-code-ast-check.json：还原CRLF字节匹配full-code原哈希，LF规范化匹配pre-lint哈希。**328项属于该原始字节基准，不称本轮或最终字节版本重新完整运行。**
- 本轮不读取、输出、复制或封存项目私有.env。配置优先级验证用审核临时目录生成的合成.env，和私有文件无关。既有账本只读核对，开始/结束哈希一致，0新增付费请求。

证据目录：`docs/implementation/phase-04/evidence/wp-09-review-r1/`。本报告与全部新日志不覆盖原文件。

## 2. 清单结论

| 项目 | 结论 | 依据、亲测及适用范围 |
| --- | --- | --- |
| A401 原生工具执行 | PASS（限定功能链路证据） | 复核原live-2成功轨迹、两provider调用ID、逻辑key SHA映射、持久receipt成功/每项1尝试、ToolMessage构造及离线实际SDK消费测试。nativeMCP fixture确实独立启动Uvicorn，执行器remote_mcp；本轮不追加同等付费演示。仍受下述网关缺陷阻断整体接受 |
| A402 多工具、usage、错误/预算 | FAIL | 多ID、缺usage unknown、有限重试/JSON修复和共享金额预留正常；但脱敏载体不完整及预算锁等待后仍发送已过期请求，见两ISSUE |
| A403 Skills权限 | PASS（现有受控安装范围） | 本轮hash/路径/白名单单测通过；追加引用篡改及真实Windows junction拒绝通过。根仅可信代码指定，无模型/HTTP/upload安装入口；正文与引用不自动成为evidence |
| E10 原真实契约 | PASS（证据核验范围） | 原要求为授权、记录、usage、工具执行；本对话可核实5元授权及flash选择，真实4请求与成功多工具/JSON、账本关联完整。不是全网关安全已通过，也不扩大到chat、其他DeepSeek型号、远程strict或维修语义 |
| factory/配置 | PASS（已测合法配置/失败关闭） | 合成项目.env验证构造参数>进程环境>显式dotenv>默认、TEST_DATABASE_URL阻断dotenv、SecretStr repr不泄漏；原定点覆盖未知provider、缺路径和维度冲突，无静默fallback |
| BGE/E5扩展 | PASS（Windows native技术范围） | 本轮真实1024/384及固定指纹，独立worker正常/取消/失租约/中断恢复/SQL激活失败；追加同一检索混合两模型与旧manifest隔离、1024存在时降级拒绝且head/结果保留通过。不是BGE质量优于E5 |
| Linux BGE Compose | NOT_VERIFIED，明确排除 | 交付报告、契约、runbook均称未验证额外挂载示例，未宣称当前可用部署。本轮不据此扩大容器审核或启动新容器；不得借用WP08 E5镜像证据 |

## 3. 代码与证据核查

### 配置、模型及索引

Settings默认不读取.env，API/index_builder通过显式开关加载，测试环境禁止项目dotenv。两工厂不提供模型参数构造actor/case/profile的入口。当前实际实测型号只有deepseek-flash；私有文件旧chat的事实来自既有记录，本轮未读私有文件确认。runbook及live代码明确覆盖flash，可复现；旧chat不通过当前核价门禁，不宣称兼容已验证。

0008接续0007，无旧迁移变化。可变vector按index dimension检查SQLSTATE23514，应用检查完整已知指纹/数量/有限值，降级先拒绝非384索引。已有行锁、租约最终校验和发布事务路径保留。本轮测试确认旧active与冻结E5依据不被失败/取消/重建覆盖。

检索按已知指纹分组，分别使用对应模型编码查询并计算cosine，不对1024和384直接求距离；分组dense结果以距离排序取全局30，再沿用RRF和确定性适配/故障码排序。追加两文档分别E5/BGE真实混合检索和冻结旧索引通过。不同模型余弦分数未做跨模型校准，是质量解释限制，不是本轮发现的数据一致性缺陷；不能从此推导召回改善。

### 真实链路与金额

执行者成功turn：`wp09-e10-fb623e314ac544c2a797684905576b3a`。本轮核算两个provider tool_call_id经SHA256(turn+":"+id)生成的logical key，与原live-persistent-receipts两条成功记录一致；工具search_manuals/get_measurement_spec，每条attempts=1，总used=2/search_used=1。原live测试确认最终chunk/spec IDs属于工具provenance。对应关系见historical-evidence-check.json。ToolMessage实际ID消费另由本轮离线SDK测试核验；不声称保存了未封存的原始HTTP整包或本轮亲自重发了provider请求。

模型选择授权来源可核实：本任务历史async回复`call_B32LRkq3snNKQLwzdSqPZfdC`，用户回答“使用 deepseek-flash（推荐）”；结合原WP09指令累计5元授权。只覆盖该授权范围，不是任意型号/无限费用许可。

真实账本实际路径为`E:\Work\xiutu-v5\.local-data\wp09-budget.json`（本次指令文本少一个分隔符，以实现及既有账本路径核对）。4请求，含首次截断，保守预留**¥0.198184**，usage按峰时缓存未命中价估算**¥0.024582**，**平台账单未核实**。本轮新增费用0；账本未变，没有第二份真实预算。测试预算文件在本轮临时目录且只接MockTransport。

本轮只读核对[DeepSeek官方价格](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/)：flash峰时输入2元/百万、输出8元/百万，代码费率与型号一致。输入UTF8字节×4+4096和固定768输出保守预留；有效核价期限、失败/崩溃/缺usage不退额度、SDK max_retries=0与网关最多一次429/5xx重试已检查。跨进程最后额度竞争本轮真实两PID仅一方成功，失败usage unknown且重启读取保留。该机制未发现5元超支；ISSUE-002针对已过期turn仍发起请求，不能混淆为已证实金额超支。

### Skills及Linux边界

Skill root为可信应用安装配置，不由模型/上传载荷指定；hash匹配、版本、references白名单、路径及祖先junction检查有效。Skill allowed_tools与应用allowlist取交集，真实权限还经现有executor/context；未知/重复工具ID拒绝。冷却Skill只有方法与缺项提示，evidence=[]。

Linux BGE覆盖文件仅增加只读snapshot bind，仍需要匹配配置、模型文件与镜像代码。当前文件存在不构成动态加载/检索/权限证明。它已被交付明示为未验证示例，因此本轮不以此阻断Windows native范围，也不颁发Linux BGE通过结论。将来声明该运行方式可用前，需要一次有界动态验证。

## 4. 本轮命令与结果

先确认Docker Server29.4.0、项目标签xiutu-v5/postgres、原容器running且127.0.0.1:5433。复用该服务，不停旧服务、不重建容器/数据库卷。新库`xiutu_test_wp09review_3b4adbfa5300`；新临时目录分别wp09-review-targeted-90d2、wp09-review-extra-6f18、wp09-review-completion-e21a。导入当前backend源代码，新反例只位于审核目录。

| 本轮记录 | 内容 | 结果 |
| --- | --- | --- |
| create.json/txt | prepare_database，新唯一库 | exit0 |
| migrate.json/txt | alembic upgrade head至0008 | exit0 |
| targeted.json/txt/xml | tests/unit/test_wp09_contracts.py + tests/integration/test_wp09_models.py | **22通过，0失败/错误/跳过，exit0，102.44秒** |
| audit-extra.json/txt/xml | 脱敏两载体、跨进程预算、Skills引用/junction、合成dotenv、混合模型 | **3通过、2失败、1审核夹具错误，exit1**；两失败即ISSUE-001；混合模型未执行因database_url夹具未注册 |
| audit-completion.json/txt/xml | 仅补注册原tests/conftest.py夹具后运行未执行的混合模型/降级，另运行真实预算锁deadline反例 | **1通过、1失败、0错误/跳过，exit1，29.81秒**；失败即ISSUE-002 |

本轮日志未列新警告。审核夹具原版本另存conftest-first.py.txt，注册修正不改变被审测试/业务断言；没有重跑两个已失败的脱敏用例直到通过。各命令cwd、展开后的参数、起止、exit均在对应json；原始stdout与JUnit完整保留。没有重复328全量、前端、第二环境或留出评测。

## 5. A类：必须整改

### ISSUE-001 — P1：部分消息载体绕过出站脱敏

- 文件：`backend/app/infrastructure/model_gateway.py:108`至111（request转换后仅处理字符串content）；影响ModelGateway出站数据契约、A402及阶段说明第3节第4项。
- 触发：①HumanMessage混合内容块中的text；②含电话/邮箱的历史AIMessage.tool_calls.args，后跟对应ToolMessage。输入均为SDK支持的消息结构；如果不支持某种载体，应明确拒绝，不能原样发送。
- 最小复现：本轮`test_audit_wp09.py::test_text_carriers_redacted[mixed_blocks]`及`[tool_arguments]`。合成电话/邮箱经真实SDK序列化到MockTransport，两项均断言失败。证据redaction-mixed_blocks.json、redaction-tool_arguments.json及audit-extra.xml。
- 实际影响：content为list时完全绕过redact；tool_calls.function.arguments不属于content也未处理。启用真实transport时可能外发应脱敏文本。**本轮未发送真实个人信息，反例没有网络调用**。
- 最小修复：在付费预留/transport之前，明确支持的消息载体，统一对允许出站的文本叶子脱敏；不支持的内容块安全拒绝。处理工具arguments时保持合法JSON与调用ID/角色/结构，不破坏工具对应关系；不通过禁用正常字符串工具参数掩盖。不得改变可信上下文/业务记录内容来迁就脱敏。
- 定点复核：保留两原反例；增加普通content、混合text块、结构化arguments等价语义与调用ID/JSON保持断言，用MockTransport检查真正请求体。必要回归多工具/结构JSON与既有秘密日志检查即可，不要求付费重跑。

### ISSUE-002 — P2：预算锁等待后未重验deadline即发送

- 文件：`backend/app/infrastructure/model_gateway.py:113`至124；跨进程阻塞点为model_budget.py的exclusive/reserve。检查发生在reserve之前；收到响应后才再次判断超时。
- 触发：turn仅余0.3秒，另一个真实进程持有本次隔离预算文件锁1.6秒。网关实际等待约**2.094秒**后仍调用transport，再报MODEL_TURN_TIMEOUT。
- 最小复现：`test_audit_wp09.py::test_deadline_after_real_budget_lock`。只将网关已用时间设置为119.7秒；文件锁由实际独立PID6300持有，不替换预算/锁/发送代码。MockTransport观察到期限后新请求1次；deadline-budget-lock.json、audit-completion.xml保留失败。
- 实际影响：过期turn仍能产生本可避免的新模型请求及费用；后置拒绝回答不能撤销已发送请求。共享5元预留仍有效，**没有证实总费用越限**。这不同于已在执行中的同步HTTP无法硬抢占，不要求实时调度重构。
- 最小修复：获得可能阻塞的预算预留后、真正发送前重新核对期限；已过期安全终止并按明确策略保留/终结预留记录，不清零账本、不发送、不重试。可以在请求超时配置中考虑剩余期限，但不要求扩建任务框架。
- 定点复核：原真实锁等待反例应0个transport请求；核对账本终态/预留策略、正常请求、429有限重试与已发请求迟到拒绝。无需重跑整个328项或真实付费请求。

## 6. B类：非阻断建议与未验证

- N01：混合模型的cosine分数目前直接合并；后续若宣称质量改善或扩大多模型使用，应在同一冻结评测中比较排序分布/校准。现有排序确定、无跨维度计算错误，不因未做新质量评测否决本包。
- N02：将本轮新反例按整改范围纳入常规回归；Linux BGE从示例转支持运行方式时补动态验证。当前不要求修复尚未承诺的容器能力。
- 本轮引用原真实DeepSeek证据，无新增provider调用；未读取账单。没有验证其他型号、全部strict参数、真实维修语义、正式Agent/图/UI或生产恢复。
- 真实资料NOT_MET及WP10/真实效果验收前截止保留。SSE首次根因未确认、Compose历史启动底层原因未确证、owner粗锁/性能/监控/清理、旧receipt/旧比较复核等既有边界不变。

## 7. 接受建议及停止

**CHANGES_REQUIRED，暂不建议接受WP09。** A401/A403/E10与Windows本地BGE技术证据可保留，无需因两个缺陷推倒重验全部链路。后续只修两项网关出站边界并定点复核；通过后再由用户决定限定范围接受，排除Linux BGE未验证部署、其他型号和后续包。

结束保护核对见protection-final.json：3670项被审文件、63项旧项目、Git index及共享真实预算账本均未变；STATUS、接受记录、历史证据/迁移未修改。无提交/推送、无付费调用、未进入WP10。完成本报告后停止，等待用户决定。

## 附录：本轮实际命令与时间

所有命令cwd均为`E:/Work/xiutu-v5`；连接凭据由run.py静默注入，以下不包含连接串。

### create

```text
E:\Work\xiutu-v5\.venv\Scripts\python.exe -B scripts/probes/prepare_database.py --name xiutu_test_wp09review_3b4adbfa5300
```

2026-09-19T00:41:05.885693+08:00 → 2026-09-19T00:41:06.582757+08:00；exit=0。原始输出：`create.txt`。

### migrate

```text
E:\Work\xiutu-v5\.venv\Scripts\python.exe -B -m alembic upgrade head
```

2026-09-19T00:41:06.676437+08:00 → 2026-09-19T00:41:07.886511+08:00；exit=0。原始输出：`migrate.txt`。

### targeted

```text
E:\Work\xiutu-v5\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider tests/unit/test_wp09_contracts.py tests/integration/test_wp09_models.py -q -s --basetemp .test-runs/wp09-review-targeted-90d2 --junitxml=docs/implementation/phase-04/evidence/wp-09-review-r1/targeted.xml
```

2026-09-19T00:41:07.981782+08:00 → 2026-09-19T00:42:53.208755+08:00；exit=0。原始输出：`targeted.txt`。

### audit-extra

```text
E:\Work\xiutu-v5\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider docs/implementation/phase-04/evidence/wp-09-review-r1/test_audit_wp09.py -q -s --basetemp .test-runs/wp09-review-extra-6f18 --junitxml=docs/implementation/phase-04/evidence/wp-09-review-r1/audit-extra.xml
```

2026-09-19T00:43:54.982244+08:00 → 2026-09-19T00:44:02.727198+08:00；exit=1。原始输出：`audit-extra.txt`。

### audit-completion

```text
E:\Work\xiutu-v5\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider docs/implementation/phase-04/evidence/wp-09-review-r1/test_audit_wp09.py::test_mixed_dimensions_and_downgrade_guard docs/implementation/phase-04/evidence/wp-09-review-r1/test_audit_wp09.py::test_deadline_after_real_budget_lock -q -s --basetemp .test-runs/wp09-review-completion-e21a --junitxml=docs/implementation/phase-04/evidence/wp-09-review-r1/audit-completion.xml
```

2026-09-19T00:45:12.126886+08:00 → 2026-09-19T00:45:45.275836+08:00；exit=1。原始输出：`audit-completion.txt`。

