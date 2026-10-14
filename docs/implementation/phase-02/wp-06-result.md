# WP-06 执行结果

状态：**IMPLEMENTED_NOT_ACCEPTED**。完成时间：2026-09-18T16:44:19.468124+08:00。仅实现本包，等待一次集中审核和用户决定；没有自行生成审核/接受结论，未进入WP-07。

## 现在能做什么

新会话会自动固定属于自己的合格资料版本与索引。检索片段绑定为不可变证据后，可以查看原文位置、创建人工规格版本并审核；比较数值会检查单位、工况、来源和适配。资料撤销后历史仍可读，旧的合格结果明确标为需要复核，不能继续授权新使用。

这只是证据与数值比较技术能力。所有演示规格为合成值，不是维修标准；within_range不等于部件正常，不输出诊断、维修报告或前端。正式语料门槛仍NOT_MET。

## 基准与修改范围

以WP05 r1审核的1539项清单为基础，用WP05接受记录的README/STATUS两项授权后哈希替换；全部匹配。审核报告、36项封存工件及Git index匹配，WP05接受记录未改。本轮起始1577项文件完整清单、main无HEAD、暂存/未暂存/未跟踪状态见baseline.json。

新增：0006_evidence_specs迁移；domain/measurements.py；services/evidence_scope.py、evidence_service.py；tools/measurement.py；api/measurements.py；对应unit/integration测试；scripts/demo_measurement.py；契约/API/结果/证据。必要修改：ORM、health预期版本、main/OpenAPI，CaseRepository/CaseService冻结范围，DocumentService审核撤销同步标记，RetrievalService内部manifest参数；迁移回归、README/CHANGELOG/STATUS/tests说明。完整变更及哈希见protection-final.json、delivery-hashes.json。

无依赖新增，无模型选型/质量重评，无旧迁移/旧项目/接受记录/Git index修改。完整回归源码基准见full-code-hashes.json，之后无实现变化。旧项目63项、历史文件和index开始/结束保护核对见protection-final.json。

## 设计与兼容变化

- 0006接0005，新增case_evidence、measurement_specs、measurement_spec_reviews、measurement_comparisons，以及document_versions.authorization_epoch。快照正文由数据库触发器禁止UPDATE/DELETE；needs_review不可由true清回false。规格上下界为无缩放NUMERIC；JSON数值为十进制字符串。
- case create请求不变，corpus_manifest从服务端冻结；无资料仍[]，已有空manifest不回填。冻结版本/ready index/profile/epoch；新文档及索引不改旧manifest。case检索用独立路由，WP05通用搜索保留。
- quote按Unicode码点start/end切片校验，hash/locator由服务器生成；重复文本不同位置对应不同证据。chunk_id与evidence_id分离，旧源文件仍经owner授权读取。
- 规格正文不可修改，新版用supersedes_id、root/version追踪，不覆盖旧比较。先pending，人审批准且来源有效和车型matched才允许within_range。
- 同owner审核/冻结/绑定/规格审核/比较先取稳定事务advisory锁；撤销和使用在同事务边界串行化。先使用则随后标复核，先撤销则拒绝/未判定。资料decision/scope/source/license变化增epoch并同步标记相关证据/规格/比较与case；重新批准不清旧标记。索引worker仍用既有物理锁连接和租约流程，未重写队列。
- 比较器接受受限精确十进制字符串，Decimal解析与输出；内部用由Decimal精确构造的Fraction交叉比较温度等转换边界，避免循环小数显示舍入误判。摄氏/华氏含偏移，单位仅temperature/pressure/voltage/resistance白名单。上下界开闭和单边界明确，缺值不填0。
- 引用门禁为EvidenceService.validate_references；重新检查owner、冻结关系、当前资格、quote/hash/locator、规格版本/审核及适配。调用者需提供重要规格IDs；不推断自然语言语义支持。默认formal拒绝synthetic，report_implemented=false、semantic_support_verified=false；case.report_gate仍NOT_IMPLEMENTED，无假报告流程。

