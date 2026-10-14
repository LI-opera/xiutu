# WP-00 独立审核 r1

审核工作包：WP-00。审核日期：2026-09-18（Asia/Shanghai）。结论：**REVIEW_PASS**。
建议用户接受 WP-00 的基线、备份恢复与资料清点交付；接受的范围不包含真实维修知识库完备性、真实模型/MCP 或 WP-01。技术审核通过不等于用户接受。STATUS 保持 IMPLEMENTED_NOT_ACCEPTED，WP-01—17 未开始。

## 1. 审核基准、读取范围与操作边界

- 旧根：`E:\Work\v4-double`，存在，非 Git 仓库；入口 `app/main.py` → `app/application.py:create_app`。首页确实返回 workbench.html，载入 workbench.js/workbench.css/final-aside.css/intake-layout.css。
- 新 Git 根：`E:\Work\xiutu-v5`，分支 main；HEAD 尚无提交，`rev-parse --verify HEAD` 返回128属预期，未跳过审核。
- 开始时32文件暂存为新增，未暂存 diff 为空，无既有未跟踪交付文件。无已有 review/remediation；本报告新建 r1，未覆盖。
- 完整读取用户指定总指南、阶段总表、P1实施说明及验收清单、STATUS、result、baseline、data-readiness、7行CSV、ADR；另读README/CHANGELOG、两个脚本、忽略/属性规则及相关 evidence。源资料按章节、标识和哈希抽查；所有暂存blob与工作区文件均纳入检查。
- E:\AGENTS.md、E:\Work\AGENTS.md、新旧项目根及排除环境/缓存后的嵌套发现均无适用AGENTS。首次普通沙箱 Git 查询因dubious ownership拒绝，后续仅使用进程参数 `-c safe.directory=E:/Work/xiutu-v5`，没有修改全局配置；所有审核Git命令使用 `--no-optional-locks`。
- 仅新建本报告、`evidence/review-r1/` 和新的隔离测试/恢复目录。未修复业务代码，未编辑执行结果/原证据，未修改STATUS，未stage/commit/push，未停止服务，未安装依赖，未发付费模型请求。

审核基准开始UTC：2026-09-17T17:52:36.140894+00:00；结束文件复核UTC：2026-09-17T17:56:59.381123+00:00（本地时间加8小时）。

索引 SHA256：`c451d6e78b8f29fc818002923a19fb1a888139ced20679ad545f75e9692a9ec6`，前后一致。

完整32文件大小/SHA256见 [baseline-before.json](evidence/review-r1/baseline-before.json)，结束核对见 [baseline-after.json](evidence/review-r1/baseline-after.json)。关键文件如下：

| 被审核文件（相对新根） | SHA256 |
| --- | --- |
| scripts/wp00_baseline.py | 79879aa4add37f6fa07b3a8c4dd15f9dd214f7673ac43ad21d9129ea5c0e7485 |
| scripts/wp00_backup.py | 460a89ad934f2fdc1e7c6c13a2d2ba365c1a33a8e4e37971f8f79ea931e1905c |
| .gitattributes | 1a857a1ce0dc521e7cf7948ca27e5734f72f5a4151753618975e7bbb227b8f5b |
| .gitignore | 6a1e8cca2a2f8a1b4ddd8bbc9fa0738c08c81273d139e74d65a7e501a6e1e616 |
| docs/implementation/STATUS.md | 4340f7978ef273635b499cf1aab83c8a13ff0fa7525160f5e6bfa6949edcf4cf |
| docs/implementation/phase-01/wp-00-result.md | 391e111160dc123054903ca34340f22afafa688bfb96625910ca160e17e56ce2 |
| docs/implementation/phase-01/source-manifest.csv | 37395425d22e73807bbf45bf12d125ef2411aeb4285d3aa29f6ed1cc1071e698 |
| docs/adr/0001-scope.md | f741233e4234a748194a1a15579dad4f93d619b37a381783233cc151faa706f3 |

原始 staged/unstaged diff 与索引条目保存为 `staged-before/after.txt`、`unstaged-before/after.txt`、`index-before/after.txt`。这些前后一致；status不同仅因新增审核未跟踪文件。32项原交付、原备份与原恢复文件没有审核期并行变化；没有结论需要因本次审核范围漂移重新验证。

## 2. 独立运行的命令与结果

### 2.1 测试真实性、隔离和旧项目保护

先逐行审查 wp00_baseline.py：`child` 不替换断言、不增skip标记、不选择子集；直接调用原 tests，禁cache/plugin autoload，返回 pytest 真实退出码。父进程返回子进程退出码，源码哈希变化另返回90，不会把失败改成成功。SQLite审计hook只允许本次run下的路径或内存库；网络hook阻断connect/getaddrinfo，socketpair例外要求调用帧来自标准库socket._fallback_socketpair及回环地址。它是针对当前测试的隔离措施，不是通用恶意代码沙箱。

