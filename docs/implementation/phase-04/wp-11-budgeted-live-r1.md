# WP-11 四次请求上限与一次有界真实诊断

时间：2026-09-20（Asia/Shanghai）。**WP-11 仍为 BLOCKED**：本轮唯一实际创建的 DKVB 业务 turn 未发布当前检查，run=`failed`、`DIAGNOSIS_PROPOSAL_NEEDS_INPUT`、publication=0。没有自行审核或接受，也没有进入 WP-12。

## 改动与边界

- `backend/app/infrastructure/model_gateway.py` 为可信工厂参数增加 `max_model_calls`，严格接受整数 1—5；WP-09 普通调用默认仍为 5。每次提供方尝试（含 429/5xx 重试）先检查次数，再预留和发送，第 5 次在 WP-11 模式被拒绝。
- `backend/app/agents/runner.py` 在 WP-11 默认付费工厂固定传入 4，继续使用 `resume_existing=True` 从同一 turn 的持久账本恢复已有尝试；模型输出或普通 API 参数不能提高该上限。一次业务修复、120 秒 turn 期限、原始 fencing 和 WP-10 校验未放宽。
- 新增 `tests/unit/test_wp11_call_limit.py`，扩充 `tests/integration/test_wp11_candidate_diagnostics.py` 以检查真实 runner 的工厂接线；同步 [契约](wp-11-contract.md)和[模型运行说明](../../runbooks/models.md)。真实探针 `tests/live/test_wp11_dkvb.py` 的 MCP 启动就绪上限从 30 秒改为 90 秒，只约束隔离服务启动，不延长业务 turn 或增加模型次数。
- 没有修改 WP-10 门禁、提示词、原资料包、历史迁移或用户 5180/5196 实例。Git index 未调整。

## 免费验证及费用门禁

从 `E:\Work\xiutu-v5` 执行 `ruff check --no-cache`（退出 0），以及 `python -B -m pytest -p no:cacheprovider -q tests/unit/test_wp11_call_limit.py tests/unit/test_wp11_price_gate.py tests/unit/test_wp11_model_limit.py tests/unit/test_wp09_remediation.py tests/unit/test_wp09_contracts.py`（退出 0，**39 passed**）。覆盖正常 4 次、包含 429 的 4 次、第 5 次零预留零发送、从原 turn 账本跨 worker 恢复、上限非法/余额不足和 WP-09 默认 5 次。证据：[unit-run.json](evidence/wp-11-budgeted-live-r1/unit-run.json)、[unit.xml](evidence/wp-11-budgeted-live-r1/unit.xml)。

隔离 PostgreSQL 下执行 `python -B -m pytest -p no:cacheprovider -q tests/integration/test_wp11_candidate_diagnostics.py`（退出 0，**4 passed**）；其中实际 runner 工厂接线检查 `max_model_calls=4`、恢复标志和 1536 输出上限。证据：[integration-run.json](evidence/wp-11-budgeted-live-r1/integration-run.json)、[integration.xml](evidence/wp-11-budgeted-live-r1/integration.xml)。这些是本轮定点结果，**不是**历史 449 项完整回归在当前字节版本重新通过。

在原共享账本的锁内只读聚合字段：运行前上限 ¥5、已保守预留 ¥1.296968、剩余 ¥3.703032；记录 11 次。每次按 100000 UTF-8 字节上限、404096 输入 token 保守上界及 1536 输出 token 上限，最坏预留 ¥0.820480；4 次最坏 ¥3.281920，运行前额度足够。见 [budget-preflight.json](evidence/wp-11-budgeted-live-r1/budget-preflight.json)。原账本没有重置或复制进证据。

## 真实 turn 与候选原因

在新隔离库、storage、测试 worker 和独立只读 MCP 进程运行 `run-live.ps1`。第一次尝试的数据库创建、迁移和 checkpoint 均退出 0，但 MCP 健康检查 30 秒内连接超时，测试退出 1；停在**创建诊断 run 之前**，未预留或发送模型请求。原失败记录保留为 [live-run.json](evidence/wp-11-budgeted-live-r1/live-run.json) 和受限目录内原始日志。MCP 启动日志为空，因此具体慢启动原因未确证；将测试启动就绪边界设为有界 90 秒后，第二次隔离准备通过，并且只创建了**一个**真实业务 turn。该次退出 1，记录为 [live-run-b85c…json](evidence/wp-11-budgeted-live-r1/live-run-b85c741ab44d485bbf782825815124ed.json)。没有因业务失败再次开付费 turn。

本轮经 DeepSeek `deepseek-flash`、本地 BGE-M3 与独立只读业务 MCP 实际运行：4 次模型请求均返回 usage，工具尝试 6 次；run=`failed`，错误 `DIAGNOSIS_PROPOSAL_NEEDS_INPUT`，publication=0、无当前步骤。首次候选是 schema 有效的 `propose_step`，业务校验给 `needs_input`，共 16 个受控 issue 标识：主要包括 `SCOPE_NOT_MATCHED`（purpose/prerequisites/actions/interpretation/choices）、`COMPONENT_NOT_GROUNDED`、`LOCATION_MISSING`、`CONDITIONS_UNCERTAIN`、`ACTION_SEMANTICS_UNCERTAIN`、`CHOICE_SEMANTICS_UNCERTAIN`、`INTERPRETATION_UNCERTAIN`。一次修复后的候选为 schema 有效的 `need_input`，disposition 仍为 `needs_input`，没有再发布。**这是业务校验拒绝及修复后主动待输入，不是 JSON 解析失败，也没有证据表明发生第 5 次额度拒绝。**详情仅含白名单 code/path 的 [脱敏摘要](evidence/wp-11-budgeted-live-r1/live-sanitized.json)；不含模型原文、资料正文、工具参数或凭据。

共享账本保守预留从 ¥1.296968 到 ¥1.947480，本 turn 增量 **¥0.650512**；锁内再次读取的剩余额度为 ¥3.052520、总记录 15 次。4 次 usage 分别是输入/输出 token 3885/349、4424/192、8803/965、3369/353；按现行峰时不考虑缓存优惠估算 **¥0.055834**。保守预留与 usage 估算均**不是平台账单**，账单未核实。没有再付费尝试。

原始测试输出及私有候选 trace 留在 `.test-runs/wp11-four-live-b85c741ab44d485bbf782825815124ed` 的受限目录，供操作者后续按证据保留策略清理；公开报告仅摘录结构化字段。两次隔离 MCP/worker 由测试 finally 停止，用户 5180/5196 未操作。隔离测试库未删除，也未复用历史审核库。

## 停止点

本轮已经取得之前无法还原的**本次**候选拒绝位置，但不能据此倒推历史真实候选的具体内容。后续若继续，应先用免费合成反例核查引用范围、动作位置和条件映射，再由用户决定下一步；本轮不猜测修改 WP-10 门禁或植入 DKVB 答案。因没有发布成功，不执行成功分支的独立进程读回和最终完整入口，WP-11 保持 `BLOCKED`。旧 worker 首次失败根因仍未确证；真实资料 `NOT_MET`、Linux BGE 部署及历史 SSE/Compose/启动根因限制保留。
