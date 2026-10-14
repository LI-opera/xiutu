# 可体验诊断闭环切片结果（WP-13 前）

记录时间：2026-09-20 22:43（Asia/Shanghai）。**结论：BLOCKED，未交付真实模型闭环，不申请接受。** WP-12 已按其独立接受记录限定接受；本切片没有改变该范围，也没有启动 WP-13—17。

## 实际交付和代码范围

先核对了 WP-12 RECOVERY-001 r2 的源码、测试、报告和封存证据：0 项不匹配；Git index SHA-256 写前后均为 `C451D6E78B8F29FC818002923A19FB1A888139CED20679AD545F75E9692A9EC6`。随后新增[切片契约](diagnosis-slice-contract.md)和[WP-12 接受记录](wp-12-acceptance.md)，STATUS 将 WP-12 记为限定接受。此后实施的切片与 WP-12 接受证据分开。

本切片新增 `frontend/src/diagnosis-slice.tsx`、`backend/app/diagnosis_slice.py`、`tests/fixtures/diagnosis-slice/bench.md`、`tests/integration/test_diagnosis_slice.py`、`tests/live/test_diagnosis_slice.py` 和 `scripts/probes/seed_diagnosis_slice.py`。直接修改 `frontend/src/main.tsx`、`frontend/src/api.ts`、`backend/app/services/diagnosis_service.py`，以及测试夹具 `tests/integration/test_document_ingest.py`。页面复用既有登录、case、diagnosis run、证据、观察和幂等 API；`GET diagnosis` 只读补充服务端公布的 `required_conditions` 和最近任务错误，供刷新后呈现真实状态。测试壳仅允许独立的 `xiutu_test_diag_slice_*` 数据库与 synthetic profile；没有另建诊断引擎或变更 WP-10 校验。`tests/fixtures/diagnosis-slice/bench.md` 是新编的合成台架样本，`formal_usable=false`，不是 DKVB 原文或真实维修资料。原有 5180/5196、它们的数据库、storage、构建和访问身份未操作。

页面已能在隔离实例选择冻结资料的会话、启动现有诊断任务、读取当前检查和已保存观察、打开被授权的证据原文、按已发布选项及工况提交观察，并在刷新后从数据库恢复状态。旧响应以 case/请求代次保护；错误与任务失败按服务端实际状态显示。没有正式报告、可信结论升级、观察以外的 WP-13 功能或预设下一检查。

## 免费验证、浏览器及失败记录

隔离库 `xiutu_test_diag_slice_f7ea5a058e8a` 的创建、迁移、checkpoint 和原相邻三项测试均退出 0。新接口用例首轮因新 fixture 缺测试所需句子而失败；补上**合成测试句子**后仅受影响用例 `1 passed`。BGE 免费预检首轮因旧 HTTP fixture 仍以 E5 启动而返回 503；改为通过既有服务以 BGE 设置查询同一冻结 manifest 后，受影响用例 `1 passed`。原失败日志 `slice.log`、`bge-free.log` 与修正日志 `slice-fix.log`、`bge-free-fix.log` 分开保留于 `.test-runs/diag-slice-f7ea5a058e8a4df79c176c59d05ad719/`；[非秘密摘要](evidence/diagnosis-slice/free-test-summary.json)记录隔离库和步骤退出码。

最终选择的三个直接相关后端实例（`tests/integration/test_wp11_graph.py::test_start_publish_wait_and_replay`、`tests/integration/test_wp12_turns.py::test_observation_atomic_idempotent_and_public_resume_closed`、`tests/integration/test_wp12_turns.py::test_two_saved_choices_drive_distinct_source_backed_checks`）在同库运行：`python -m pytest <这三个节点> -q`，`3 passed`、退出 0，原始 `final-targeted-corrected.log/xml` 保留。新增浏览器后端契约测试另在 `slice-fix.log/xml` 中为 `1 passed`。该次之前有一条写错 pytest 节点名的命令，退出 4、没有运行测试，见 `final-targeted.log`；不计作业务失败或通过。`ruff check --no-cache` 对受影响 Python 文件退出 0；前端 `npm run typecheck` 退出 0，`npm run build -- --outDir <隔离目录>` 退出 0，未覆盖 `frontend/dist`。这不是标准完整入口的当前版本回归。

