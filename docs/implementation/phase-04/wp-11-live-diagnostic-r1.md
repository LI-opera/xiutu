# WP-11 有界真实诊断验证：调用前阻断记录 r1

时间：2026-09-20 12:49（Asia/Shanghai）。本轮遵照“一次新业务 turn；预算或配置门禁拒绝即停止”的授权。**未发起真实 turn、模型请求或工具调用；没有取得本轮候选校验原因。WP-11 继续 BLOCKED。**

## 前置基准

- 已读 `STATUS.md`、`wp-11-remediation-r1.md`、`wp-11-diagnostic-r1.md`、`tests/live/test_wp11_dkvb.py` 及 `runner.py` 诊断路径。上轮真实候选的具体拒绝原因无法从历史记录还原；449 项完整回归只属于上轮版本。本轮没有重跑全套或改候选校验。
- `runner.py`、`graph.py`、`worker.py`、真实探针代码 SHA256 均匹配诊断 r1 的封存清单；Git index SHA256 仍为 `c451d6e78b8f29fc818002923a19fb1a888139ced20679ad545f75e9692a9ec6`。未修改实现、接受记录、迁移或历史证据。
- 现有 PostgreSQL `127.0.0.1:5433` 可达，本机 BGE-M3 目录、项目私有 `.env` 和共享账本存在。真实探针显式采用 `deepseek-flash`，项目私有 `.env` 中的旧 `deepseek-chat` 配置不会用于该探针。本轮未打印凭据、连接串、模型正文或完整账本。
- 上轮合成 ACL 检查显示受限 trace 子目录下无继承 ACE、无普通用户组 ACE；本轮代码与该检查时一致。但因费用门禁先拒绝，**本轮未创建**隔离数据库、storage、MCP 实例、worker、业务 turn 或新的私有 trace；这些运行时条件不能称为本轮动态通过。

## 免费预算与门禁检查

在 `E:\Work\xiutu-v5` 通过项目 `.venv` 执行只读 Python preflight（退出码 0）：使用合成占位 key 构造 `DeepSeekGateway(settings, paid=True)`，构造函数在任何 HTTP 请求及新的账本预留前返回 **`MODEL_PRICE_RECHECK_REQUIRED`**。代码门禁要求当前 UTC 早于 `2026-09-20 00:00:00`；实测为 `2026-09-20 04:49:46 UTC`。这表示既有价格依据的有效期已到，不等于共享 ¥5 余额耗尽。遵照停止条件，本轮没有改有效期、核价常量、配置或绕过门禁，也没有运行真实 DKVB 测试入口。

只输出聚合账本字段：上限 ¥5、检查前已预留 ¥1.296968、剩余 ¥3.703032、既有记录 11 条；检查后仍为 ¥1.296968 和 11 条。预留金额和历史 usage 估算均不是平台账单，本轮没有新增 usage、预留或实际费用。脱敏核对见 [preflight.json](evidence/wp-11-live-diagnostic-r1/preflight.json)。未输出或复制完整账本到证据目录。

## 结果与后续条件

因调用前门禁拒绝，真实测试入口**未执行**，没有退出码、run 状态、publication、独立进程恢复结果或本轮候选 `type/stage/schema/disposition/code/path`。不能把上轮失败或免费 MockTransport 反例冒充本轮真实候选。上轮 `DIAGNOSIS_PROPOSAL_NEEDS_INPUT` 的具体原因与旧 worker 首次失败根因仍为**未确证**。

如需再做真实验证，须先由有授权的实施工作核实当前 `deepseek-flash` 价格及有效期，并使原费用门禁按可审查依据恢复；随后重新核对共享账本和本轮授权。不得简单改系统时钟、抬高额度或用另一份账本。此报告不授权第二个付费 turn，也不提出未经真实 trace 支持的提示词、资料或 WP-10 门禁修改。

未操作 5180/5196、旧项目或用户数据；无私有 trace 需要本轮清理。真实资料 `NOT_MET` 及其他既有限制继续保留。未审核、接受、提交、推送或进入 WP-12。
