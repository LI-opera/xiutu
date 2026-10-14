# WP-11 交付阻断整改 r1（实施自测，非审核/接受）

本次只处理[原实施结果](wp-11-result.md)中的完整入口失败和真实模型截断。WP-12、预览功能、用户实例、既有历史迁移和接受范围均未扩展。真实资料仍为 `NOT_MET`；DKVB 合成整理正文不构成实际维修依据。

## 基准与失败归组

开始/保护核对见 `evidence/wp-11-remediation-r1/baseline-check.json`：历史接受文件、旧迁移和 Git index 与 WP-11 原封存一致。原始失败日志、真实探针摘要及预算预留继续保留在 `evidence/wp-11/`，没有覆盖。

原完整入口的 20 项失败分成两组，不把数量当缺陷数：

1. **标准入口测试工件目录（17 项）**：失败栈均在旧 WP-10 测试的 `save()`，原因是 `WP10_EVIDENCE` 未设置。`scripts/test.ps1` 已改为每次 UUID 测试运行创建自己的 `wp10-evidence` 目录，且 pytest 临时目录独立，避免由调用者手工准备或覆盖历史证据。原 17 项在隔离库定点通过；最终标准入口的实际结果另记。
2. **旧 worker/索引/receipt 共享路径（原 3 项，后续定点另见 revoke 1 项）**：原失败中两个 ingest worker 在 `before_finish` 后约 6 毫秒退出，但 run/job 仍 `running`、版本仍 `parsing`、chunk 为 0；另一个索引锁窗口没有观察到预期 PostgreSQL 等待。原子事务未半发布。旧定点里的 `revoke` 组合在 `before_finish` 时 staged embeddings 为空。未预设为机器慢或生产缺陷。测试子进程增加仅在 `WP11_TRACE_WORKER=1` 时生效的安全异常类别、DB 时钟/租约状态标记；不打印 SQL 参数、连接串或原文，不改变生产 worker、fencing、断言和旧测试。四个原失败实例加 WP-11 图共享路径定点 13 项通过；完整索引及 receipt 两模块依原顺序 32 项通过、1 条已知警告。旧失败在这些定点中未复现，**原始根因仍未确证**；最终完整入口若再现，将依据新标记具体定位，不凭重跑通过宣称已修复。

## MODEL_TRUNCATED 的具体阶段与整改

原共享账本仅按既有 WP-11 turn 的非秘密元数据读取：请求 1、2 均为工具调用并返回，第三次在最终 JSON 候选阶段以 `MODEL_TRUNCATED` 失败，原 `max_tokens` 与每次预留的 `output_upper` 均为 768；第三次 usage 缺失，预留未清零。不是 BGE、MCP 初始化或第一轮工具响应截断。原探针测试自身退出 0 而业务失败，属于验收判定错误。

`backend/app/config.py` 新增仅服务端可设的 `diagnosis_max_output_tokens`，默认 1536、允许 768—1536；`runner.py` 仅在 WP-11 工厂调用传入该值，普通 WP-09 网关仍默认 768。`model_gateway.py` 对输入界限再次校验，同一值用于 SDK 请求与共享账本的保守预留，并记录脱敏请求模式/失败阶段；`length` 继续拒绝，不拼接残缺 JSON。提示只增加通用的准确引用与缺项规则、紧凑输出 schema，不植入 DKVB 病例答案，不绕过 WP-10 校验。工具/检索/模型次数、120 秒期限和一次业务修复限额保持。

`tests/live/test_wp11_dkvb.py` 现在先保存脱敏结果，再要求 run 为 `waiting_input`、恰一条 publication、当前检查由既有校验接受、引用属于冻结 manifest，且新读取进程见到同一检查、账本调用数不增。业务失败必须让成功验证入口非零退出；不以 pytest 运行结束替代业务发布。未达到这些条件的真实请求保留负面证据，不反复付费尝试直到模型“答对”。

官方当日价格及 JSON 截断说明的链接和本项目保守上界见 `evidence/wp-11-remediation-r1/price-check.json`；价格/费用使用原 `deepseek-flash` 与共享人民币 5 元账本。usage 估算及预留均非平台账单。

## 免费验证、最终完整入口与真实链路

