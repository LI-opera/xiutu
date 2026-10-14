# WP-13 本地报告运行说明

先按现有运行说明启动隔离 PostgreSQL、API 与 worker，并将 `DATABASE_URL` 指向自己的 `xiutu_test_*` 库；迁移到 `0012_reports`。不要连接用户 5180/5196 的数据库或存储。报告请求只由已认证的 owner 发起；进度报告在 `unknown` 病例可用。查看 `/api/v2/cases/{id}/reports/gate` 的阻断项，再用当前 revision 请求相应 kind。通过 `run_id` 查询任务，以 `report_id` 读取正文和当前有效性。修改观察或撤销资料后，重新读取历史报告会显示失效，必须重新请求，不能把旧正文当当前报告。

最终报告图仅消费已冻结的范围、当前有效结论卡和引用。模型执行路径默认关闭；只有受控服务端明确启用 `XIUTU_WP13_PAID=1` 才会通过现有 DeepSeek 网关及原持续计量账本。本包不授权实际付费报告调用，自测使用 MockTransport。没有已审核的 supported/ruled_out 卡和可信结构化动作时，门禁或报告校验会拒绝确定维修建议。模型草稿校验失败保留失败记录，不会覆盖此前有效报告。
