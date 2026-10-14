# WP-13 报告 API（待审核）

报告仅由已登录用户主动请求。`GET /api/v2/cases/{case_id}/reports/gate` 返回最终报告的 `allowed`、`blocking_items`、当前 revision/epoch。`POST /api/v2/cases/{case_id}/reports` 接受 `{"kind":"progress|final","expected_revision":N}`，要求现有同源 Cookie、`Origin`、`X-CSRF-Token` 和 `Idempotency-Key`。返回 202 的 `report_id` 与 `run_id`；同键同内容返回原响应，同键不同内容冲突。最终门禁不满足返回 409 `FINAL_NOT_READY` 和结构化 `error.details.blocking_items`，不入队。

`GET /api/v2/cases/{case_id}/reports` 与 `GET /api/v2/cases/{case_id}/reports/{report_id}` 仅 owner 可读，返回报告内容、状态及实时 `current_validity`。旧 revision、结论或来源变化会显示 stale；历史仍可读。任务状态和事件沿用 `/api/v2/runs/{run_id}`。普通诊断流程不会自动请求报告。

进度报告允许 `unknown` 结论，列已保存检查和观察、未完成区域、资料/适配缺项与不能下的结论；没有确定换件清单。最终报告由六项服务端门禁及发布前重验控制，动作必须出自当前可信结论卡的结构化依据；有效引用本身不能授权任意说法或换件。本包没有将 `unknown` 卡升级为 supported/ruled_out 的公开入口。当前真实 DKVB 资料和第二项检查尚不满足最终报告门槛。