旧tests中Settings明确注入tmp_path的数据库、资料、附件和日志；模型生成/HTTP/搜索使用替身。使用 -B 不写旧pycache；密钥设为空、网页搜索关闭。没有连接旧业务库。审查原config及测试调用位置后才执行：

```powershell
& 'E:\Work\v4-double\.venv\Scripts\python.exe' -B 'E:\Work\xiutu-v5\scripts\wp00_baseline.py' --old 'E:\Work\v4-double' --run 'E:\Work\xiutu-v5\.test-runs\wp00-review-r1-legacy' --evidence 'E:\Work\xiutu-v5\docs\implementation\phase-01\evidence\review-r1'
```

实际时间：2026-09-18 01:53:20—01:53:25；Python 3.12.10；退出0；**67 passed / 0 failed / 0 errors / 0 skipped / 1 warning**，pytest 4.63s。警告为Starlette引用AnyIO BlockingPortal的弃用别名。证据：本审核的 legacy-test-summary.json、legacy-pytest.txt、legacy-junit.xml。

独立解析3份JUnit：首次失败记录、执行者成功记录、本次审核记录均为同一组67个 classname/name；没有测试删减。首次socketpair误拦记录保留：17通过、50 setup errors、7 warnings、退出1，调用栈从AnyIO/asyncio到socketpair再到guard。当前修正只放行该标准库内部路径，非把异常吞掉。

旧初始53文件 before==after；当前63文件审核前后哈希一致。与最初53文件相比，仅阶段总表变更、P2—P6共10份计划新增，完全等于执行交付时已记录差异；与执行者最后63文件清单逐项一致。业务源码、测试、config.py、.env.example和依赖文件无其他变化。详见 [legacy-comparison.json](evidence/review-r1/legacy-comparison.json)。真实.env内容未列入原历史哈希清单，不能追溯证明其历史每字节不变；B02的PASS针对要求的源码/配置模板及本次不修改旧目录，不扩展该证据范围。

### 2.2 指定快照与独立恢复

审查 wp00_backup.py 后确认：源SQLite以mode=ro打开并调用Connection.backup；资料逐文件前/后/副本哈希核对，最多3次；末尾再核对文件集合/哈希，失败保留INCOMPLETE。恢复先验证清单/大小/哈希，使用全新目标，之后检查schema、行数和完整性。

实际备份 `E:\Work\xiutu-backups\phase-01-20260918-0115` 存在，manifest与原evidence完全相同；脚本SHA256与manifest记录一致。原恢复确为 `E:\Work\xiutu-backups\restore-20260918-0115`，实际验证文件及其restore字段与原evidence匹配。

本次独立执行：

```powershell
& 'E:\Work\v4-double\.venv\Scripts\python.exe' -B 'E:\Work\xiutu-v5\scripts\wp00_backup.py' restore --backup 'E:\Work\xiutu-backups\phase-01-20260918-0115' --output 'E:\Work\xiutu-backups\review-r1-restore-20260918-0155'
```

退出0，8文件恢复。审核另用独立sqlite3查询（不调用脚本inspect_db）在mode=ro&immutable=1下检查备份、原恢复、新恢复：三个integrity_check均为ok，sqlite_master的type/name/tbl_name/sql全量一致，行数如下：

| 表 | 备份清单 | 实际备份 | 原恢复 | 审核新恢复 |
| --- | --- | --- | --- | --- |
| attachments | 0 | 0 | 0 | 0 |
| audit_events | 741 | 741 | 741 | 741 |
| session_state | 42 | 42 | 42 | 42 |
| sessions | 88 | 88 | 88 | 88 |
| sqlite_sequence | 1 | 1 | 1 | 1 |

实际备份文件集合=清单8文件+manifest，无未清点载荷。8文件在备份、原恢复、新恢复的大小/SHA256全部相符；映射见 [restore-independent.json](evidence/review-r1/restore-independent.json)。两张已授权图分别位于三个目录下的：

- `supplemental/04-image-20260903222136740.png`
- `supplemental/05-image-20260903222223621.png`

PNG字节恢复成功；原稿绝对链接未改写，不能声称打开恢复稿就已自动修复链接。SQLite为同一历史一致快照，不与活跃源库当前行数强行比较。本次只读完整性/schema/行数/文件验证，**不是产品级服务运行恢复验证**。

### 2.3 防覆盖、篡改与Git检查

审核辅助程序：[review_checks.py](evidence/review-r1/review_checks.py)，实际用旧解释器 -B运行，退出0。它仅在全新 `.test-runs/wp00-review-r1-checks` 创建合成SQLite/资料/附件：

- 合成backup与restore退出0；已有backup目标再次备份退出1，目标哈希不变。
- 已有restore目标再次恢复退出1，目标哈希不变。
- 修改合成备份文件后恢复退出1，报Backup hash mismatch，目标未创建。
- 另保持字节数不变再次篡改，仍因SHA256不匹配退出1，目标未创建，见 same-size-tamper.json。

所有子进程精确参数/退出码/输出见 backup-commands.json；没有篡改任何原备份或原恢复。复跑必须改用新目录，不能重复覆盖本次工件。

