# WP-11 有界真实诊断验证 r2：价格门禁已修，最坏预留不足而停止

时间：2026-09-20（Asia/Shanghai）。本轮根据用户明确授权移除“价格核验到期即拒绝”的固定日期门禁，先免费验证，再核对原共享 ¥5 账本。**没有发起新业务 turn、真实模型请求或 MCP 调用，候选校验的实际拒绝原因仍未取得；WP-11 保持 BLOCKED。**这不是上一轮 r1 阻断记录的改写。

## 变更及价格依据

- `backend/app/infrastructure/model_gateway.py` 仅删除按 `2026-09-20 00:00 UTC` 抛出 `MODEL_PRICE_RECHECK_REQUIRED` 的分支；没有改模型/API目标限制、共享账本、原子预留、锁后期限复查、SDK `max_retries=0`、429/5xx 有限重试、单 turn 次数、一次候选修复或 120 秒门禁。
- 新增 `tests/unit/test_wp11_price_gate.py`，覆盖过原截止日期后付费模式仍走预算、未知模型、累计超额、配置错误、预留后过期以及输出额度。测试使用合成 key、替身适配器和独立临时账本，没有网络请求。
- `docs/runbooks/models.md` 更新价格说明。2026-09-20 核对 [DeepSeek 官方人民币价格表](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/)：`deepseek-flash` 高峰且缓存未命中输入 ¥2／百万 token、输出 ¥8／百万 token，现有保守系数无需改动；见 [price-check.json](evidence/wp-11-live-diagnostic-r2/price-check.json)。官方保留调价权，后续操作仍需核价。账本预留、usage 估算均不是平台账单，固定价格估算不能保证平台实际扣款恰好不超过 ¥5。

## 免费验证与停止计算

在 `E:\Work\xiutu-v5` 执行 `ruff check --no-cache backend/app/infrastructure/model_gateway.py tests/unit/test_wp11_price_gate.py`，退出码 0。随后执行：

`python -B -m pytest -p no:cacheprovider -q tests/unit/test_wp11_price_gate.py tests/unit/test_wp11_model_limit.py tests/unit/test_wp09_remediation.py`

退出码 0，**15 passed，6.55 秒**；命令、时间、独立临时目录、JUnit 和原始输出见 [free-run.json](evidence/wp-11-live-diagnostic-r2/free-run.json)、[free.xml](evidence/wp-11-live-diagnostic-r2/free.xml)、[free.log](evidence/wp-11-live-diagnostic-r2/free.log)。本轮没有重跑上轮 449 项完整入口；该结果仍仅属于上轮源码版本。

锁定读取**原共享账本**的聚合字段：累计上限 ¥5，已预留 ¥1.296968，剩余 ¥3.703032，历史调用记录 11 条。WP-11 服务端请求上限为 100,000 UTF-8 字节、输出上限 1536 token；现有保守公式每次输入上界 `100000×4+4096=404096` token，峰时预留上界 `(404096×2+1536×8)/1000000=¥0.820480`。单 turn 网关最多 5 次模型尝试（包含有限重试），因此整轮最坏预留为 **¥4.102400**，比剩余额度多 **¥0.399368**。见 [budget-preflight.json](evidence/wp-11-live-diagnostic-r2/budget-preflight.json)。这是代码允许的保守最坏值，并非预期用量或平台账单；前次真实 turn 的较低实际预留不能替代本次最坏值。

按本轮“原 ¥5 额度不足则停止”的明确条件，**未运行** `tests/live/test_wp11_dkvb.py`，没有创建隔离库/storage/MCP/worker/业务 turn，也没有新的私有候选 trace。因此没有本轮 run 状态、publication、独立进程读回、候选类型或 issue `code/path`；不能把免费合成用例当成本轮真实拒绝原因。结束再次核对已预留金额仍为 ¥1.296968、调用记录仍为 11 条，见 [final-check.json](evidence/wp-11-live-diagnostic-r2/final-check.json)。共享账本没有新预留、usage 或平台账单可核对；未重置、复制或输出完整账本。

## 状态及保留项

STATUS 仅反映此轮最小价格门禁修正与预算停止点。WP-11 仍 **BLOCKED**，未审核、未接受。上轮真实请求的 `DIAGNOSIS_PROPOSAL_NEEDS_INPUT` 具体原因和旧 worker 首次失败根因仍“未确证”；真实资料 `NOT_MET` 及历史未确认问题保留。没有修改 WP-10 校验、提示词或维修资料；没有操作 5180/5196、旧项目、接受记录、历史迁移或 Git index，也没有提交、推送或进入 WP-12。
