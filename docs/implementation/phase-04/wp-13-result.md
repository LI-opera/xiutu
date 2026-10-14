# WP-13 报告服务实施结果（2026-09-21）

状态：**IMPLEMENTED_NOT_ACCEPTED**，仅为执行者实施与自测，等待一次集中审核和用户决定。真实资料仍 `NOT_MET`；此前诊断切片只发布首项当前检查和后续保守 `unknown` 卡，没有第二项当前检查。`unknown` 不是确诊、排除或最终报告就绪。

## 实际能力

- `0012_reports` 增加报告历史表，并扩充区域卡数据库 assessment 约束；没有公共接口将 `unknown` 卡改成最终结论。报告任务仅在用户带认证、CSRF、当前 revision 和幂等键主动请求时建立。
- 进度报告读取已保存检查、观察选择或测量值、区域卡、冻结资料与缺项；`unknown` 病例可生成，正文不产生确定换件清单。最终报告由服务端六项门禁控制，未满足时 409 `FINAL_NOT_READY`，返回结构化 `blocking_items`，不创建 run/job。
- 独立报告 LangGraph 读取冻结快照、核对结论和冲突、生成并校验草稿；现有 JobStore 的 lease/fencing 与 owner/case 锁在同一 PostgreSQL 事务中完成报告状态、run/job 终态及事件发布。发布前重新核对 revision、epoch、manifest、当前结论、来源、规格和门禁。旧结果保留历史；当前有效性在 GET 时重算。
- 统一 `ReportDraft` 限制字段和大小。最终诊断说法与可信卡的原句及本卡引用绑定；换件动作只能来自 `supported` 卡，前置条件、操作和完成标准逐项匹配；规格审批/来源有效性、动作去重及依赖环均硬校验。报告模型路径可通过现有工厂和计量网关，但本包未开启付费请求，使用 MockTransport 验证结构化生成。

主要新增：`backend/app/services/report_policy.py`、`report_service.py`、`report_publish.py`，`backend/app/agents/report_graph.py`，`backend/app/validators/report.py`，`backend/app/api/reports.py`，`migrations/versions/0012_reports.py`，`tests/integration/test_wp13_reports.py`。必要接入改动在 `main.py`、`worker.py`、`job_store.py`、`case_service.py`、ORM/schema；接口与运行说明见 [API](../../api/wp-13-reports.md) 和 [runbook](../../runbooks/reports.md)。未改 0001—0011 历史迁移、用户 5180/5196、Git index。

## 验证及原始证据

测试环境为新建 `xiutu_test_wp13_2fa18dfeb0ee` 隔离 PostgreSQL，真实 HTTP/API、worker 和免费 MockTransport。真实付费报告调用 **0**。本包定点覆盖 unknown 进度报告与最终拒绝、用户请求才入队、重复键、合成 supported 卡的完整最终路径、模型输出与当前结论绑定、重复动作和环、ruled_out 不授权换件、跨 owner、请求后来源撤销、发布前旧 revision 以及观察更正后的历史 stale。合成最终卡是测试夹具，不是实际维修结论。

原始证据分别保留，不合并为不同功能覆盖数：

