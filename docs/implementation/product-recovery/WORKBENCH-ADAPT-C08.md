# WORKBENCH-ADAPT-C08：C07 契约的一次真实模型体验

状态：`FAILED_VALIDATION_NOT_ACCEPTED`，2026-09-24。**实际真实生成请求恰为 1 次，未重试、未修复性二次调用、未调用备用模型。** 模型返回后被服务端校验拒绝；没有发布有效建议。本记录不是用户对真实建议质量的验收。

## 调用前核对

- 正式目标：[独立合成 DEMO 病例](http://localhost:5215/workbench/97812694-5339-4e59-badc-d87a9bc5c431)，case ID `97812694-5339-4e59-badc-d87a9bc5c431`，revision 42，绑定 `2.2.1-b02` / `synthetic=true` / `formal_usable=false`；41 条当前有效观察均明示为模拟、非用户实测。本次允许范围仅 `supplement_or_handoff`。旧替身分析 `d88829d4-a817-4154-b04e-9ffbcda79c9d` 保留；本病例此前没有真实分析或在途任务。原 C03/C05 两条真实失败分析在另一病例中，状态未改。
- 项目已有配置通过原加载器确认：提供方 DeepSeek、官方接口 `https://api.deepseek.com`、密钥存在；项目 `.env` 默认型号仍是旧 `deepseek-chat`。**未修改 `.env`**，仅本次精确限定的本地 API/worker 进程在内存中覆盖为用户授权的 `deepseek-flash`。运行中正式 API 再次回报 `real/deepseek/deepseek-flash`、`dkvb-c07-v1`、输出上限 4096 tokens、输入上限 48,000 字符、单逻辑请求最多一次。
- C07 快照只使用本病例有效事实、派生/缺项、两段冻结手册摘录 `C01-SRC-CHARGE-AIR-P1/P5` 及唯一受控检查 `CHECK_CHARGE_AIR_HOSE_SEATING_LEAK`。图片仅为查看引用，没有作为图像输入。按**网关实际 schema 消息序列化**计算，本次完整模型消息为 36,802 字符，低于 48,000；该预算计数与 `generate_structured_once` 共用 schema 文本生成函数，定点测试通过。没有静默删去异常或缺项。
- 官方 [模型列表](https://api-docs.deepseek.com/quick_start/pricing/)与 [JSON 输出说明](https://api-docs.deepseek.com/guides/json_mode/)支持 `deepseek-flash`、Chat Completions 的 JSON 输出和大于本次 4096 tokens 的输出上限。网关本次路径为 SDK `max_retries=0`、`retry_transient=False`、不执行结构修复调用；worker 对病例分析不自动重投递，分析 `dispatch_state` 在发出前保留一次性占用。隔离库迁移为 `0017_case_analysis_diagnostics`，调用前无排队病例分析任务。

## 一次正式请求与拒绝结果

使用正式 `POST /api/v2/cases/{case_id}/analyses`，以病例 ID、revision 42、付费确认及精确限定的单次幂等键发起一次请求。新分析 ID `9d38a39d-0c61-428a-beae-53316ce9ceb9`，run ID `9d86a358-1569-4807-8527-4699acb00931`，冻结契约 `case-advice-proposal-c07-v1`。原账本仅有该分析的 `:1` 一条真实调用：`received`、`finish_reason=stop`，模型回报输入 15,877 / 输出 1,660 / 合计 17,537 tokens；实际费用没有可靠结算数据，记为**未知**。

响应 3,173 字符 / 5,441 UTF-8 字节，受限诊断完整留存、未截断；JSON 解析及提案结构校验成功。服务端组装并校验时拒绝，分析持久化为 `failed`、`content_json` 为空：

- 顶层：`ANALYSIS_UNSUPPORTED_OPERATION`
- 阶段：`business_validation`
- 规则：`text.unsupported_operation`
- 字段：`steps[1].action`
- 允许范围：`supplement_or_handoff`

该自由步骤的短片段是“补充记录 AIR-14（加压过程是否遵守最大 0.5 bar）……实际情况或未执行原因”。其中“加压”来自被引用的问题名称，前文实际要求补充记录；词法校验把它当成执行加压，**首处疑似误拦**。但对原响应做只读、逐字段隔离诊断，另发现 `uncertainty` 中包含非冻结测量的编辑性演示阈值，`safety_notice` 中自行写入 `0.5 bar` 操作限值，均触发 `text.unsupported_parameter`。后者涉及受控范围外的参数表述，不能因为首处疑似误拦就发布。逐字段探针不等于整份响应在修正首处后必然通过；本轮没有改契约、删步骤或重跑模型。

仅就**未发布**回复做效果观察：概述引用 AIR-07/AIR-08 接头异常，`supported_directions` 为空，共提出 5 个步骤；结构化事实、缺项和摘录 ID 均指向本次冻结对象，具有病例针对性。但有上述校验问题，不能把这些步骤展示为有效维修建议，也不能据此认定真实 AI 效果已验收。

## 收尾

真实请求结束后立即停止短时实例，并用原启动脚本恢复同端口的替身 API/Web/worker。正式 API 再读回 `stub`、`paid=false`、输出上限 1536；默认启动环境把临时注入的 `DEEPSEEK_API_KEY` 置空。普通页面后续点击不会继续付费。目标病例仍为 revision 42、41 条有效观察；新真实失败与旧替身成功分列，未把模型结果写入观察、实际处理或复检。C03/C05 失败分析保持原样。未重建数据库/数据卷，未操作 Docker/WSL，也未进入阶段 D。

本次仅为核算**实际**完整输入预算而将网关的 schema 文本生成抽成共用函数，并增加定点测试；没有放宽 C07 业务校验。相关定点 `31 passed`。下一步若要修复上述字段误拦与参数边界，需要单独工作包；任何新真实生成都需新的明确授权。本轮在失败结果处停止。
