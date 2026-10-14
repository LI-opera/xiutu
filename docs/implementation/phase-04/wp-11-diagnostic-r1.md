# WP-11 候选校验免费定点诊断 r1

时间：2026-09-20（Asia/Shanghai）。范围仅为候选进入 `ProposalService.validate()`、一次修复及 `DIAGNOSIS_PROPOSAL_NEEDS_INPUT` 的诊断；未执行付费模型调用，未读取或重置真实费用账本，未审核或接受 WP-11。**WP-11 仍为 BLOCKED。**

## 基准与可确认事实

- 依据 `STATUS.md`、`wp-11-contract.md`、`wp-11-result.md`、`wp-11-remediation-r1.md` 及原 `live-safe-summary.json`。上轮最终完整 449 项通过是历史基准，本轮未重跑。
- 原真实 DKVB turn 的可确认结果为 4 次 DeepSeek 请求、一次修复额度已用、`DIAGNOSIS_PROPOSAL_NEEDS_INPUT`、publication=0；上轮已排除这次 `MODEL_TRUNCATED`。对原私有日志仅统计有限诊断标识，未复制或输出原文：见 [historical-detail-check.json](evidence/wp-11-diagnostic-r1/historical-detail-check.json)。日志没有候选类型、issue code/path/disposition。**历史真实候选的具体拒绝原因不可还原**；本轮合成结果不能冒充它。
- Git index 哈希与本轮开始记录的 `c451d6e78b8f29fc818002923a19fb1a888139ced20679ad545f75e9692a9ec6` 一致。历史报告、接受记录、迁移和用户实例未改。文件哈希见 [protection-final.json](evidence/wp-11-diagnostic-r1/protection-final.json)。

## 最小改动与诊断边界

- `backend/app/agents/runner.py` 在首次候选、首次 schema 错误、修复额度耗尽、修复 schema 错误及修复业务校验后调用可选诊断 sink。字段固定为 `stage`、候选类型、schema 状态、disposition、有限的 issue `code/path`、issue 数量、修复额度状态和有限错误码。`code` 用静态白名单，`path` 只允许受控字段名与有界路径；不包含模型原文、问题描述、资料、quote、工具参数、issue detail、凭据或完整响应。sink 异常不会改变原校验、预算或发布结果。未设置 sink 时生产默认路径不保存这些字段。
- `backend/app/agents/graph.py`、`backend/app/worker.py` 仅传递可选 sink；未改原 `ProposalService`、fencing、候选结论或 run 的公开错误。`tests/live/test_wp11_dkvb.py` 为将来**显式授权**的探针提供私有 trace 文件，未在本轮运行。Windows 下先收紧空目录 ACL，再创建 trace；普通 Users/Authenticated Users 不继承读取权限。文件仍由操作者保管于 Git 忽略的 pytest 临时目录，后续需按运行记录明确清理；不会写进 run、SSE 或静态资源。仅用合成文件核对 ACL，见 [private-acl-check.json](evidence/wp-11-diagnostic-r1/private-acl-check.json)。
- 新增 `tests/unit/test_wp11_candidate_diagnostics.py` 与 `tests/integration/test_wp11_candidate_diagnostics.py`。集成测试使用隔离 PostgreSQL、合成资料及 SDK `MockTransport`，无真实模型请求。没有改 WP-10 门禁或植入 DKVB 答案。

## 命令、结果及保留失败

所有命令在 `E:\Work\xiutu-v5` 执行，测试数据库为全新 `xiutu_test_wp11_diag_cd9ab3589daf`，没有复用用户实例或历史审核库。数据库创建、迁移和 checkpoint 初始化均退出 0；见 [integration-summary.json](evidence/wp-11-diagnostic-r1/integration-summary.json) 及隔离执行脚本 [run-integration.ps1](evidence/wp-11-diagnostic-r1/run-integration.ps1)。此脚本只从项目私有配置在进程内取得本地数据库凭据，不打印连接串；没有加载 `.env` 或真实模型账本。

| 执行 | 结果 | 证据 |
| --- | --- | --- |
| `python -B -m pytest -p no:cacheprovider -q tests/unit/test_wp11_candidate_diagnostics.py tests/unit/test_wp11_model_limit.py` | 退出 0，5 通过 | [unit.log](evidence/wp-11-diagnostic-r1/unit.log)、[unit.xml](evidence/wp-11-diagnostic-r1/unit.xml) |
| 首轮 `python -B -m pytest -q tests/integration/test_wp11_candidate_diagnostics.py` | 退出 1，夹具装配 4 错误；`docrig` 未导入，业务用例未执行 | [integration.log](evidence/wp-11-diagnostic-r1/integration.log)、[integration.xml](evidence/wp-11-diagnostic-r1/integration.xml) |
| 补齐测试夹具导入后，同模块定点重跑 | 退出 0，4 通过，53.29 秒 | [integration-r2.log](evidence/wp-11-diagnostic-r1/integration-r2.log)、[integration-r2.xml](evidence/wp-11-diagnostic-r1/integration-r2.xml) |
| `ruff check --no-cache` 覆盖本轮改动文件 | 退出 0 | 命令输出 `All checks passed!` |

首轮脚本还曾因计算项目根目录少一层而在读取私有数据库配置前退出，未建库；更正后才创建上列隔离库。独立 `py_compile` 因沙箱拒写 `__pycache__` 未完成；ruff、pytest 已完成语法/导入验证。上述失败未覆盖或改写。

## 本轮免费复现说明

- 合成 `propose_step` 缺位置：首次及一次修复均记录 `candidate_type=propose_step`、`LOCATION_MISSING`、受控 path、`needs_input`；run 失败、无 publication、修复额度已用。这证明可以区分业务校验拒绝并安全定位一个可能的门禁，但**不是上轮真实模型缺位置的证据**。
- 首次 `need_input`：记录类型与 disposition，未消耗修复额度，也没有发布。首次 schema 无效而修复为有效步骤：分别记录 schema 错误与修复后的候选，并通过原发布路径。首次有效 `propose_step`：正常进入原发布路径。后两者各恰好一条 publication、run 为 `waiting_input`。
- 4 条路径中 `MockTransport` 请求数、隔离预算记录与预期一致。合成秘密标记和内部 issue 不出现在普通 run GET 或 SSE；诊断文件的样例权限核查没有普通用户组 ACE。结构化字段仅能说明候选/校验在哪一步被拒，**不能据此判断真实维修语义正确**。

## 尚不能确认与下一步

上轮真实候选的具体 issue、拒绝属模型结构、引用支持关系、资料不足还是接入传递问题，均**未确证**。本轮正例说明同一接入路径能发布合成有效候选，缺位置反例说明 WP-10 门禁可正确拒绝，但两者都不能反推出真实失败原因。下一次如获真实调用授权，显式启用本次私有有限 trace，在一次 turn 后只提取 `type/code/path/disposition`；不能仅凭当前免费结果修改 WP-10 或付费重试。原 worker 首次失败根因亦继续单列“未确证”。真实资料仍 `NOT_MET`，历史 SSE/Compose/启动未确认根因及其他既有限制保留。

本轮未操作 5180/5196，未提交、推送、审核、接受或进入 WP-12。
