# 可体验诊断闭环切片契约（WP-13 前）

本切片不改变 WP-00—12 的限定接受范围，也不启动 WP-13—17。只复用现有 case、diagnosis run、worker、ProposalService、只读业务工具/MCP、发布与观察事务，在现有 React 应用提供最小交互。真实模型输出与免费确定性夹具必须分开标注。

## 入口与顺序

用户在已登录应用选择冻结了合格合成资料的 case，提交 `POST /api/v2/cases/{id}/diagnosis/runs`（`expected_revision`、CSRF、Idempotency-Key）；页面以 `GET /api/v2/cases/{id}/diagnosis`、`GET /api/v2/runs/{id}`、`GET /api/v2/cases/{id}/observations` 读取真实状态。worker 经现有资料检索、模型网关、WP-10 校验和 WP-11 原子发布，进入 `waiting_input` 后页面才展示当前步骤。证据使用已授权 `GET /api/v2/evidence/{id}` 和来源 content 接口定位。观察使用 `POST /api/v2/cases/{id}/observations`，提交当前 revision、graph_epoch、step_id 以及已发布输入 schema 所允许的选项、工况、测量或 unavailable 原因。提交成功后服务端原事务保存观察并生成下一 run；刷新只从数据库恢复状态。

页面不预设下一检查或模拟任务成功。异步响应绑定当前 case 与请求代次；切换 case 或新请求后旧响应不得覆盖。409 显示并要求重取最新 revision，不自动把旧选择套到新步骤。当前检查的 `accepted` 只表示其经过原提案校验，不表示维修结论。

## 资料与费用边界

先在新隔离 PostgreSQL 中免费检查资料车型范围、引用及位置/工况/动作/选项是否足以通过原 WP-10 门禁。DKVB 缺失精确年款/发动机系列不能补造。若使用完整合成台架样本，显著标记 `synthetic=true, formal_usable=false`，不能替代真实 DKVB。若免费阶段无法形成有据检查，不发付费请求。

真实验证最多一个初始业务 turn 和它的一个观察后续 turn。2026-09-20 用户明确取消原共享账本的累计人民币 5 元拒绝上限；原账本经一次显式 v1→v2 迁移后继续计量，并保留旧授权和历史上限。每次请求仍先持久预留，保留每 turn 四次模型请求、120 秒、工具/检索及一次修复等门禁；不得初始化或重置账本。任何业务失败留下证据并停止本轮真实验证。fixture 发布与 DeepSeek 发布分别报告。此切片不生成最终报告、不升级 unknown 区域卡，不实现 WP-13 门槛。

## 验证与交付

受影响的后端事务/恢复测试、前端状态/类型检查/独立构建与隔离浏览器路径；成功、拒绝、幂等、刷新和两种已保存观察的后续差异分别核对。新实例与 5180/5196 的数据库、存储、主机 Cookie 和构建隔离。结果记入 `diagnosis-slice-result.md`，STATUS 单列切片状态。失败不得写作闭环成功。
