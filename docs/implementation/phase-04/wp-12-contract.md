# WP-12 实施契约（2026-09-20）

范围：合成且精确适配资料下，观察提交、区域激活/结论、事实更正与恢复。复用 WP-11 的 run/job、图、checkpoint、租约和发布；不实现报告、正式观察表单前端或真实维修推断。DKVB 精确适配与真实模型发布仍不在通过范围。

## API 与事务

- `POST /api/v2/cases/{case_id}/observations`：认证、Origin/CSRF、`Idempotency-Key`；请求为 `expected_revision, graph_epoch, step_id, kind, choice_index?, conditions?, measurements?, reason?`。`choice` 的 `choice_index` 必须命中已发布选项；已检查的状态选项需要用户提交与有据前置工况相符的 `conditions`，不能仅从资料前置句自动认定实际工况；`measurement` 的规格必须是已审核且当前有效的 `spec_id`，使用原 Decimal 比较门禁验证 quantity、unit、conditions；`composite` 必须提交所要求的选择和测量；`unavailable` 必须含非空原因。请求不接收 owner、资料范围、状态或观察 ID。返回 202 的 observation/run/case revision。选项原文“未检查”仅记为已选，不自动变成已检查/正常。
- 对规范化请求先在同一事务锁/插入幂等记录，再按 owner 锁、case 行、step、原 run 的顺序检查；成功写不可变观察、完成步骤、revision+1、入队诊断 run/job、事件与幂等响应。相同 key/hash 重放原 202；异内容 409。不同 key 重答、旧 revision、错 step、跨 owner 均拒绝。409 `REVISION_CONFLICT` 附当前 revision。
- 公开 `POST .../diagnosis/resume` 不再接受任意预存 observation UUID；可信内部恢复仍可从数据库引用读取，必须核对 observation 对应正式提交 run 及 step/epoch。模型/检索/MCP 在事务外。
- `GET .../diagnosis` 返回当前检查与区域状态。纯浏览/切换已有区域不写事实；`POST .../areas/{id}/activate` 仅对无待答步骤的待生成区域创建含 `area_activation` 引用的 run，不伪造观察。
- `POST .../observations/{id}/correct`：原因、旧 observation、`expected_revision`，活动 run 时拒绝；追加 supersedes 行、旧 epoch 步骤/结论失效、epoch+1、新 workflow/run 分析。历史可读，不原地改旧事实。

## 状态与结论

同一 case 最多一个实际 waiting 步骤；步骤回答后进入 completed，待分析 run 取得下一检查或保守的待补状态。区域结论为独立持久记录，限定本区域、有效观察及其当前有效来源；`unknown/conflicting/needs_input` 不等于正常、排除或确认。无可信规则时，不提供确认/排除结论。更正保守地使全部旧区域结论、后续步骤和报告状态 stale；旧 worker 由 graph_epoch/revision/fencing 阻断。

### A411 区域终态补充（0011）

- 单次观察提交、步骤从等待列表消失、`need_input` 或模型自报“已完成”都不是区域终态。正常图仅在两种额外事件中尝试收尾：发布**另一合格区域**的已校验检查，或在已保存观察后收到 WP-10 校验通过的 `conclude_area(assessment=unknown)` 明确结束意图。模型的 finding/assessment 不直接写入卡片；服务端从数据库重新计算。
- 同一 owner/case/epoch 下的旧区域必须处于 active，所有步骤已回答、有效观察均 `checked=true`，没有未回答步骤、不可测量、同规格同工况冲突、失效引用/比较或其他活动诊断任务。冻结 manifest 也须仍可用。条件不满足则当前发布事务回滚，case 留 `needs_review`，run 返回具体阻断码；旧区域不标 completed，也不写“正常/排除/确诊”。
- 通过时在原 worker 物理锁连接与 case/job/run 行锁下写 **一张**该区域 `unknown` 卡、`area.completed` 事件和区域 completed 状态；下一检查或 area_close 的 run/publication/case revision 与之同一事务提交。最后 SQL 后继续使用数据库时钟及原租约快照校验，失败整体回滚。终态后的 checkpoint 仅在同一 publication 存在、原 token/连接/租约仍有效且 case 行锁下 graph_epoch 未改变时可写；更正先提交则旧 checkpoint 拒绝。唯一 `(area_id,created_revision)` 与同一 turn 的 publication key 阻止重放重复卡；同键异内容拒绝。
- 已有 pending 区域按创建顺序选择；发布跨区域检查不得越过更早的 pending 区域。显式 area_close 将最早 pending 区域以可信 `area_activation` 入队，否则保守停在 `needs_review`，不生成假检查。新区域一旦加入也计入未完成集合。当前没有受信的 retired 合并/重复写入口；任何 retired 行都**不**视为已完成，缺少受信合并事件时拒绝收尾，不能凭 `retired_reason` 跳过待测。
- 原显式 `POST .../areas/{id}/conclude` 保留兼容：可在非活动 run 时读取保守待补/冲突卡，但不单独将区域标为 completed。没有批准的可信结论规则时 `unknown` 卡不授权报告或维修结论。`0011_area_closure` 只扩展 graph checkpoint 的 `completed` 相位，不更改 0001—0010。

## 验证顺序

先隔离 PostgreSQL 中进行 A410—A414 定点：幂等、所有权/步骤/规格输入、无法测量、区域只读/激活、冲突与分支、更正/旧 worker、跨进程恢复；再运行最终源码一次标准完整入口。仅合成资料和确定性夹具，不付费调用。失败日志独立保存，不覆盖历史记录。用户实例 5180/5196、旧迁移、Git index 不变。
