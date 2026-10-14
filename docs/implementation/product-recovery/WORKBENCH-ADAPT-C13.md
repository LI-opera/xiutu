# WORKBENCH-ADAPT-C13 · C12 后一次真实在线验证

状态：`FAILED_VALIDATION_NOT_ACCEPTED`（2026-09-24）。本次确实完成了一次真实生成，但**没有发布有效分析**；不能把任务返回、旧替身建议或失败提示称为真实建议交付。未改契约、提示词、病例事实、资料或操作清单，不进入阶段 D。

## 调用与环境

- 正式体验页：[独立 C12 DEMO 病例](http://localhost:5215/workbench/1ff861f8-745d-49af-bb1e-7b436e606d2c)。病例 revision 42，41 条有效模拟观察，专题 `2.2.1-b02`，范围 `supplement_or_handoff`；此前仅有一条 `partial` 替身结果，无在途真实任务。分析完成后 revision 仍为 42，处理与复检事实未自动增加。
- 运行中的 API 与 worker 已通过 C12 替身记录和实际任务路径核对；冻结输出契约 `case-advice-proposal-c09-v1`，采用当前 C12 分层校验。冻结资料摘录为 `C01-SRC-CHARGE-AIR-P1`、`C01-SRC-CHARGE-AIR-P5`，受控清单仅 `CHECK_CHARGE_AIR_HOSE_SEATING_LEAK`；图纸未作为模型输入。
- 实际提供方 DeepSeek，模型 `deepseek-flash`，接口主机 `https://api.deepseek.com`，完整模型输入约 39,861 字符（上限 48,000），实际输出上限 4,096 tokens。SDK/网关重试关闭，worker 不重投递病例分析；精确病例、revision 与幂等键限定短时真实授权。
- 第一次正式 POST 被本地 CSRF 校验以 403 拒绝，未创建分析或模型请求。补齐合法 CSRF 头并重新只读预检后，正式接口返回唯一真实分析 `42f51091-6417-4f4d-8f80-0f8df68ac97a`、run `6662117d-cea8-44e1-98cd-443b3e27e712`。**实际真实生成请求数为 1**，没有模型重试或备用调用。
- 账本 `analysis_id:1` 记录响应 `received`、`finish_reason=stop`，输入 17,334、输出 1,805、合计 19,139 tokens。无可靠结算金额，费用未知。

## 发布结果与受限诊断

原始响应在本次受限诊断中完整保留、未截断（5,579 UTF-8 字节，SHA-256 `0f9152afd371d03cd2f3e3c38b1e7a1a617ee4ab64930a67975d2d7321f7c9f9`），解析后于业务校验拒绝：`summary` / `number.operation_limit` / `ANALYSIS_UNSUPPORTED_PARAMETER`。首个相关片段为“按演示阈值（250/150 hPa）呈现持续偏低模式”。它明确说“演示阈值”，因此存在**可能误拦**；但该数值是否被用作操作限值必须结合整段用途与冻结依据再判，不能在本轮直接放行。

同一响应的只读独立字段探针另报：`retest_plan` / `text.unsupported_operation`（建议在可比负荷下重新采集压力帧，当前清单未授权）；`supported_directions[1].limit` / `number.operation_limit`（将 250/150 hPa 明示为演示带宽而非手册限值，亦可能误拦）；`steps[0].request` / `text.unsupported_operation`（要求补记加压过程是否遵守 0.5 bar，属于补记录还是变相执行指令需看字段语义）；`steps[3].source_ids` / `source.applicability_unconfirmed`（跨区交接借用气路 P1，来源适用范围不足）。探针发现不能证明其余内容已整体合格，也不能代替发布路径；本轮不删改模型原文、不降低规则、不重新生成。

正式分析为 `failed`、`content=null`，原替身结果仍独立保存。正式 5215 Chrome 页面实际显示历史“真实模型生成 · failed · revision 42”，没有未经批准的建议正文；刷新后仍如此。页面顶部“模型替身验证 · 非真实 AI”表示**今后普通请求模式**，不是把这条历史真实失败改成替身。页面仍标记 `synthetic / DEMO / formal_usable=false`。未验证引用点击，因为本次没有可发布建议与引用。

## 收尾和边界

短时真实 API/Web/worker 已停止，再以原脚本和原端口恢复 `stub` / `paid=false`，运行子进程不再注入密钥；普通页面点击不会继续产生真实请求。原历史真实生成标识、失败状态、受限诊断与病例记录保留。没有第二次真实生成，也没有在本轮修正规则后付费重试。若后续处理数值表达与补记录语义，须单独决定并验证；本轮到此停止。

本轮新增仅用于限定授权窗口与只读核对的 `scripts/c13_preflight.py`、`scripts/c13_once.py`、`scripts/c13_status.py`、`scripts/c13_audit.py`；业务规则和页面代码未修改，未运行全仓回归或数据库迁移。
