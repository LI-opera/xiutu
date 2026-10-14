# WP-11 实施结果（自测，未审核、未接受）

本包接续已接受的 WP-10，仅实现一轮一项的持久诊断任务：已有会话入队、原 worker 领取、可信资料检索与模型候选、WP-10 校验、同一事务发布当前建议检查、进入 `waiting_input`，再凭数据库已保存的观察引用开启下一轮。当前还没有 WP-12 观察提交界面、自动确诊、报告或正式前端。真实资料门槛仍为 `NOT_MET`，DKVB 合成整理正文不构成真实维修标准。

## 基准和改动

开始时 WP-00—10 各自限定接受，DKVB 专题切片限定接受；WP-11 原为 `NOT_STARTED`。本包只新增 `0009_graph`，原 `0001`—`0008`、旧项目、接受记录、历史报告与 Git index 均不改。保护文件和 index 哈希见 `evidence/wp-11/protection-current.json`、`final-protection.json`；后者确认历史保护文件及 Git index 均未变。完整回归时的 175 项源码哈希见 `full-final-v5-code-hashes.json`；此后仅 `scripts/test.ps1` 和 opt-in 探针 `tests/live/test_wp11_dkvb.py` 字节发生变化，生产实现和已收集测试未变。原 5180、5196 服务、数据库、storage、访问身份和索引未重启或更新；5196 原 worker 不存在，本包未操作。

- `migrations/versions/0009_graph.py`、`backend/app/infrastructure/orm.py`、`backend/app/infrastructure/schema_version.py`：区域、步骤、候选、publication 与 progress；唯一当前步骤及工作流键。LangGraph checkpoint 放独立 `wp01_wp11` schema，通过 `scripts/setup_graph_checkpoint.py` 显式初始化。
- `backend/app/agents/graph.py`、`checkpoint.py`、`runner.py`：状态增量只含流程引用，业务事实每次从数据库读取；可信身份、冻结资料、工具与本轮预算由服务端建立。原模型工厂/网关及只读 MCP 不重写；工具轮次上限不会暗中触发第二次 JSON 修复。
- `backend/app/services/diagnosis_service.py`、`publish_service.py`、`backend/app/infrastructure/job_store.py`、`backend/app/worker.py`：认证入队与已保存观察恢复，原物理 advisory 锁、租约 token、数据库时钟和单事务发布。锁或后续 SQL 等待之后重检租约及 120 秒 turn 期限，失效则整体回滚。发布已提交而 checkpoint 未更新由持久 publication/progress 对账，不重新请求模型。
- `backend/app/api/cases.py`、`backend/app/domain/schemas.py`、`backend/app/services/case_service.py`：受保护的启动、resume、当前检查入口与会话快照；原 run 查询/SSE 继续使用。
- 对应迁移、图恢复、模型预算及接口测试，`scripts/demo_wp11.py` 免费合成演示，`tests/live/test_wp11_dkvb.py` 明确 opt-in 的真实 DKVB/BGE/MCP/DeepSeek 探针；运行和边界见[契约](wp-11-contract.md)、[API](../../api/wp-11-diagnosis.md)、[运行说明](../../runbooks/diagnosis.md)。

## 事务和恢复边界

当前区域/步骤、case revision、run output revision、publication key/hash 与 `run.waiting_input` 事件在同一事务；同键同内容在有效 fencing 下返原结果，异内容及过期 revision 拒绝。`wait` 只中断图，不写业务事实。worker 失锁、租约过期、取消或 turn 超时不得迟到发布；checkpoint 也仅能由原物理锁连接、有效 token/PID/租约写入。等待状态释放 worker 和活跃槽。resume 只收观察 UUID，验证 case、步骤、revision、epoch 和当前有效性；测试直接准备观察不是 WP-12 用户写入流程。

每轮工具最多 6 次、检索最多 3 次、模型最多 5 次、业务修复最多一次，期限 120 秒；自动尝试最多 3 次，均继承同一 run/turn 与已用预算。诊断显式 retry 暂时 fail-closed，避免用新 run 重置预算；终态错误保留，正式待补/重新授权交互尚未实现。`need_input` 无有效当前检查时不伪装已发布。配置和费用不足、MCP 断连不会静默退回本地执行。

## 自测和证据版本

所有数据库验证只用新建 `xiutu_test_*` 库。首次完整入口因全局测试 profile 注入等配置问题、当时迁移期望和短租约夹具，记录为 `400 passed / 41 failed`，**不是最终版结果**，原日志保留。后续两次完整入口在代码检查发现工具轮次隐藏修复、turn 期限和显式 `.env` 装载差异时由执行者主动中断，分别见 `full-final-v2/v3/v4-interruption.json`；均不计为通过。首次异常堆栈包含测试数据库凭据，精确原始文件仅留在 Git 忽略的私有测试目录，交付副本已脱敏，见 `failure-redaction.json`。