32个暂存blob及对应工作文件均检查：无实际密钥值、SQLite/图片/PDF/ZIP载荷，无完整私人维修稿正文。密钥仅在内存比对，不打印；测试里的secret-test-key等是原测试伪值。完整文件类型/内容审查与scan共同使用，不把扩展名过滤单独当作泄密证明。

忽略测试覆盖.env/.env.local、.venv、node_modules、业务库、备份、日志、private/repair_docs/attachments、.test-runs、PDF；.env.example不被忽略。`git diff --cached --check`退出0。

.gitattributes第2行只对phase-01/evidence原始工件关闭空白检查；第3行对scripts/*.py保留原字节、允许CRLF和末尾空行，**没有关闭脚本其余空白检查**。实测README、ADR、backend普通代码的whitespace属性均unspecified，未广泛关闭普通代码/文档检查。该规则当前覆盖两份已执行脚本，可满足保存执行哈希的目的。

## 3. B01—B11逐项结论

| ID | 结论 | 实际审核证据与边界 |
| --- | --- | --- |
| B01 | PASS | 绝对路径/新Git根main/unborn HEAD实际核对；旧根非Git；旧入口及页面资产由代码核实，preflight路径与配置一致。 |
| B02 | PASS | 原53文件前后相同；当前63文件与执行最后清单相同，审核前后相同；仅已登记的阶段计划变化，业务代码/测试/配置模板无其他变更。 |
| B03 | PASS | 本审核全新临时目录实际67通过、退出0，JUnit测试身份完全一致；初次错误及修正证据保留，未修改断言或跳过测试。 |
| B04 | PASS | Connection.backup静态审查；实际历史快照清单/脚本哈希匹配；独立SQLite integrity/schema/5表行数核对通过。 |
| B05 | PASS | 全新审核恢复目录实测成功；备份/原恢复/新恢复8文件一致；两张图映射可恢复；合成负例拒绝覆盖与大小相同的篡改。 |
| B06 | PASS | 7行与7个实际文件SHA256全匹配；配置语料确为2Markdown、附件空；SRC-001缺2图属实，7类缺章/影响/待核对方明示。 |
| B07 | PASS | 全32项暂存与工作内容核对/秘密扫描/忽略规则/属性范围检查通过；索引未变，无私人载荷或业务库进入交付。 |
| B08 | PASS | 7项许可均unknown；SRC-002—005明确虚构，SRC-001及外部图保留未知；备份授权与公开许可分开，ADR没有宣称支持真实车型。 |
| B09 | PASS | 历史会话有创建前ABSENT检查及无覆盖初始化操作，preflight留同一结论；当前独立仓库32文件均为WP-00交付，无未知迁移/旧环境。过去不存在性不能靠当前文件系统重演，本项结合创建时操作记录评估。 |
| B10 | PASS | STATUS为WP-00 IMPLEMENTED_NOT_ACCEPTED；WP-01—17 NOT_STARTED；没有虚构review/acceptance或模型/MCP成功记录。 |
| B11 | PASS | 变更仅2个辅助脚本与文档/证据，无新生产诊断树/Agent/报告/业务接口，无WP-01安装或探针。 |

## 4. 问题清单与未验证项

未发现需要建立ISSUE的阻断或必须整改缺陷；本轮没有修复请求，因此无虚构ISSUE编号。首次隔离器错误已作为历史执行问题保留并由本次独立重跑验证解决。检索命令曾遇到Windows通配参数错误，随后使用明确路径/程序逐文件校验，未将失败输出作为PASS依据。

本次没有验证、也不应补做：DeepSeek真实调用、MCP传输、WP-01依赖兼容/安装复现、新服务启动及产品级恢复。原始维修文献真伪、权属/许可、车辆适配和图片技术内容仍未获专业审核。历史.env原始字节不在执行哈希范围，限制见上文；未发现本次业务配置被修改的证据。

## 5. 不阻塞本包、但影响后续的资料缺项

清点验收不等于资料可用于真实维修。SRC-001仅二次整理，原始PDF/版次/使用许可及原页支持关系缺失；EA888 Gen3是发动机系列而非精确发动机代码。对应车型故障定义、准确位置、测量条件、电路/针脚、数值标准、完整拆装/加注/匹配、完工复核条件仍须补齐；整理稿两张相对PNG仍缺失。SRC-002—005的虚构数据不能进入正式证据；已备份图没有因此获得公开分发许可。

由资料提供者与维修专业审核者确认；真实资料门槛仍为NOT_MET。后续依赖和模型契约按对应工作包验证，不将本报告扩展为真实诊断效果验收。用户明确接受或授权带缺项继续后，才能另行执行WP-01。

## 6. 审核结论和停止点

**REVIEW_PASS；建议用户接受WP-00，范围为已验证的基础交付和诚实的资料清点。** 不替用户写ACCEPTED。审核期间被审查32文件、63项旧源码/文档、暂存区、原备份/原恢复均未发生变化；本任务只新增审核报告/证据和隔离验证工件。审核完成即停止，不开始WP-01。
