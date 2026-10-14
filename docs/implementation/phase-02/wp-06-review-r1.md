# WP-06 r1 集中审核报告

结论：**REVIEW_PASS（仅WP-06限定技术范围）**。D213 PASS，D214 PASS。审核完成：2026-09-18T16:59:06.173581+08:00。

建议用户可接受证据快照、人工规格审核、精确比较和撤销门禁的技术交付，并保留本文列明限制。技术审核通过不等于用户ACCEPTED，不接受整个P2阶段，不授权WP-07。

**流程披露：本任务参与了WP-06实施，本轮在同一任务切换为审核角色。不是不同任务/窗口的独立审核。** 本轮只读审查实现，新增审核脚本、原始证据和本报告；没有修业务代码、STATUS、迁移、接受记录或原证据。

## 1. 依据、输入基准和保护

已检查E:/AGENTS.md、E:/Work/AGENTS.md、项目根及项目目录内AGENTS.md，未发现适用文件。读取STATUS、WP05接受记录、WP06契约/结果、README/API、P2实施/验收清单、总指南4.3、8.2/8.4/8.5和WP06相关契约；用实际源码和测试判断，未将执行者总结直接当审核结论。

- Git根E:/Work/xiutu-v5，分支main，HEAD不存在；单次safe.directory，无全局设置修改。完整暂存/未暂存diff、未跟踪清单在baseline.json，不能因无HEAD跳过新增交付。
- 执行者delivery-hashes.json **1663项全部匹配**；full-code-hashes.json **99项全部匹配**；执行者protection-final中1459项历史/迁移/门禁保护全部匹配；交付清单本身SHA与封存声明匹配。完整232项之后没有未验证实现改动。
- 开始审核另固定所有交付及执行证据文件（含忽略的子进程日志），共1881项；开始/结束逐项一致。baseline.json、protection-final.json可复核。
- Git index SHA256 `c451d6e78b8f29fc818002923a19fb1a888139ced20679ad545f75e9692a9ec6`，结束相同。旧项目扩展63项哈希匹配。0001—0006迁移、原接受记录、STATUS、执行者原日志均未改变。
- 当前进程实际导入项目backend源码，路径/SHA及数据库内省见runtime-facts.json；没有误用旧editable副本。

## 2. 本轮环境与执行结果

Docker Server29.4.0可达；xiutu-v5-postgres-1 running，Compose project=xiutu-v5/service=postgres，127.0.0.1:5433映射5432。镜像sha256:00ba258a66dac104fd5171074a0084462a64a1369d8513f3d0a634e2f24d15bc。只读归属证据environment.json。复用既有服务，不重建/删除容器卷，不停止未知进程。

新审核库`xiutu_test_wp06review_6bf850d6049f4847b916`，升级至0006_evidence_specs；PostgreSQL16.14/vector0.8.2。迁移回归按原测试在另一个新唯一库演练。凭据静默加载本项目受保护文件，未读取旧.env；命令/证据不含连接密码。库保留供复核。

cwd均E:/Work/xiutu-v5；完整入口和补充用例各运行一次，新临时目录互不复用；两者部分执行时间重叠，合成owner/存储/进程互相隔离，共用本轮审核库。所有HTTP/worker均为用例自己创建并结束的进程。没有新建第二venv、前端构建、WP05模型选型或留出质量评测；本地E5仅复用回归/演示所需的索引与查询。

| 本轮运行 | 通过 | 失败/错误/跳过 | 秒 |
|---|---|---|---|
| full | 232 | 0/0/0 | 455.004 |
| audit-targeted | 18 | 0/0/0 | 104.034 |

完整入口1条既有Starlette/AnyIO弃用警告；新增18项无警告。没有失败后循环重跑。full.xml、audit-targeted.xml和原始txt分别保存结果，test-summary.json含统计及选定用例。

| label | 实际命令（无敏感URL） | exit | 开始—结束 |
|---|---|---|---|
| create | `E:\Work\xiutu-v5\.venv\Scripts\python.exe -B scripts/probes/prepare_database.py --name xiutu_test_wp06review_6bf850d6049f4847b916` | 0 | 2026-09-18T16:48:42.202228+08:00 — 2026-09-18T16:48:42.868079+08:00 |
| migrate | `E:\Work\xiutu-v5\.venv\Scripts\python.exe -B -m alembic upgrade head` | 0 | 2026-09-18T16:48:42.951563+08:00 — 2026-09-18T16:48:44.045020+08:00 |
| full | `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/test.ps1` | 0 | 2026-09-18T16:48:44.121786+08:00 — 2026-09-18T16:56:22.271657+08:00 |
| audit-targeted | `E:\Work\xiutu-v5\.venv\Scripts\python.exe -B -m pytest docs/implementation/phase-02/evidence/wp-06-review-r1/test_audit.py -q -s -p no:cacheprovider --basetemp E:/Work/xiutu-v5/.test-runs/wp06-review-extra-7b17a32c42774b4b94e6 --junitxml=E:/Work/xiutu-v5/docs/implementation/phase-02/evidence/wp-06-review-r1/audit-targeted.xml` | 0 | 2026-09-18T16:52:56.977580+08:00 — 2026-09-18T16:54:42.736629+08:00 |
| runtime-inspection | `E:\Work\xiutu-v5\.venv\Scripts\python.exe -B docs/implementation/phase-02/evidence/wp-06-review-r1/runtime_facts.py` | 0 | 2026-09-18T16:54:15.281908+08:00 — 2026-09-18T16:54:16.524720+08:00 |