## D213 / D214 本次自测证据

| 验收点 | 本次实测 | 边界 |
|---|---|---|
| D213 | 28个比较器用例：精确边界、开闭/单边、C/F偏移、压力/电压/电阻转换、缺值、NaN/Inf/bool/float拒绝、quantity/unit/conditions错误；真实HTTP pending、approved、unknown/mismatch、撤销后的比较 | 合成规格，非真实维修人工真值 |
| D214 | 真实HTTP新case冻结、空manifest拒绝、越权/伪quote/错误index、旧索引重建仍定位、新资料不扩范围、不可变SQL触发器、规格版本/旧比较、撤销/重新批准仍阻断、重复文本offset | 没有资料范围更新/重启诊断图流程 |

五类并发：bind、compare、review、case、spec，与资料撤销形成双HTTP请求屏障；主事务持有实际owner advisory锁，pg_blocking_pids观察到两个独立连接等待，释放后核对结果和复核状态。原始证据revocation-race-*.json，含PID/wait事件/响应；不是仅启动线程即宣称成功。

数据库真实约束/触发器和NUMERIC类型见database-schema-facts.json。HTTP全链路及结构化门禁演示见demo-*.json、cli-demo-*.json；完整和定点JUnit见下。撤销GET历史保留源quote和locator，比较历史原结果不改，但current_validity=false/needs_review=true。

## 命令与结果

cwd均E:/Work/xiutu-v5。本轮唯一主测试库：xiutu_test_wp06_778a2527f03c40ccabf95b；迁移回归另建唯一库并保留。复用归属确认的xiutu-v5-postgres-1 loopback5433，未重建容器/删卷/停止未知服务。凭据由runner静默加载本项目文件，不读旧.env、不写入命令证据。

| 运行 | 通过 | 失败/错误/跳过 | 秒 |
|---|---|---|---|
| units | 28 | 0/0/0 | 0.10 |
| integration-first | 7 | 0/0/0 | 69.77 |
| targeted-final | 39 | 0/0/0 | 110.28 |
| full | 232 | 0/0/0 | 446.00 |

另实际运行demo_measurement.py：1通过（20.25秒），使用新的owner、测试存储和自身API/worker；不是空演示说明。完整入口只运行一次；232项通过、0失败/错误/跳过，1条已知Starlette/AnyIO弃用警告保存在full.txt。没有付费模型请求，live测试不在标准入口。

