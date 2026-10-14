# 诊断闭环切片：候选修复上下文定点整改

记录时间：2026-09-21 00:53（Asia/Shanghai）。**切片仍为 `BLOCKED`。**真实初始 DeepSeek turn 本轮已发布唯一、有出处的当前检查；隔离浏览器保存一条合成观察后，真实续轮选择了保守的 `conclude_area`，服务端发布 `unknown` 区域卡，未发布第二项当前检查。本轮因此不能称为真实模型两步闭环成功，不自行审核或接受，也不启动 WP-13。

## 依据、差异和免费验证

操作者受限文件 `.test-runs/diag-slice-real2-c7af8164/proposal-diagnostic.private.jsonl` 经只读有限提取，确认此前真实首轮：首次候选 `propose_step`、schema 有效、仅 `INTERPRETATION_UNCERTAIN:interpretation` 一项业务问题；一次修复为 schema 有效的 `need_input`。历史候选原文和引用摘录未复制到本报告。`runner.py` 原修复请求只有原始对话与 `issues`，不含被拒候选，因此模型无法直接保留已通过字段。现于 [runner.py](../../../backend/app/agents/runner.py) 保存完整结构化候选，在一次修复请求中仅附被拒候选及有限 `code/path`，明确无依据的 `interpretation` 应为空数组、其余有据字段保留；schema 失败时候选为 `null`。消息仍先经网关现有复制、载体校验和出站脱敏，再预留与发送。没有自动删字段、放宽 [ProposalService](../../../backend/app/services/proposal_service.py) 或 [interpretation 门禁](../../../backend/app/validators/proposal.py)，修复后的整个候选仍重新验证。一次修复、四次模型请求及 120 秒限制均未改。

新增 [集成反例](../../../tests/integration/test_wp11_candidate_diagnostics_integration.py) 用真实隔离 PostgreSQL、原 ProposalService、SDK MockTransport 检查实际第三次出站请求：有据候选仅带非空解释时先拒，清空后可发布；继续带解释、另一个字段失效、修复返回 `need_input` 或 schema 错误均不能发布。候选中的合成邮箱在出站修复上下文被替换为 `[EMAIL]`，原候选对象保持不变；私有阶段诊断和公开 run/SSE 不含该值。原 `need_input`、初始 schema 失败及正常首轮路径也覆盖。所有测试只用合成数据，未触及真实账本或付费接口。

定点命令与版本：新建 `xiutu_test_diagrepair_932569ae`（`prepare_database.py` exit 0、Alembic exit 0）；首次 `pytest tests/integration/test_wp11_candidate_diagnostics_integration.py -q` **7 passed / exit 0**。随后只增加隐私和修复 `need_input`/schema 反例：最终测试文件先运行 `-k interpretation` **5 passed / exit 0**，再运行 `-k 'not interpretation'` **4 passed / exit 0**，两个集合互斥；`ruff check backend/app/agents/runner.py tests/integration/test_wp11_candidate_diagnostics_integration.py` exit **0**。原始 XML/日志分列于受限 `.test-runs/diagrepair_932569ae/`，不把首轮 7 项当最终测试字节版本的整组重跑。最终 `runner.py` SHA-256 `04BADD429171E23B7240D261B99AB1E91ECFB9E3C65F8CCED98945C20E4C910A`，集成测试 `D99DD1FF76B656C03A1DB834ED31A76217E72E586F1BFDC3884821190CB91566`；live 测试未改，SHA-256 `BADA9B22074DC92F774A7E9040AB3D5517DCD40C2DDB42067D2B612332D8565F`。此前完整回归证据属于旧版本，本轮没有重跑全仓。

## 唯一真实首轮、浏览器观察与续轮