免费定点：原四项加 WP-11 图测试 **13 passed**（`worker-diagnostic-run.json`，原始隔离日志）；索引和 receipt 自然顺序 **32 passed、1 warning**（`legacy-modules.log/xml`）；模型配置、请求预留、截断与一次修复等 **32 passed**，新增失败阶段元数据后 3 项复跑通过（`free-targeted.log/xml`、`model-final.log/xml`）。这些结果分别记录，不相加冒充新覆盖数。未改变既有已接受测试的业务断言。

最终标准完整入口：在全新 `xiutu_test_wp11_full_cfa3c42a6871` 库上执行 `./scripts/test.ps1`，2026-09-19 19:45:16—20:18:49（+08:00），**退出码 0，449 passed、1 warning，2009.96 秒**。原始输出保留在本轮 Git 忽略的私有测试目录；脱敏统计见 `evidence/wp-11-remediation-r1/full-final-summary.json`，运行记录见 `full-run.json`。标准入口不生成 JUnit，本报告不虚构 XML。运行前后 176 个源码、迁移、脚本及测试文件的 SHA256 完全一致，见 `full-pre-code-hashes.json` 与 `protection-final.json`。原 20 项失败这次均未出现；worker/索引/receipt 原偶发失败的首次根因仍未确证，不能把这次通过写成已找到并修复其根因。

完整入口通过后，仅建立一个新的 `xiutu_test_wp11_live_b9b2aeb36685` 隔离库并执行一次 `uv run --frozen python -B -m pytest -p no:cacheprovider -q -s tests/live/test_wp11_dkvb.py`。库准备首次把 Alembic URL 写成项目不接受的 `postgresql+psycopg://`，迁移退出 1；保留私有失败日志，随后在**同一个新库**用 `postgresql://` 完成迁移与 checkpoint，均退出 0（`live-db-prep.json`）。该准备失败发生于模型调用之前。

真实链路于 20:21:59—20:23:16 运行，**pytest 退出码 1，业务 run=`failed`、`DIAGNOSIS_PROPOSAL_NEEDS_INPUT`、publication=0、无当前检查**。这次成功入口准确拒绝了“进程完成即业务通过”的旧假阳性。两份白名单合成正文在新库完成上传、审核、BGE 索引和会话冻结；真实只读 MCP 执行 6 次工具尝试。DeepSeek 共 4 次请求：前 2 次结束为 `tool_calls`，后 2 次 JSON 响应均为 `stop`，**这次没有 MODEL_TRUNCATED**。当前 run 的一次业务修复额度已使用，未形成可暂存的有效候选；因此失败位于候选/修复校验阶段，尚未到事务发布。现有脱敏轨迹不足以断言候选到底缺哪个字段或支持关系，不能猜成模型、MCP 或数据库故障。独立进程重新读取同一步骤的成功断言因没有步骤而未执行；确定性恢复测试与真实成功证据必须分开。

四次请求的 usage 均有返回，合计输入 19,945 token、输出 1,080 token。按已核对 `deepseek-flash` 峰值输入/输出单价、不享缓存优惠的估算上界为 **¥0.048530**；原共享账本的保守预留从 **¥0.662576** 增至 **¥1.296968**（本轮增加 ¥0.634392），这不是平台账单。账本没有重置或另建额度，仍低于共同授权的 ¥5 上限；所有真实请求和修复均计入。见 `live-safe-summary.json`、`live-run.json` 和私有原始日志。按用户停止条件，**没有创建第二个付费业务 turn，也没有用夹具冒充真实发布**。

下一项免费可验证假设：首次 JSON 候选与 WP-10 的字段/支持关系门禁不匹配，唯一一次修复仍未给出可接受的 `propose_step`。可在隔离测试中只记录校验 issue 的代码与路径、候选类型和修复前后结果，不记录原始问题、引用正文或模型响应，再用 MockTransport/合成候选重现；这些证据出现之前不扩大提示、不放宽门禁、不再次付费碰结果。

## 范围及停止条件

原共享费用账本不重置、不另建 5 元额度；本轮确实只在免费与完整回归通过后发起一个真实业务 turn。测试库、storage、cookie、worker 均隔离；5180/5196 和用户索引不操作。结束核对：176 个全量基准文件、12 个受保护历史文件与 Git index 均无差异（`protection-final.json`）。由于**真实当前检查尚未发布**，WP-11 继续 `BLOCKED`；STATUS 仅更新本轮证据及剩余阻断说明，不自行审核、接受或进入 WP-12。下一步需要先取得免费、脱敏的候选校验原因，再由用户决定是否授权后续真实验证。