| label | 实际子命令（无敏感连接串） | 退出码 | 起止时间 |
|---|---|---|---|
| create | `E:\Work\xiutu-v5\.venv\Scripts\python.exe -B scripts/probes/prepare_database.py --name xiutu_test_wp06_778a2527f03c40ccabf95b` | 0 | 2026-09-18T16:21:44.593144+08:00 — 2026-09-18T16:21:45.203112+08:00 |
| database-facts | `E:\Work\xiutu-v5\.venv\Scripts\python.exe -B docs/implementation/phase-02/evidence/wp-06/database_facts.py` | 0 | 2026-09-18T16:36:25.729974+08:00 — 2026-09-18T16:36:26.435198+08:00 |
| database-introspection-final | `E:\Work\xiutu-v5\.venv\Scripts\python.exe -B docs/implementation/phase-02/evidence/wp-06/database_facts.py` | 0 | 2026-09-18T16:44:04.011624+08:00 — 2026-09-18T16:44:04.602584+08:00 |
| demo | `E:\Work\xiutu-v5\.venv\Scripts\python.exe -B scripts/demo_measurement.py` | 0 | 2026-09-18T16:31:46.136793+08:00 — 2026-09-18T16:32:08.413262+08:00 |
| format-final | `uv run --frozen ruff format backend/app/services/evidence_service.py backend/app/tools/measurement.py backend/app/api/measurements.py tests/integration/test_evidence_measurement.py` | 0 | 2026-09-18T16:31:45.712917+08:00 — 2026-09-18T16:31:45.830150+08:00 |
| format | `uv run --frozen ruff format backend/app/domain/measurements.py backend/app/tools backend/app/services/evidence_scope.py backend/app/services/evidence_service.py backend/app/api/measurements.py backend/app/retrieval/service.py backend/app/services/document_service.py backend/app/services/case_service.py backend/app/repositories/cases.py backend/app/main.py backend/app/api/openapi.py backend/app/infrastructure/orm.py tests/unit/test_measurement.py tests/integration/test_evidence_measurement.py tests/integration/test_migrations.py scripts/demo_measurement.py migrations/versions/0006_evidence_specs.py` | 0 | 2026-09-18T16:27:08.026930+08:00 — 2026-09-18T16:27:08.159947+08:00 |
| full | `pwsh -NoProfile -File scripts/test.ps1` | 0 | 2026-09-18T16:32:08.507917+08:00 — 2026-09-18T16:39:37.546156+08:00 |
| integration-first | `E:\Work\xiutu-v5\.venv\Scripts\python.exe -B -m pytest tests/integration/test_evidence_measurement.py -q -s -p no:cacheprovider --basetemp E:\Work\xiutu-v5\.test-runs\wp06-71e33c2b8649443782d03f6296f5592e/integration-first --junitxml=E:/Work/xiutu-v5/docs/implementation/phase-02/evidence/wp-06/integration-first.xml` | 0 | 2026-09-18T16:24:25.050877+08:00 — 2026-09-18T16:25:36.409360+08:00 |
| lint-final | `uv run --frozen ruff check backend tests migrations/versions/0006_evidence_specs.py scripts/demo_measurement.py` | 1 | 2026-09-18T16:27:53.469794+08:00 — 2026-09-18T16:27:53.602151+08:00 |
| lint-first | `uv run --frozen ruff check backend/app/domain/measurements.py backend/app/tools backend/app/services/evidence_scope.py backend/app/services/evidence_service.py backend/app/api/measurements.py tests/unit/test_measurement.py tests/integration/test_evidence_measurement.py scripts/demo_measurement.py migrations/versions/0006_evidence_specs.py --fix` | 1 | 2026-09-18T16:27:07.784492+08:00 — 2026-09-18T16:27:07.941199+08:00 |
| lint-fix | `uv run --frozen ruff check backend/app/services/case_service.py backend/app/services/document_service.py backend/app/services/evidence_service.py backend/app/tools/measurement.py backend/app/api/measurements.py tests/integration/test_evidence_measurement.py --select I --fix` | 0 | 2026-09-18T16:31:45.488260+08:00 — 2026-09-18T16:31:45.613711+08:00 |
| lint-imports | `uv run --frozen ruff check backend/app/domain/measurements.py backend/app/main.py backend/app/infrastructure/orm.py backend/app/api/measurements.py tests/integration/test_evidence_measurement.py --select I --fix` | 0 | 2026-09-18T16:27:53.257430+08:00 — 2026-09-18T16:27:53.381446+08:00 |
| lint-verified | `uv run --frozen ruff check backend tests migrations/versions/0006_evidence_specs.py scripts/demo_measurement.py` | 0 | 2026-09-18T16:31:45.922654+08:00 — 2026-09-18T16:31:46.039644+08:00 |
| migrate | `E:\Work\xiutu-v5\.venv\Scripts\python.exe -B -m alembic upgrade head` | 0 | 2026-09-18T16:21:45.289679+08:00 — 2026-09-18T16:21:46.394361+08:00 |
| openapi-export-final | `E:\Work\xiutu-v5\.venv\Scripts\python.exe -B docs/implementation/phase-02/evidence/wp-06/export_openapi.py` | 0 | 2026-09-18T16:44:02.065664+08:00 — 2026-09-18T16:44:03.936394+08:00 |
| openapi | `E:\Work\xiutu-v5\.venv\Scripts\python.exe -B docs/implementation/phase-02/evidence/wp-06/export_openapi.py` | 0 | 2026-09-18T16:33:17.665232+08:00 — 2026-09-18T16:33:19.564210+08:00 |
| targeted-final | `E:\Work\xiutu-v5\.venv\Scripts\python.exe -B -m pytest tests/unit/test_measurement.py tests/integration/test_evidence_measurement.py tests/integration/test_migrations.py -q -s -p no:cacheprovider --basetemp E:\Work\xiutu-v5\.test-runs\wp06-71e33c2b8649443782d03f6296f5592e/targeted-final --junitxml=E:/Work/xiutu-v5/docs/implementation/phase-02/evidence/wp-06/targeted-final.xml` | 0 | 2026-09-18T16:27:53.717667+08:00 — 2026-09-18T16:29:45.635262+08:00 |
| units | `E:\Work\xiutu-v5\.venv\Scripts\python.exe -B -m pytest tests/unit/test_measurement.py -q -p no:cacheprovider --junitxml=E:/Work/xiutu-v5/docs/implementation/phase-02/evidence/wp-06/units.xml` | 0 | 2026-09-18T16:24:07.239964+08:00 — 2026-09-18T16:24:08.781854+08:00 |