| 检查 | 本轮实际结果 | 原始证据 |
| --- | --- | --- |
| `0009_graph` + checkpoint setup | 全新隔离库执行成功；未升级用户库 | `final-v5-db-prepare.json`、`final-v5-checkpoint.log` |
| 图、发布、恢复及迁移定点 | 9 passed；另新增 turn 期限锁等待 1 passed | `targeted-clean-v3.log/xml`、`turn-deadline.log/xml` |
| 网关轮次/修复预算定点 | 3 passed；无网络请求 | `gateway-final.log/xml` |
| 免费 CLI 合成恢复演示 | 1 passed；第一次发布后等待，数据库已存观察后第二轮发布 | `demo-free.log` |
| 标准完整入口，生产及收集测试最终版本 | **exit 1：426 passed、20 failed、1 warning**，约 36 分钟；不能视作通过。17 项 WP-10 失败均因标准入口未准备 `WP10_EVIDENCE`；另 3 项旧索引/receipt 用例失败，详见原日志 | `full-final-v5.log`、`full-final-v5-run.json` |
| 受影响旧用例定点 | **exit 1：24 passed、1 failed、25 deselected**；此前失败的 17 项 WP-10 和 3 项旧索引/receipt 本轮通过，另一个旧索引 `revoke` 组合的 staged embeddings 为空。原因未确证，不能称旧索引回归已修复 | `legacy-targeted.log/xml`、`legacy-targeted-run.json` |
| 标准离线入口（脚本修正后） | **exit 0：269 passed、1 条已知警告**；脚本为 WP-10 证据自动准备每次运行专属目录。没有据此冒称完整数据库入口已通过 | `offline-final.log`、`offline-final-run.json` |
| 真实 DeepSeek→只读 MCP 有界探针 | 第一次在上传响应码断言处失败、第二次因验证命令 URI 格式在收集阶段失败，均未调用模型；修正后一次探针测试自身 exit 0，但**业务 run=failed、MODEL_TRUNCATED、publication=0**。真实 `deepseek-flash` 请求 3 次、工具尝试 6 次，未得到可发布的当前检查。保留负面结果，不为了答对重复付费 | `live-run.json`、`live-run-v2.json`、`live-run-v3.json`、`live-summary-sanitized.json`；完整原始输出仅在 Git 忽略的私有测试目录 |

完整入口使用 `./scripts/test.ps1`，cwd 为项目根，环境只显式指定隔离 `DATABASE_URL/TEST_DATABASE_URL`，不注入全局 synthetic profile 或模型凭据。脚本修正后 `./scripts/test.ps1 -OfflineOnly` 无数据库配置通过；旧 WP-10 失败分组在隔离库中经独立证据目录定点验证，但未再次执行完整数据库入口。原始输出与起止时间、退出码保存到各 `*-run.json`；未将重复定点项目累加为功能覆盖数。真实探针在用户授权的**原共享 ¥5 账本**中预留额从 ¥0.198184 增至 ¥0.662576，增加 ¥0.464392；前两次 usage 有报告，第三次缺失，故不能记零费用。预留额和 usage 推算不是平台账单，本轮没有另建额度或重置账本。

## 可体验步骤和未完成项

在**新隔离库**先 `alembic upgrade head`，再运行 `python -B scripts/setup_graph_checkpoint.py`；启动独立 API/worker 后，用原认证与 CSRF 创建带已冻结资料的会话，调用 `POST /api/v2/cases/{id}/diagnosis/runs`，通过 run/SSE 与 `GET /api/v2/cases/{id}/diagnosis` 查看当前建议检查。免费可复制入口 `python -B scripts/demo_wp11.py` 只使用合成候选和直接保存的测试观察，明确不是 AI 或实际维修建议。观察保存后的 `POST .../diagnosis/resume` 只接收其 UUID。运行环境、必要配置及停止方式详见[runbook](../../runbooks/diagnosis.md)。本包不部署到 5180/5196。

**停止点与必须解决项：WP-11 尚未达到交付通过。** 标准完整入口仍有 20 项失败，其中 WP-10 证据目录问题已有脚本修正和定点证据，但旧索引 `revoke` 等并发用例仍需定位并在受影响范围复核；真实模型链路得到 `MODEL_TRUNCATED`，没有完成校验和发布。免费确定性图/事务/恢复能力已经实现并通过定点，但不能替代上述两项门槛。当前状态如实记为 `BLOCKED`，不自行审核或接受；后续应定点诊断旧索引失败，并在共享预算允许且有明确修正依据后才考虑一次新的真实链路验证，不循环请求直到模型答对。

真实资料来源/许可、精确车型适配、正式规格和缺失章节/图片仍未达原截止要求；既有 Linux BGE、SSE/启动/Compose 未确认根因及性能/监控/清理待办保持。E10 沿用 WP-09 对 `deepseek-flash` 的限定结论，WP-11 的合成探针不代表真实维修效果。共享人民币 5 元授权绝不重置；预留和 usage 估算均非平台账单。WP-12—17 未启动，不自行写审核通过或用户接受。
