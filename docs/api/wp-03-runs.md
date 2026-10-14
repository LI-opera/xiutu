# WP-03 任务 API

以[WP-03契约](../implementation/phase-02/wp-03-contract.md)及运行时/openapi.json为准确请求/响应依据。所有路径前缀/api/v2。

| 路径 | 请求 | 响应 |
| --- | --- | --- |
| GET /runs/{id} | cookie | 200 RunSnapshot；owner越权404 |
| GET /runs/{id}/events | cookie；可选Last-Event-ID | text/event-stream；持久id/type/概要JSON；游标错误400 |
| POST /runs/{id}/cancel | cookie、Origin、CSRF、Idempotency-Key；无body | 202 RunAction，已终态200 |
| POST /runs/{id}/retry | 同上；JSON expected_revision（case必需，无case为null） | 202新run及parent_run_id；无剩余预算/不允许状态409 |

SSE缺Origin允许同源EventSource；若携带必须匹配配置；跨站Fetch-Metadata拒绝。15秒注释心跳、按ID重放、终态关闭；会话过期/注销关闭，重新连接需登录。消费端按ID去重并查询快照，不靠事件构造唯一业务事实。

active_run摘要仅任务id/kind/status，report_gate仍不可用。无诊断start/reassess和资料导入入口。OpenAPI快照保存在本包evidence/openapi.json。
