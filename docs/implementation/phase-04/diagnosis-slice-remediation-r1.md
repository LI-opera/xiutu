# WP-13 前诊断闭环切片：免费定点诊断与整改 r1

记录时间：2026-09-20（Asia/Shanghai）。**切片仍为 BLOCKED。**本轮没有调用付费模型、读取或重置真实费用账本，也没有审核、接受或启动 WP-13。以下通过的续轮仅为明确标记的确定性合成夹具，不是 DeepSeek 自主发布。

## 基准与受限证据

实施前复核 `diagnosis-slice` 交付清单，所列文件均匹配；Git index SHA-256 为 `C451D6E78B8F29FC818002923A19FB1A888139CED20679AD545F75E9692A9EC6`，本轮未改 index。历史契约、结果、失败日志和受限候选诊断未覆盖。原真实 turn 仍为 `DIAGNOSIS_PROPOSAL_NEEDS_INPUT`、publication=0；原免费续轮仍为 `MODEL_TURN_TIMEOUT`、publication=0。

只在本机受限目录读取旧候选诊断的有限 `stage/type/schema/disposition/code/path` 字段。旧记录**没有候选原文**，因此无法还原模型具体选用了哪一段、如何改写字段或填写了何种解释；不能将下述免费夹具的措辞当成旧真实候选。公开报告不包含模型原文、工具参数、凭据或私有 trace。

## 拒绝码逐项定位

| 首次候选 code/path | 可确认的原因与来源 | 不可确认的部分及处理 |
| --- | --- | --- |
| `CONDITIONS_MISSING:prerequisites` | 首次候选缺前提字段；旧首轮检索 top3 片段未含工况句，完整已授权合成版本在 `tests/fixtures/diagnosis-slice/bench.md:9` 有明确 `engine=off` 工况。 | 无法知道模型是否另行检索；本轮让原工具在同一冻结版本中有界取相邻块，不填造条件。 |
| `LOCATION_UNCERTAIN:location` | 首次字段未满足原有明确空间关系规则；合成来源在 `bench.md:7` 有对象和方位，旧 top3 已覆盖位置。 | 无候选原文，不能断言具体改写或错引；提示要求完整来源句，不改变规则。 |
| `ACTION_SEMANTICS_UNCERTAIN:actions` | 首次动作未满足原有“对象、动作、检查内容”有界规则；`bench.md:11` 有直接动作，旧 top3 已覆盖。 | 具体动词/对象写法无法还原；只补可信字段填写说明。 |
| 两个 `CHOICE_SEMANTICS_UNCERTAIN:input.choices` | 首次两个选项不符合原有非数值有界词形；旧 top3 不含两个直接观察句，完整来源分别在 `bench.md:15`、`:17`。 | 不能断言真实模型具体选项措辞；有界检索扩展让原句进入候选依据。 |
| `INTERPRETATION_UNCERTAIN:interpretation` | 首次候选带自由解释；WP-10 原规则明确不授权自由解释，即使引用存在也不等于诊断语义获准。 | 解释的内容及依据无法还原；提示要求模型不要提出无支持解释或返回 `need_input`，没有在代码中静默删除该字段。 |

首次 `propose_step` 通过 schema 解析，但业务校验为 `needs_input`；唯一修复候选为 schema 有效的 `need_input`，修复额度已使用，仍未发布。这里有证据证明“原始首轮检索漏掉工况与选项所在块”，**没有证据**证明所有拒绝均由检索造成，也没有证据证明该合成资料天然不足以形成检查。

## 最小改动与安全边界

- `backend/app/agents/runner.py`：首轮仍经可信 `ToolExecutor` 和冻结 manifest 搜索，top_k 从 3 增至 5；对前两个命中各调用一次现有 `get_evidence_context(neighbors=2)`。只接受同一文档版本和索引的块、去重且最多 12 块；任一工具失败或版本/index 不符则明确失败，不退回不完整来源。扩展后再次检查原 120 秒 turn 期限；原工具权限与总/检索预算不变。
- 同文件提示只补通用字段角色：每个事实字段用有出处的完整句，位置含对象和空间关系，前提含工况，动作含对象/操作/检查内容，选项为原文支持的非数值观察；自由解释不能靠引用自动获准。没有写死 P01 答案、改变 WP-10 校验、车型适配、规格、证据归属或 publication/fencing。
- `tests/unit/test_diagnosis_slice_context.py`、`tests/integration/test_wp11_candidate_diagnostics_integration.py`、`tests/integration/test_diagnosis_slice.py` 增加正常与误放行反例：上下文去重、跨版本及工具错误拒绝；实际 runner 接线；缺工况、改写方位、无支持动作、无支持选项及自由解释仍被拒。`tests/live/test_diagnosis_slice.py` 的免费预检在隔离库使用本地工具模式核对冻结版本的五类来源句。
- `scripts/probes/seed_diagnosis_slice.py` 只支持隔离 localhost URL 与受限运行记录；新增 `scripts/probes/diagnosis_slice_continuation.py` 在浏览器观察前准备来源绑定，随后等待真实入库观察，沿用原 child run 的 created_at 与 120 秒期限完成**一次免费夹具**续轮。两者均不调用模型。

