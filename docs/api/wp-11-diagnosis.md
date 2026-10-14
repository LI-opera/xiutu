# WP-11 诊断任务基础接口（待审核）

本包在已有会话和run/SSE之上增加单步诊断图。当前检查是经WP-10候选校验后的**建议检查**，不是已确诊结论。仅使用会话冻结且当前仍有效的资料；真实资料门槛仍为NOT_MET。

| 接口 | 请求/结果 | 保护 |
| --- | --- | --- |
| `POST /api/v2/cases/{case_id}/diagnosis/runs` | JSON `{"expected_revision":0}`；202返回run ID和queued状态 | 登录Cookie、Origin、CSRF、Idempotency-Key、owner/revision/资料范围 |
| `GET /api/v2/cases/{case_id}/diagnosis` | 当前case revision/epoch/status及唯一waiting_input步骤，或null | 登录与owner；跨owner 404 |
| `POST /api/v2/cases/{case_id}/diagnosis/resume` | JSON `{"expected_revision":1,"observation_id":"UUID"}`；202返回新run | 同启动保护，且观察必须已在数据库中保存并关联当前步骤 |
| `GET /api/v2/cases/{case_id}` | 原快照附`current_check` | 登录与owner |
| `GET /api/v2/runs/{run_id}`、`.../events` | 原任务查询与SSE；发布产生`run.waiting_input` | 原run所有权与SSE游标规则 |

同Idempotency-Key同请求重放返回原状态码/响应；异请求冲突。创建与resume均不接受客户端owner、corpus、epoch、工作流权限、规则或观察正文。WP-12尚无正式观察提交API；`resume`只接收既有数据库观察UUID，不能拿任意请求JSON当观察事实。测试夹具直接入库的观察不代表WP-12已完成。

worker在原租约/advisory锁连接上发布`diagnosis_steps`、`diagnosis_publications`、run状态、case revision和事件；持久检查点只持进度/引用。发布后checkpoint失败可从publication和progress恢复等待状态。失败任务保留错误码，不能被表示成已发布。当前诊断显式`retry`拒绝，以免新run绕过本轮预算；无资料、候选校验失败、模型预算/配置或MCP错误尚无正式用户待补交互。没有报告发布或观察修改能力。
