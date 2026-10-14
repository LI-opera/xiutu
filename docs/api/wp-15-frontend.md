# WP-15 正式诊断工作台接口绑定

WP-15 不增加平行诊断后端。正式页面从 `docs/api/openapi.wp14.json` 生成
`frontend/src/generated/api-schema.ts`，并调用既有 `/api/v2` 接口。

## 读取

- `GET /cases/{case_id}`：病例、revision、graph epoch、冻结资料范围、活跃任务。
- `GET /cases/{case_id}/diagnosis`：当前步骤、最近任务及等待状态。
- `GET /cases/{case_id}/diagnosis/areas`：区域状态及保守结论卡。
- `GET /cases/{case_id}/observations`：不可变观察历史；每项附原步骤的输入 schema 与工况，供受控更正表单使用。
- `GET /cases/{case_id}/reports/gate`、`GET /cases/{case_id}/reports`：服务端报告门禁与历史报告。
- `GET /evidence/{evidence_id}`：冻结版本、定位快照、当前有效性及结构化 `source_access`。PDF 只使用证据绑定版本和可信物理页；缺页、映射缺失、`needs_ocr` 和无独立页图分别显式返回，不回退最新版本或第一页。

## 写入

- `POST /cases/{case_id}/diagnosis/runs`：显式启动诊断。
- `POST /cases/{case_id}/observations`：按当前步骤 schema 提交 choice、measurement、composite 或 unavailable；带 `Idempotency-Key`、CSRF、expected revision 与 graph epoch。
- `POST /cases/{case_id}/observations/{observation_id}/corrections`：追加更正，不改写旧观察。
- `POST /cases/{case_id}/diagnosis/areas/{area_id}/activate`：仅激活服务端判定可激活的 pending 区域。
- `POST /cases/{case_id}/reports`：用户主动请求进度报告；最终报告仅在 gate `allowed=true` 时启用。

## SSE

`GET /runs/{run_id}/events` 使用 cookie 会话。客户端保存最后一个事件 ID，重连发送
`Last-Event-ID`；`reset_required` 后清除游标并先重新读取 HTTP 快照。事件 ID 去重，终态事件关闭流。
路由、病例或 epoch 改变后，旧流即使迟到也不能更新当前页面。
snapshot 临时失败进入最高 5 秒的指数退避，并向当前页面暴露恢复错误；恢复成功后清除错误并继续原游标，终态则停止。

## 客户端写入幂等

开始诊断、区域激活、观察提交、更正、取消和两类报告请求都按接口、目标 ID、revision、graph epoch 与规范化 body 持有稳定键。歧义网络失败复用原键；成功或明确 409 后清理。报告响应的 `run_id` 接入独立 RunStatus，终态重新读取报告列表、gate 与病例快照。

## 边界

前端不生成身份、revision、epoch、资料范围、规格或结论。`unknown` 只表示待补；来源失效时历史仍可读，但不能显示为当前依据。409/413/422、超时、模型/MCP/worker 失败均保留服务端错误码和 trace id。