在另一全新隔离库 `xiutu_test_diagrepair_live_416a9bd4`，迁移及已有 LangGraph checkpoint 初始化成功；真实本地 BGE-M3 1024 维索引、冻结 manifest、独立只读业务 MCP 均由原 live 探针准备。运行 `pytest tests/live/test_diagnosis_slice.py::test_one_bounded_synthetic_turn -q -s`，`DIAGNOSIS_SLICE_LIVE=1`，**exit 0**：`waiting_input`，`publish` 仅 1 条，有 6 个属于冻结资料的引用，3 次模型请求、4 次工具尝试。独立进程随后读回同一步骤、revision 1，publication 仍为 1。资料是 `synthetic=true, formal_usable=false` 的隔离台架样本，不代表 DKVB 实车。

为避免准备时间计入续轮期限，先建立了 revision 2 的只读 MCP 授权并验证 health，再用本轮专属 Chrome profile 的实际页面选择服务端给出的选项，点击“保存观察并启动下一轮”。浏览器显示保存成功；数据库有 1 条观察、revision 2、一个 child run。对该 child 执行一次真实 worker，`run-continuation.py` **exit 1（业务验收断言）**：模型请求 2 次、工具尝试 4 次，run 为 `succeeded`，publication 1 条但节点为 `area_close`。受限诊断只显示首次 `conclude_area`、schema 有效、`needs_input` disposition、0 个校验 issue；服务端生成 `unknown` 区域卡。独立数据库读取见原步骤 `completed`、观察 1 条、case revision 3 / `needs_review`、无当前待答步骤；这并非有出处的第二项检查。没有再次创建首轮或付费续轮，也没有用夹具补发布。浏览器刷新后的状态检查 exit 0：已保存观察仍显示、当前无待答检查、`needs_review` 可见。

本轮隔离浏览器首次截图刷新命令在已满足页面状态断言后于 `Page.captureScreenshot` 超时（exit 1），原日志保留；只针对截图可用性改私有探针后，页面状态只读复核 exit 0。原提交前/后截图保存在受限目录。此前浏览器辅助令牌页被浏览器策略阻断，临时令牌文件与传递进程已删除，剪贴板已清空；最终浏览器证明使用独立 Chrome profile。所有受限候选 trace、浏览器截图、测试凭据和连接信息均只留在 `.test-runs/diagrepair_live_416a9bd4/`，由操作者在后续定位结束后负责清理；公开只保存[脱敏汇总](evidence/diagnosis-slice-repair-r1/summary.json)。

原共享 v2 账本延续计量，21→26 条调用；保守累计预留 ¥2.839008→¥3.734104，新增 **¥0.895096**（首轮 ¥0.529504、续轮 ¥0.365592）。五次均有 usage，按本地已核价参数的 usage 估算合计 **¥0.080946**。预留及估算均不是平台账单，平台扣款未核实。原账本没有重置或复制；没有恢复累计 ¥5 拒绝上限，每 turn 四请求、120 秒及其他发送前门禁保留。

本轮仅改变 [runner.py](../../../backend/app/agents/runner.py)、上述集成测试，新增本报告和脱敏汇总，并更新 STATUS 的切片进展。原资料、WP-10 门禁、历史报告/证据、接受记录、迁移、5180/5196 用户实例及 Git index 均未改；Git index SHA-256 仍为 `C451D6E78B8F29FC818002923A19FB1A888139CED20679AD545F75E9692A9EC6`。本轮拥有的 API、Vite、MCP 和浏览器进程已停止；检查时 5180/5196 均未监听，本轮未操作或重启它们。

停止点：修复上下文缺失已有免费正反例及一次真实首轮成功证据；真实续轮选择保守区域收尾，**第二项检查未发布**。下一项应先免费核对已保存观察与现有合成来源是否足以支持另一项检查，以及续轮选择 `conclude_area` 的上下文和规则，再决定是否实施有限调整；不得由本报告推断应强制模型生成步骤。切片保持 `BLOCKED`，真实资料 `NOT_MET`、正式维修效果、生产恢复、历史旧 worker 首发根因等限制继续保留。