runner仅注入隔离URL、审核输出目录、PYTHONPATH并原样调用子命令，不过滤用例或改变断言；full以PYTEST_ADDOPTS指定正斜杠绝对JUnit路径。每个label.json含cwd/实际命令/时间/退出码。子进程原日志副本和哈希见child-log-manifest.json。

## 3. D213：规格与精确比较 — PASS

代码：domain/measurements.py:21起、tools/measurement.py:24—70、evidence_service.py:225—382、0006_evidence_specs.py。

- 请求数值必须为受限十进制字符串；NaN/Inf/bool/JSON浮点拒绝。lower/upper使用无缩放NUMERIC，definition/result JSON数值为字符串，编码不经float。审核补充HTTP写入`1.00000000000000000000000000001`，真实PG读取上下界保持相同Decimal，比较为within_range，证据gate-history-precision.json及runtime-facts.json。
- 转换比例/偏移由精确常数构成；Decimal输入转精确Fraction比较。展示只在局部100位上下文生成，converted_exact明确循环小数；判定不读取展示舍入值。独立预期使用已知恒等式33°F=5/9°C、32°F=0°C、-40°F=-40°C，固定上下界小数直接写明预期，不用实现计算测试预期。7项补充覆盖5/9两侧、上下无界、开区间和等值闭区间；number-*.json保留输入/预期/输出。
- 本轮完整入口的28个原比较器用例覆盖开闭边界、单边、相等/倒置/无意义范围、单位白名单、压力/电压/电阻、缺值/工况、quantity/unit错误及非法数值。非法输入422、合法但不匹配返回未判定，缺值不填0。
- 真实HTTP先pending，approved后才可能within_range；rejected/revoked均spec_not_approved，来源失效evidence_invalid；unknown不能批准，mismatch不进入manifest。审核补充重新批准规格后旧比较仍needs_review，不能恢复成有效结果。
- supersedes检查同case/component/quantity，并用唯一后继及root/version约束，正文不可变；新版本pending，不改旧比较definition。本轮补充跨case supersedes409。审核人/时间/意见保留追加历史。

within_range仅表示该输入满足该结构化规格，不表示部件正常或维修结论。全部端到端规格为显著标记的合成测试值，不是真实维修专业真值。

## 4. D214：冻结范围、引用、撤销 — PASS

| 检查 | 代码与本轮证据 | 结论 |
|---|---|---|
| 服务端冻结 | CaseService.create:43起先owner锁再幂等与freeze_manifest；evidence_scope.py:38冻结owner/profile/version/ready index/epoch；完整HTTP演示旧空manifest拒绝、新资料不扩范围 | PASS |
| 固定索引与当前资格 | retrieval/service.py:19/36及推理后重查；source:109重查epoch/qualification/索引关系；演示重建后仍查询旧合法index、撤销后搜索409 | PASS |
| 引用真实关联 | bind:112校验真实chunk/version/index、Unicode切片；生成SHA/locator，区分evidence与chunk ID；完整伪quote/错index/越权，补充中文+emoji码点定位 | PASS |
| 不可变与历史 | 冻结迁移159起触发器禁止正文UPDATE/DELETE、needs_review单向；真实SQL修改quote/规格值被拒绝，原文仍授权读取；4表触发器内省与ORM一致 | PASS |
| 审核失效 | document_service.py:305先owner锁，decision/scope/source/license实变增epoch，与invalidate_source同事务；decision/scope完整用例、source/license补充各增1并阻断；重新批准不清旧复核 | PASS |
| 幂等历史与后续使用 | 审核补充撤销后原key仍返回原201/响应；GET比较current_validity=false，新key比较evidence_invalid，门禁拒绝 | PASS |
| 门禁关联 | validate_references:384查case owner、逐证据case与current validity、spec.evidence_id属于传入证据且已审核；补充其他case证据、其他case规格、其他owner、无证据均阻断 | PASS |
| 测试隔离 | Settings.profile_boundary限定synthetic必须test模式+xiutu_test库，公开DTO无profile/formal覆盖参数；默认formal门禁拒绝合成；原正式资格回归通过 | PASS |