| 运行 | 结果 | 证据 |
| --- | --- | --- |
| 首轮 WP-13 定点 | 3 项夹具接线错误，随后修正 | `.test-runs/wp13-targeted-99bcf8769e0f49109e353d7888a23bb9/` |
| 受影响定点及反例 | 5 项通过；后续图接线 5 项通过；真实观察更正 1 项通过 | `.test-runs/wp13-final-targeted-e6974c69b9854d3ab2fa80681fa36c69/`、`.test-runs/wp13-graph-targeted-113b44b77ed44d6687e80e3572b6ec4d/`、`.test-runs/wp13-correction-dbd9c87053494c76967aa42eeda1725a/` |
| 中途完整入口 | 两次主动中断：先发现测试环境变量污染旧单测，后收紧报告动作与观察正文；原始部分输出保留，均不能算完整回归 | `evidence/wp-13/full-838c65673cfc4fe0ba993ba05c33ccad/`、`evidence/wp-13/final-full-1644d2de056d45c89728244d49a4ab45/`、`evidence/wp-13/final-full-8e016b14263b43648e5272a962a7f7d6/` |
| 首次完整入口（测试配置缺口） | 退出 1：415 通过、100 失败、1 警告；大部分失败来自测试进程加载开发库配置，另有迁移清单未列新表；失败保留，不算业务完整通过 | `evidence/wp-13/final-full-b0490365aebd47269539263204cab188/` |
| 根因定点 | 认证、迁移与 WP-13 共 11 项通过、1 警告；随后测试入口显式绑定隔离 `DATABASE_URL`，并更新新表预期 | `.test-runs/wp13-rootcause-1574dbcde8b84f14a9e736ae676928af/` |
| 修正后的标准完整入口 `./scripts/test.ps1` | 用户关机导致外部中断，无 pytest 汇总、无退出码；日志推进至迁移/后续集成段，不能记为通过 | `evidence/wp-13/final-full-d5c3ff4fa3ee4547bb53062b669613c5/` |
| checkpoint 前置缺口后的完整入口 | 退出 1：506 通过、9 失败、1 警告；9项均与全新库未显式初始化 LangGraph checkpoint 表相邻，失败原样保留 | `evidence/wp-13/final-full-a9b67a2f01b54795bc3ec110bca68f41/` |
| checkpoint 根因定点 | 自动初始化既有 checkpoint schema 后，原9项全部通过（130.07秒） | `.test-runs/wp13-nine-failures-e1298cd58a914e0e8170eb9b0cff3852/` |
| 最终标准完整入口 `./scripts/test.ps1` | 退出 1：514 通过、1个 `httpx.ReadError [WinError 10053]`、1警告（41:23）；唯一失败发生在测试HTTP读取、没有业务断言结果 | `evidence/wp-13/final-full-7d4a328f77fd43cb9f89f39f80d85529/` |
| 唯一失败定点复跑 | 同一源码、同一隔离库、无代码改动，1项通过（14.46秒）；按约束不循环重跑完整入口 | `.test-runs/wp13-single-readerror-5d81532506ba4e3f938df11a93d41b87/` |

先前失败不是执行通过：使用全局 `APP_MODE=test`、`RETRIEVAL_PROFILE=synthetic` 污染了部分旧单测；仅提供 `TEST_DATABASE_URL` 时，又会让显式 `Settings(app_mode="test", retrieval_profile="synthetic")` 从项目 `.env` 读取非隔离库配置。前者的认证单测 5 项通过，见 `.test-runs/wp13-auth-clean-b4fe98c535b5463898854cc6a7be3b33/`；后者的 100 项失败原始日志保留。测试脚本现将已验证的 `TEST_DATABASE_URL` 传给 `DATABASE_URL`，没有放宽合成资料数据库隔离规则；迁移清单加入 `reports` 表，并在每个全新测试库上显式运行既有 LangGraph checkpoint 初始化。根因组 11 项、checkpoint原失败9项以及最终唯一HTTP读错误实例分别定点通过；Python受影响文件Ruff通过。用户关机中断轮、506/9轮及514/1轮均单独保留，不能改写为完整入口全绿；最终源码哈希见最后一轮证据目录。

## 可复现体验与限制

在隔离库迁移到 `0012_reports`，以同 owner 登录并获取当前 case revision；先 `GET /api/v2/cases/{id}/reports/gate`。对 `unknown` 病例 `POST .../reports` 请求 `kind=progress`，由本轮 worker 处理后用 `report_id` 读取缺项与观察。相同病例请求 `kind=final` 返回 409 且无报告任务。测试专用受信 supported/ruled_out 夹具可验证最终生成、引用/动作和 stale 行为；不得把夹具结果发给实际车辆用户。

目前生产诊断流程只自动形成保守 `unknown` 卡，没有已审核的 supported/ruled_out 卡写入流程，故真实 DKVB 和当前预览病例不能生成有效最终报告。报告模型未实际付费验证，结构化语义正确性不由 MockTransport 证明；通用自然语言支持/维修效果、真实资料门槛、Linux BGE、生产恢复、第二项当前检查和后续正式前端均未验收。WP-14 未开始。
