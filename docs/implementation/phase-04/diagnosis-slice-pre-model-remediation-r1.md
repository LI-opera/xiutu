# 诊断闭环切片：前模型 `HANDLER_FAILED` 定点整改与有界真实验证

记录时间：2026-09-21（Asia/Shanghai）。**前模型故障已定位并修正测试环境接线；完整真实闭环仍 BLOCKED。**本轮没有修改 WP-10 校验器、业务 worker/graph、资料或模型提示。只修正 `tests/live/test_diagnosis_slice.py`：在隔离库 Alembic 迁移之后、创建诊断 run 之前，显式调用已有 `scripts/setup_graph_checkpoint.py`，核对数据库仍是 `TEST_DATABASE_URL`，并将子进程输出保存在私有目录。LangGraph saver 的表不由 Alembic 自动安装；原探针遗漏此步。没有通过忽略异常、退回本地工具或跳过 fencing 解决问题。

## 根因和失败证据

原真实首轮保留于受限 `.test-runs/diag-slice-paid-a37c1b2e/`。只读核对显示：run/job 均 `failed`、graph phase `failed`、checkpoint_ref 空、`wp01_wp11.checkpoints` 表不存在；事件仅 `run.queued/run.started/run.failed`，publication 与工具审计行均为 0。**这些计数本身不足以断言故障阶段。**在同一隔离库新建免费合成 case，经相同 `Worker.once → DiagnosisGraph.execute → FencedPostgresSaver.get_tuple` 路径，禁止模型网络，操作者私有包装仅记录异常类型及代码位置：实际异常 `UndefinedTable`，最后业务帧 `backend/app/agents/checkpoint.py:75`；worker 将其收敛为 `HANDLER_FAILED`。原失败并非模型候选或 WP-10 语义门禁。私有记录为 `.test-runs/diag-slice-premodel-5e2b1c/missing-checkpoint-repro.json`；无异常消息、SQL 参数、资料正文或凭据进入公开证据。

对同一隔离库执行已有 checkpoint 初始化脚本后，以新的免费 case、相同 BGE/冻结 manifest/`remote_mcp` Settings、独立只读 MCP HTTP 服务和 worker/graph 路径复测；仅将模型 factory 替换为必定抛出 `MODEL_CALL_DISABLED` 的无网络网关。结果：MCP health 成功、真实远端工具尝试 4 次、测试网关被调用 1 次、run 以预期 `MODEL_CALL_DISABLED` 结束、publication 0。对应受限结果为 `.test-runs/diag-slice-premodel-5e2b1c/free-remote-result.json`。这证明原前模型窗口已经越过，不证明真实模型会给出合法检查。

## 免费测试及代码基准

原隔离库的免费复现命令为 `.venv/Scripts/python.exe -B <私有 repro.py>`，exit **0**，其中 worker 业务状态为 `HANDLER_FAILED`，捕获 `UndefinedTable`；原始日志单独保留。`scripts/setup_graph_checkpoint.py` 在该库 exit **0**。之后 `.venv/Scripts/python.exe -B <私有 free-remote.py>` exit **0**，业务按设计以 `MODEL_CALL_DISABLED` 结束。新建 `xiutu_test_diag_free_b521c901`，Alembic exit **0**；运行修正后的 `tests/live/test_diagnosis_slice.py::test_one_bounded_synthetic_turn`，**未设置** `DIAGNOSIS_SLICE_LIVE`，exit **0 / 1 passed**，其中新 checkpoint 初始化成功。受影响 `test_wp11_candidate_diagnostics_integration.py` 与 `test_wp11_graph.py::test_graph_interrupt_and_saved_observation_resume`，exit **0 / 5 passed**；`ruff check tests/live/test_diagnosis_slice.py` exit **0**。免费验证没有发送 DeepSeek 请求，也没有读取完整真实费用账本。没有重跑全仓或重新评测资料检索质量。

生产 `worker.py`、`graph.py`、`runner.py` 最终 SHA-256 分别为 `DADFDD4C6D7836E659DF2F377E44A88D7960225D41C1400A648BD6437B20D84F`、`DB44CAC08CA1AF1E6F3CEDD2DFEA639422E71E262770A2EC85268F6DB53FD918`、`FD51E0DD0339E4396B47E64F08C8AD9D26EF8361A7827E10935A06C75A16FD3E`，本轮未改。修正后的 live 测试 SHA-256 为 `BADA9B22074DC92F774A7E9040AB3D5517DCD40C2DDB42067D2B612332D8565F`。Git index 前后 SHA-256 均为 `C451D6E78B8F29FC818002923A19FB1A888139CED20679AD545F75E9692A9EC6`。

## 唯一新的真实首轮

免费路径通过后，在全新 `xiutu_test_diag_real2_c7af8164` 隔离库中运行迁移（exit **0**），由修正后的 live 测试先安装 checkpoint、上传/解析合成台架资料、建立 BGE-M3 1024 维索引、冻结该 case 的资料范围并启动独立只读 MCP，再创建**一个**真实初始诊断 run。命令为 `.venv/Scripts/python.exe -m pytest tests/live/test_diagnosis_slice.py::test_one_bounded_synthetic_turn -q -s --basetemp <本轮私有目录> --junitxml <本轮私有目录/live.xml>`，`DIAGNOSIS_SLICE_LIVE=1`，exit **1**：run `failed`，错误 `DIAGNOSIS_PROPOSAL_NEEDS_INPUT`，publication **0**，当前步骤不存在。此处不是先前的 `HANDLER_FAILED`。

本轮私有受限候选诊断只提取：首次 `propose_step` 结构有效、`needs_input`、`INTERPRETATION_UNCERTAIN:interpretation`；一次修复返回结构有效的 `need_input`。不公开模型原文、问题描述、引用摘录、工具参数或完整响应。原 WP-10 门禁未放宽，也没有手写候选替代模型输出。由于首轮未发布，**没有浏览器观察、child run 或真实续轮**；未把免费夹具续轮冒称真实成功。真实路径的受限原始文件位于 `.test-runs/diag-slice-real2-c7af8164/`，公开仅有[有限汇总](evidence/diagnosis-slice-pre-model/summary.json)。本轮独立 MCP 进程由测试结束清理；5180/5196 未操作。

模型请求 **3** 次、工具尝试 **4** 次，均在原单 turn 上限内。原共享 v2 账本在本轮前后为 18→21 条调用、累计保守预留 ¥2.329216→¥2.839008，新增预留 **¥0.509792**。三次请求均收到 usage；按已记录 token 与本地计价系数计算的估算为 **¥0.046290**，并非平台账单，平台实际扣款未核实。无累计人民币 5 元拒绝上限；仍保留每次发送前的持久预留、模型/API 白名单、四请求和 120 秒门禁。原始私有 trace、MCP 凭据、数据库 URL 与账本留在原受限位置，由操作者在完成后续定位后处理，不复制进公开报告。

## 停止点

前模型环境接线错误已按同路径免费反例定位和修复；新的真实 turn 进入候选校验，但其解释字段无法获原资料支持，修复候选主动 `need_input`。按本轮授权，失败后**停止**，没有新建第二个付费首轮。完整模型→第一检查→保存观察→真实第二检查链路仍未验证，切片保持 **BLOCKED**、未接受、未部署；WP-13—17 仍 `NOT_STARTED`。合成资料 `formal_usable=false` 不代表 DKVB 实车维修，真实资料 `NOT_MET`、生产恢复和旧 worker 首次失败根因等既有限制继续保留。本报告是执行者自测，不是集中审核。