普通引用存在没有被报告成重要规格或语义支持已验证。门禁要求调用者明确提供重要spec_ids；当前验证它们与证据/case的关系和批准状态，不能推断自然语言声明需要什么规格或证明quote支持该声明。返回report_implemented=false/semantic_support_verified=false，正式报告流程仍未实现。

### 撤销并发：补足确定顺序证据

原测试test_revocation_serializes_real_requests观察两个真实HTTP数据库连接等待owner advisory锁，能证明竞争和已发生顺序的安全性；**单次随机调度不能证明两个顺序全部覆盖**，本报告不这样引用旧结果。

审核新增test_ordered_revocation：对bind、compare、review、case、spec各运行use→revoke和revoke→use，共10项。持有真实PG owner锁，先启动第一个请求并观察它在pg_stat_activity/pg_blocking_pids等待，再启动第二个并观察两个等待连接，然后释放锁；保存query_start/数据库observed_at/PID/blockers及HTTP结果。通过明确结果断言确认实际顺序，不以线程启动顺序代替证明。

- 使用先行：绑定201、比较201 within_range、规格审核200、case201有manifest、规格创建201；随后撤销导致新记录失效/needs_review，比较历史仍可读但不可授权。
- 撤销先行：绑定/规格审核/规格创建409；比较201 evidence_invalid；case201但manifest=[]。
- 两组各5个ordered-*.json均记录先1个、后2个PG等待连接；无死锁或超时。序列化与事务提交结果一致。

资料使用的授权线性化点是owner锁保护事务；冻结另外锁版本行与active切换串行化。检索推理不持长事务，输出前重新检查epoch/资格，返回片段仍须经bind再次校验；不能把检索结果当成永不撤销的授权。

## 5. 本轮演示、回归与引用旧证据的区别

- **本轮实测**：完整232项一次；其中test_demo_evidence_and_measurement实际启动HTTP/独立worker，上传→解析→审核→真实本地E5索引→新会话冻结→检索→绑定/原文→规格审核→范围内/超限/缺工况→撤销后历史与新使用分离。复用该用例本轮demo-*.json，不再重复CLI执行同等链路。
- **本轮额外实测**：18项审核专用反例，不改被审测试；7数值独立预期+1综合HTTP/精确存储/门禁/epoch+10固定顺序并发。
- **受影响回归**：完整入口含认证/CSRF/所有权/幂等、迁移health、真实索引、租约三个发布窗口、旧token/断锁/取消、PG/vector、跨进程checkpoint和本地MCP；以full.xml为准，未运行付费模型。
- SSE心跳/认证过期/跨owner本轮17.188秒通过，**本轮未复现，首次根因未确认**；不能称为已修复或确定是环境偶发。
- **执行者旧证据只引用历史**：原232完整、39定点、CLI1通过用于比对实现和覆盖；不加到本轮通过数，也不冒称另一审核窗口验证。WP05评测和模型选型不重做、不重新接受。

## 6. 问题与建议

### A. 必须整改

本轮未发现需要阻断WP-06限定技术交付的具体实现缺陷；无新增必须整改ISSUE。没有现场修改实现以换取测试通过。

### B. 非阻断建议

- N01 / P3：`tests/integration/test_evidence_measurement.py:285`附近的并发测试使用随机竞争。现有实现本轮已通过确定双顺序验证，建议后续按需要将审核专用10项确定顺序用例整理进常规回归，减少以后只保留随机证据的歧义。本包不以此为接受前置。
- N02 / P3：`backend/app/services/evidence_scope.py:20`为owner级粗锁。当前是正确性方案，未发现本包死锁或功能阻塞。以后有规模依据再增加锁等待监控和评估粒度，不要求现在重构。
- N03 / 后续集成边界：`backend/app/services/evidence_service.py:384`的门禁不接收待发布自然语言声明，不能自动判定哪些重要规格被调用者遗漏。未来工具/报告接入时应从结构化动作收集必需spec_ids并调用门禁；不能将allowed扩展成语义支持/正式报告发布授权。当前契约已明确，非本包新增功能要求。

## 7. 未验证、保留限制和停止点

真实资料门槛NOT_MET，来源/许可、精确车型/发动机适配、正式规格/电路/拆装/复核章节与缺图最迟WP-10/真实效果验收前补齐；本轮不证明真实维修数值或诊断效果。E10 NOT_VERIFIED，另行授权模型/范围/预算后最迟WP-09验证，本地E5不替代它。

不含正式诊断图、LLM支持关系、报告生成/生产发布、前端、生产恢复、规模性能/清理/监控验收；固定384维、SSE及既有待办保留。未重测第二环境或无变前端，不因这些不在范围内项目判BLOCKED。

建议限定接受本包技术范围；用户仍拥有接受决定权。STATUS保持IMPLEMENTED_NOT_ACCEPTED，未新增接受记录，不提交/推送/付费调用。完成审核后停止，不推进WP-07，不接受整个P2。
