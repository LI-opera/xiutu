# WP-15 完整诊断工作台联调与交互恢复结果

日期：2026-09-21  
状态：`IMPLEMENTED_NOT_ACCEPTED`  
契约：[wp-15-contract.md](wp-15-contract.md)  
证据：[evidence/wp-15](evidence/wp-15/)

## 实际交付

正式 `/workbench/:caseId` 已连接 WP-11—13 的真实病例、诊断、区域、观察、任务、证据和报告 API。页面支持：启动/恢复诊断、区域树、当前检查、choice/measurement/composite/unavailable 观察表单、运行状态与 SSE 恢复、区域结论、观察更正、进度报告及服务端最终报告门禁。服务端事实由 TanStack Query 持有；本地状态仅保存未提交表单和当前选择。

本包只增加 OpenAPI 响应声明和观察历史的只读输入 schema/工况字段，没有复制诊断、观察、发布、报告或资料门禁。身份、revision、graph epoch、冻结资料范围、规格和结论仍由服务端决定。旧 preview/hash 入口保留，5180/5196 未启动、停止、更新或部署。

主要文件：

- 后端响应声明：`backend/app/domain/schemas.py`、`backend/app/api/cases.py`、`backend/app/api/reports.py`。
- 观察历史适配：`backend/app/services/observation_service.py`。
- 工作台：`frontend/src/formal/pages/WorkbenchPage.tsx`、`frontend/src/formal/diagnosis/WorkbenchParts.tsx`、`run-events.ts`、`types.ts`。
- 视觉及入口：`frontend/src/formal.css`、`frontend/src/formal/components/AppShell.tsx`。
- 生成契约：`docs/api/openapi.wp14.json`、`frontend/src/generated/api-schema.ts`。
- 隔离入口与测试：`scripts/wp15_workbench.py`、`tests/unit/test_wp15_openapi.py`、`tests/integration/test_wp15_workbench.py`、`frontend/tests/wp15-workbench.test.tsx`。

## 确定性主路径

隔离 PostgreSQL 中的免费 E2E 使用明确 `synthetic=true`、`formal_usable=false` 的台架资料，经既有 ProposalService 校验、事务发布第一项检查、HTTP 提交观察、创建 child run、发布第二项有据检查，并从新读取路径恢复；最终报告 gate 保持关闭。命令 `pytest tests/unit/test_wp15_openapi.py tests/integration/test_wp15_workbench.py`：`3 passed`，exit 0，见 `final-backend-targeted.log`。单独 E2E 证据为 `deterministic-e2e.log`。

观察空值、工况、不可测原因、409 草稿保留、稳定幂等键、SSE 去重/重连/reset/stale-context、报告门禁和撤销 PDF 旧版本定位由最终前端 `33 passed` 覆盖，见 `final-frontend-tests-v2.log`。预览兼容测试为 `22 passed`，见 `preview-compat.log`，不冒称 24 项。

## 有界真实 DeepSeek 链路

免费路径通过后，只创建了一个真实初始 turn。合成台架资料经本地 BGE-M3、独立只读 MCP、DeepSeek、原 ProposalService 和事务发布得到：`waiting_input`、1 条 publication、6 个冻结范围内引用、4 次工具尝试、3 次模型请求；usage 三次均 reported。隔离浏览器随后按真实页面 schema 保存一项观察，病例 revision 由 1 变为 2，并只创建一个续轮。

唯一真实续轮读取该已保存观察，产生 1 条保守 `area_close` publication，run 为 `succeeded`，模型请求 3 次、工具尝试 6 次；没有发布第二项当前检查。刷新后页面仍显示观察、无当前步骤以及 `unknown` 待补卡。该结果符合资料缺少 P01→Q02 条件关系时的保守行为，不能写成“两步检查成功”、确诊、排除或最终报告就绪。

持续计量 v2 未重置：保守累计预留从本轮前 `3.734104` 变为首轮后 `4.257768`、续轮后 `4.833088`。这是本地预留；usage 估算与预留均不是平台账单。脱敏证据见 `live-sanitized.json`，私有有限 trace 留在受限 `.test-runs/wp15-live-20260921-r1`，未复制密钥、Cookie、提示、工具参数或完整账本。

## U508—U514

| 项 | 结果 | 证据与边界 |
| --- | --- | --- |
| U508 区域结束即时显示摘要 | PASS | SSE 终态触发快照刷新；真实续轮刷新读回 `unknown` 卡。页面只显示服务端卡，不本地推断。 |
| U509 SSE 断线、重复和恢复 | PASS | `wp15-workbench.test.tsx` 覆盖 ID 去重、Last-Event-ID、reset、终态及旧上下文；实现额外修复同一网络块内的迟到事件。 |
| U510 空值、单位和快速双击 | PASS | 表单只按服务端 schema 组装；空值/原因不足禁用，单位/conditions 原样提交，稳定内容指纹复用幂等键；服务端事务回归复用 WP-12。 |
| U511 固定观察和报告布局 | PASS | 1440/1024/390 浏览器检查均在三栏/响应式页面内显示观察与报告，不使用临时弹窗。 |
| U512 旧版、撤销版及页码 | PASS（限定） | Drawer 使用服务端 `source_content_url`、snapshot 与 validity；新增撤销旧 PDF page=7 组件反例。实际浏览器本轮打开的是合成 Markdown 当前版本；PDF/版本映射后端沿用已接受专题证据。 |
| U513 三视口、键盘和长文本 | PASS（限定） | 1440×900、1024×768、390×844 均无关键横向溢出；按钮、导航、长事实区可滚动。浏览器摘要见 `browser-verification.json`。 |
| U514 真实浏览器→API→worker→MCP→LLM | PASS（限定实际结果） | 首轮发布真实检查、浏览器保存观察、真实续轮保守 `unknown` 并刷新读回。未产生第二项检查，明确不在通过范围。 |

## 命令与结果

- OpenAPI：`api:generate`、`api:check` exit 0；见 `final-api-generate.log`、`final-api-check.log`。
- 前端：最终测试 33 passed、typecheck exit 0；生产代码版本的独立 `build:wp14` exit 0，105 modules，见 `final-frontend-tests-v2.log`、`final-typecheck-v2.log`、`final-build.log`。
- 预览兼容：22 passed，exit 0。
- Python：受影响文件 Ruff 最终 exit 0，启动脚本 `py_compile` exit 0，见 `ruff-final.log`。
- 后端受影响组首轮缺 `TEST_DATABASE_URL`，随后系统临时目录 PermissionError；改用项目内独立临时目录后 12 passed/1 worker readiness timeout。该节点只在第二个全新隔离库定点运行一次并通过；最终 WP-15 定点 3 passed。原失败未删除，见 `failure-history.json` 及对应日志；不把它们合写成受影响组全绿。
- 浏览器初次 CDP 在业务动作前因来源参数缺失返回 403；只重启本轮自有 Chrome 后，观察提交成功。两次合成截图与三视口摘要已封存。

## 当前限制

- 真实资料仍 `NOT_MET`；真实链路使用合成台架资料，不是 DKVB 实车或维修效果验证。
- 真实续轮没有第二项当前检查，只产生保守 `unknown` 区域卡。
- 真实最终报告语义、生产恢复、负载、遥测、部署、备份及迁移未验证；WP-16/17 未开始。
- 5180/5196 未操作；本包没有部署正式前端。
- 本结果是执行者自测，不是集中审核或用户接受。

## 停止点

WP-15 实现与自测完成，状态保持 `IMPLEMENTED_NOT_ACCEPTED`，等待一次集中审核。未进入 WP-16。