浏览器经独立 `localhost:5202`（与用户的 `127.0.0.1` Cookie 主机隔离）访问独立库及构建。免费确定性夹具发布了一项明确标成“非 AI”的 P01 检查；页面读到实际 step、`engine=off` 工况和证据版本/定位，提交选项后数据库保存一条观察、revision 变为 2、生成后续 run。刷新仍显示相同观察和任务。由于人工检查与脚本准备已使该后续 run 超过 turn 截止时间，随后尝试免费续轮时 `MODEL_TURN_TIMEOUT`、无第二次 publication；`browser-continuation.log` 原样保留。页面再次刷新显示 `failed` 和该错误，未伪造下一检查。夹具只能证明已完成的观察事务及读取，不能代替真实模型续轮。

## 唯一一次真实模型 turn

免费阶段在隔离库以既有 BGE-M3 建立 1024 维索引，冻结 manifest 含一个合成资料版本，原 WP-10 服务校验一项来源可追溯的非数值候选通过；`free-preflight.json` 保留模型、索引及资料哈希，不复制正文。第一次启动真实探针在 MCP 就绪期间 `httpx.ConnectTimeout`，**未创建付费 turn、账本未变**；失败留于独立 `.test-runs/diag-slice-live-9e90ad921f4a4e1089409e3bdb66e3d1/`。有界修正仅允许启动探测处理该连接超时，不改授权或候选门禁。

第二个隔离库 `xiutu_test_diag_slice_fec9834700c0` 中只创建**一个**真实业务 turn：DeepSeek 经现有网关、一次真实只读业务 MCP 工具尝试及原提案校验。结果为 run `failed`、`DIAGNOSIS_PROPOSAL_NEEDS_INPUT`、publication **0**、当前 step **无**，测试验收入口退出 1。私有有限诊断只提取：首次 `propose_step` schema 有效，业务校验 `needs_input`；代码/路径为 `CONDITIONS_MISSING:prerequisites`、`LOCATION_UNCERTAIN:location`、`ACTION_SEMANTICS_UNCERTAIN:actions`、两个 `CHOICE_SEMANTICS_UNCERTAIN:input.choices`、`INTERPRETATION_UNCERTAIN:interpretation`。一次修复后的候选为 `need_input`，schema 有效，仍 `needs_input`。没有更改资料、植入候选答案或放宽 WP-10 门禁；失败后没有第二个付费 turn。

本 turn 模型请求 3 次、工具尝试 1 次，3 次请求均有 usage 状态 `reported`。原共享 5 元账本的累计**保守预留**由 ¥1.947480 增至 ¥2.329216，差额 ¥0.381736；调用计数 15→18。它和 usage 估算均不是平台账单，本次未核实平台实际扣款；不重置账本或推断仍可再运行一次完整 turn。公开[脱敏运行摘要](evidence/diagnosis-slice/live-run-summary-r2.json)仅给隔离库及退出码；私有 `live-summary.json`、有限候选诊断及原始日志留在受限 `.test-runs/diag-slice-live-fec9834700c04c3fac076469b130f5c9/`，后续清理由本机操作者决定，不进入文档或[交付哈希](evidence/diagnosis-slice/delivery-hashes.json)。价格资料来源为[DeepSeek 官方价格页](https://api-docs.deepseek.com/quick_start/pricing/)；固定保守预留与 usage 不保证平台实扣等于估算。

## 当前阻断、体验和停止点

真实模型未发布首项检查，故无法在授权的两个 turn 上限内验证“真实模型读取用户观察后发布第二项”。隔离浏览器可体验的是**已发布合成夹具检查→提交观察→刷新**，以及对失败 run 的真实呈现；不能将其称为 DeepSeek 闭环。当前修复方向应先免费分析上述结构化 issue 对应的来源与有界表达，而不是重试付费或放宽原门禁。此次未做该后续整改。

独立端口 5202 的进程经 PID、解释器路径和创建时间核对后已停止；用户 5180/5196 继续保持原状态。当前没有供用户持续访问的新版诊断页面，也未部署到用户实例。若将来继续，需要先解决真实候选依据及免费续轮超时演示时序，再做新一轮有界验证和审核。WP-13—17 仍 `NOT_STARTED`。真实资料 `NOT_MET`、DKVB 精确适配缺项、真实维修效果/生产恢复未验证、仅 `unknown` 区域卡和旧 worker 首次失败根因未确证均保留。

本任务也参与了 WP-12 实施、整改和审核，不能称不同任务独立审核。本报告是执行者结果，不写 `REVIEW_PASS` 或用户接受；待用户决定如何处理阻断。
