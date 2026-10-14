# WP-12 观察、区域与更正 API（隔离合成技术范围）

所有写请求使用登录 Cookie、同源 `Origin`、`X-CSRF-Token`、`Idempotency-Key`。`case_id` 必须属于当前操作者；跨 owner 统一 404。请求模型 `extra=forbid`；不接收调用方指定 owner、资料范围、业务状态或观察 ID。读取结果不代表正式维修结论。

## 提交当前检查

`POST /api/v2/cases/{case_id}/observations`：

```json
{"expected_revision":1,"graph_epoch":0,"step_id":"<GET /diagnosis 的 current_step.id>","kind":"choice","choice_index":0}
```

对表示已检查状态的选项，还须提交 `conditions:{"engine":"off"}` 等与步骤前置条件一致的实际工况；未确认工况返回 422，不能凭资料中的前提替用户声称已满足。测量输入改用 `kind:"measurement"` 和 `measurements:[{"spec_id":"...","value":"1.0000000000000000001","unit":"V","conditions":{"engine":"off"}}]`；复合输入须同时含 `choice_index` 和全部 `measurements`。无法测量用 `kind:"unavailable", reason:"..."`，不得传 choice 或 measurements。单位是受控白名单，十进制值保留字符串精度。选择必须来自当前步骤；规格必须已审核、当前有效且属于该 case，工况须与批准规格一致。

成功返回 202，包含 `run_id, observation_id, case_revision, graph_epoch, status`。观察、步骤完成、revision、下一 run/job、事件和幂等响应在同一事务。相同 key/请求重放原响应；同 key 异请求 409，不同 key 重答已完成步骤 409。`REVISION_CONFLICT` 的 `error.details.current_revision` 可用于重新读取。公开旧 `/diagnosis/resume` 返回 `OBSERVATION_SUBMIT_REQUIRED`，不接受任意预存观察 UUID 推进。

`GET /api/v2/cases/{case_id}/observations` 返回至多 100 条不可变历史，包含 `supersedes_id`、`effective`、`correction_reason`。`GET /api/v2/cases/{case_id}/diagnosis` 返回 revision、epoch、实际当前步骤或 null；后续 run 的状态和 SSE 仍使用已有 `/api/v2/runs/{id}` 契约。

## 区域与更正

`GET /api/v2/cases/{case_id}/diagnosis/areas` 仅浏览，不写观察或增加 revision。`POST /api/v2/cases/{case_id}/diagnosis/areas/{area_id}/activate` 请求 `expected_revision,graph_epoch`；已有该区域待答步骤时返回 200 只读，否则只有无其他待答步骤/活跃任务时才创建 202 生成 run，run 绑定 `area_activation` 引用，不伪造观察。`POST .../conclude` 同一请求字段，返回 201 保守区域卡：`unknown/conflicting/needs_input`，重新检查观察来源与比较当前有效性；这些状态不表示确认、排除或报告可发布。当前无可信区域结论发布、retired 合并操作。

正常图在本区全部检查已回答且观察/来源仍有效时，若发布另一合格区域的检查，会在同一事务将旧区域标为 `completed` 并生成唯一 `unknown` 卡；经 WP-10 校验的 `conclude_area(assessment=unknown)` 也可触发服务端自动收尾，不创建假步骤。该 run 以 `succeeded` 结束，`GET /diagnosis` 可见下一 run 的 `analyzing` 或无合法下一项时的 `needs_review`。仅回答一次、`need_input`、不可测量、冲突或失效来源不会收尾；阻断码通过原 run 查询/SSE 查看。旧 `conclude` 仍可读取/记录待补摘要，但它本身不标记区域完成。当前没有可信自动确诊/排除或 retired 合并入口。

`POST /api/v2/cases/{case_id}/observations/{observation_id}/correct` 在原提交字段之外要求非空 `correction_reason`。有活跃 run 先返回 `RUN_ACTIVE`；成功 202 追加 `supersedes_id` 观察，旧事实、步骤和区域卡保留历史并标记需复核，`graph_epoch+1` 且新 workflow 排队。旧 worker 不能向新 epoch 发布。历史读取不等于当前授权；资料撤销后必须重新检查。

免费可运行演示：配置独立 `xiutu_test_*` 数据库且令 `DATABASE_URL=TEST_DATABASE_URL`，然后运行 `python -B scripts/demo_wp12.py`。该脚本调用真实 HTTP TestClient 与 PostgreSQL fixture，只证明合成事务行为，不调用 DeepSeek，也不代替 WP-12 人工审核。