## 实际验证与失败保留

新隔离库 `xiutu_test_diag_slice_fix_eab0eae398e1`、独立 storage/构建及受限 `.test-runs/diag-slice-fix-eab0eae398e1464d9000e2acc8228f15/` 用于本轮；日志保留在该目录，含 `targeted.log/xml`、`targeted-envfix.log/xml`、`bge-free.log/xml`、`bge-free-fix.log/xml`、`bge-browser.log/xml`、`field-boundary.log/xml` 及浏览器/续轮记录。该目录不进入交付哈希，不复制私有 token 或 trace。命令中的环境变量均指向这次隔离库。

| 命令/范围 | 退出码和结果 | 证据版本说明 |
| --- | --- | --- |
| `python -m pytest tests/unit/test_diagnosis_slice_context.py -q` | 0；3 passed | 新有界来源单元正反例。 |
| 首轮受影响集成选择（未设置 `APP_MODE=test` 与隔离 `DATABASE_URL`） | 1；3 passed、5 failed | 配置错误原样保留于 `targeted.log/xml`，不计业务回归结论。 |
| 同 5 个受影响实例，设置 `APP_MODE=test` 与本轮隔离 `DATABASE_URL` | 0；5 passed | `targeted-envfix.log/xml`；没有把两轮合写为一次 8 项通过。 |
| 首轮 `tests/live/test_diagnosis_slice.py` 免费 BGE 预检 | 1；`MCP_CONFIG_UNAVAILABLE` | 免费预检误继承远端工具模式；`bge-free.log/xml` 保留。 |
| 修正免费预检模式后，仅同一受影响实例 | 0；1 passed | `bge-free-fix.log/xml`。 |
| 增加隔离浏览器受限运行记录后，仅同一免费预检实例 | 0；1 passed | `bge-browser.log/xml`；这是最新免费浏览器准备版本。 |
| `tests/integration/test_diagnosis_slice.py` 的新增字段正反例 | 0；1 passed | `field-boundary.log/xml`；合法准确引用通过，五类误放行仍拒绝。 |
| `.venv/Scripts/ruff.exe check --no-cache` 对本轮变动 Python | 0；all checks passed | 最终静态检查。 |
| `npm run typecheck`；`npm run build -- --outDir <隔离目录>` | 均 0 | 私有 typecheck/build 日志；未覆盖 `frontend/dist`。 |

浏览器经本轮 `http://localhost:5204`（与用户 `127.0.0.1` Cookie 主机隔离）读取新库：确定性 P01 当前检查先发布；在页面选择有来源的“外观完好”并提交，观察入库、revision=2，生成 child run。预备好的免费续轮脚本在 child 创建后 **0.114703 秒**领取，原 WP-10 校验通过，单条 publication 提交 Q02 当前检查，revision=3。浏览器刷新后仍看到同一已保存 P01 观察、同一 Q02 步骤、来源及 `waiting_input`；页面明确标为“确定性夹具·非AI”。`continuation-result.json` 记录 publication_count=1。旧隔离库中原过期 run 仍为 `failed/MODEL_TURN_TIMEOUT`、publication=0；本轮没有改写其 created_at、重置 run 或延长正式期限。5204 本轮进程经 PID/路径/创建时间核对后已停止，用户 5180/5196 未操作。

## 结论与下一门槛

免费证据显示：原文有可直接引用的合成检查句；原首轮 top3 遗漏了工况与选项，扩展后的可信工具路径把它们带入同一冻结资料范围，误放行门禁未放宽；及时启动的免费续轮可发布并跨刷新读回。**这不能证明真实 DeepSeek 的首轮会选对引用或字段，也不能证明真实模型在观察后发布下一步。**历史真实失败候选的逐字根因不可还原，若后续再做真实验证，应沿用既有限额与私有有限诊断，只由当次证据判断。

切片继续 **BLOCKED**；STATUS 本轮不改。真实资料仍 `NOT_MET`，DKVB 精确适配缺项、真实模型发布、正式维修效果与生产恢复均未验证。旧 worker 首次失败根因仍未确证。本报告是实施者免费整改记录，不是审核通过或用户接受。