每个label.json/txt保留cwd/时间/命令/退出码，test-summary.json汇总JUnit，child-log-manifest.json保存本轮子进程日志原路径/哈希。静态检查初始exit1为新增文件单行格式/导入及fixture重定义问题；格式化、恢复fixture并明确本地fixture后lint-verified退出0。所有失败静态记录保留，不写成从未发生错误。证据整理脚本首次因Windows路径转义在执行前报SyntaxError，修正后退出0；OpenAPI/数据库内省另用不冲突文件名重新只读导出，见artifact-notes.json。定点测试和完整入口没有失败后循环重跑。

## 用户亲自验证

按README静默加载本项目凭据，创建全新xiutu_test_*库、设置DATABASE_URL/TEST_DATABASE_URL，运行alembic upgrade head至0006，使用既有固定本地E5文件。执行：

```powershell
Set-Location E:\Work\xiutu-v5
uv run --frozen python -B scripts/demo_measurement.py
```

CLI复用已安装的开发测试工具，实际HTTP链路：合成上传→解析→审核→索引→新会话冻结→检索→绑定与原文定位→创建/审核规格→within/outside/conditions_missing→撤销后历史可读、新使用被阻断。输出.test-runs/wp06-demo-唯一ID的JSON、JUnit及日志，只结束本次进程，不删除保留库。测试1..2 V/engine=off不是汽车维修规格；演示审批不代表专业确认。

## 尚未验证与待办

没有已知必须解决的本包自测失败，仍等待审核。未做真实维修真值/专业规格效果验收、规模/吞吐压测、第二环境、未变前端或WP05留出质量复评。owner级锁较粗，后续有规模依据再细化；无清理平台，索引/证据/历史保留。工况为受控字符串精确匹配，不支持任意工况表达式或自动规格抽取；缺单位/工况等绝不猜测。引用门禁不能替代自然语言支持关系或未来正式报告发布验证。

E10 NOT_VERIFIED，另行授权后最迟WP-09；真实资料NOT_MET（来源/许可、精确车型/发动机、正式规格/电路/拆装/复核/缺图）最迟WP-10/真实效果验收前。SSE首次超时根因未确认；本轮未复现，相关用例17.172秒通过，不能称历史问题已修复。固定384维和性能/监控/清理、上传配额/复杂PDF隔离等既有待办保留。P2技术链路不等于真实维修效果或阶段无条件通过。完成后停止，不实施WP-07。
