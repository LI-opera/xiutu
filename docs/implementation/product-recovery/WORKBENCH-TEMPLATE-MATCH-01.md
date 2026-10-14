# WORKBENCH-TEMPLATE-MATCH-01

日期：2026-09-26。状态：IMPLEMENTED_NOT_ACCEPTED。

## 交付范围

在原工作台接诊区增加品牌、年份、确认按钮，沿用原配色、卡片、分组与问题组件，未修改样式文件。品牌、车型、年份、主诉、故障码必填；发动机在匹配需要时确认。没有 AI 排序、生成或模型调用。

新建病例提交 `workbench_flow=template-match-v1`，依普通数据库关系匹配模板，并冻结完整模板、版本与哈希。旧专题绑定和历史病例路径不变。

当前编辑性适用范围为大众/探岳/2019/DKVB：P0299 对应五区，P0236 对应前三个区域。只支持单码，未匹配或发动机缺失明确返回说明。P0236 是资料包的初始子集配置，不声称是厂家完整故障树。

## 存储与路径

- 迁移 `0018_workbench_templates` 新增 `workbench_templates`（版本化完整 JSON）和 `workbench_template_matches`（车型条件、故障码、模板外键）。已在原隔离库应用。
- `backend/app/topics/workbench_template_relations_v1.json` 定义适用关系。
- `scripts/seed_workbench_templates.py` 从既有 B02 目录构建完整分组、问题、选项、字段和引用；已有同版本不同内容拒绝覆盖。
- `backend/app/services/workbench_templates.py` 负责匹配、规范化、冻结与投影。
- `case_service.py`、`workbench_b01_service.py`、`api/cases.py` 接入新流；模型/schema、ORM、schema_version 同步。
- 前端 `MatchedVehicleIntake.tsx`、`FormalVehicleProfile.tsx`、`WorkbenchPage.tsx`、`FormalWorkbenchB01Page.tsx` 使用原页面组件。
- OpenAPI 与前端生成类型已更新。

新模板仍复用 B02 的内部派生计算与已有条件操作校验，通过模板子集过滤展示与记录范围；这不是全车型通用诊断引擎。未填写的工况、安全状态保留未知，不填正常；区域固定顺序，不执行 AI 排序。新流不显示未接入的 AI 与维修复检模块，旧病例保持原页面。

## 验证

- 模板/B02 定点测试 10 passed；前端 typecheck 通过。
- 浏览器真实提交相同车辆、不同故障码：P0299 五区，P0236 三区；点击区域可展开原分组、问题及选项。
- AIR-01 原因输入不自动保存，保存后显示记录；更正通过正式接口形成新有效观察，幂等重复请求不重复写入。
- 正式 API 验证错误年款、品牌、故障码、缺发动机、多故障码均不错误套用模板；P0236 写入 TUR-01 被拒且 revision 不变。
- 旧病例 `95b92020-ae99-418b-a7e3-b8bb7aa4e776` 仍为 B02，revision 34。
- 自有服务重启后本机自动登录、两病例读取及刷新正常。首次重启健康检查因预期迁移仍为 0017 失败，更新至 0018 后恢复；未动其他服务。
- API/Web/worker 为 stub / paid=false；真实模型调用 0 次。

验证脚本：`scripts/verify_workbench_templates.py`，默认只读核对并发送预期拒绝请求；`--verify-correction` 仅针对标记的五区验收病例执行一次更正，勿无意重复使用。

## 体验入口与当前数据

- http://localhost:5215/workbench ：填写并确认。
- P0299：http://localhost:5215/workbench/7d5ac558-e812-4bbf-812f-cae4cbe7860f ，revision 3，2 条历史/1 条有效模拟观察。
- P0236：http://localhost:5215/workbench/d9e18ecc-50b3-481b-88da-69c06b26d4d2 ，revision 1，0 观察。

补充页面修复：病例页顶部原为只读快照，导致用户在展示的病例页无法输入和确认。模板病例现在复用可编辑接诊表单并在原位置显示确认按钮。编辑后确认会创建新病例并打开其模板，旧病例观察不会被覆盖。浏览器已从上述 P0236 病例在顶部改填 P0299，创建 `047097ef-65cb-422c-84cc-70f8c9d81701`；新页显示五区、0 条观察，原三区病例仍在。前端 typecheck 通过，未改样式文件。

验收仅证明上述映射、完整题目读取和记录路径，不证明其他车型适用性或维修有效性。用户尚未接受。后续方向等待用户安排。

回退线索：可恢复旧接诊入口与旧路由分支；保留新增模板、病例快照和记录。不要通过降级迁移删除用户数据。

## 综合区关联修正（2026-09-26）

新模板病例保留原四栏综合分析。服务端仅把本次匹配区域下的有效观察、异常、无法完成、冲突和待记录题纳入区域摘要；接诊安全题不混入区域事实。页面初次显示全部匹配区域并标明来源区域，点击上方区域卡后只看该区；可切回全部范围，摘要中的题目可跳回原题。区域排序不参与事实归类，未检查不等于正常，也不产生病例级 AI 结论。旧专题病例的综合区路径不变；新模板的病例级 AI 与维修复检模块仍未接线。

定点验证：模板投影 5 passed、综合区渲染 1 passed、前端 typecheck 通过；正式 API 核对病例 `18a144fe-dfa2-4d44-8824-11388d26fa9a` 的 10 条观察均归于增压压力测量，区域摘要无非区域记录。本次未调用模型、未改动病例事实。

## 2026-09-26 移除新模板观察读取的遗留 50 条限制

用户在其他动力系统方向保存 X-11、X-12、X-14 时收到 RESULT_TOO_LARGE。主病例当时 revision 59、50 条有效观察。根因是保存后的病例投影调用 report_policy.snapshot，该处仅对旧 B01/B02 读取完整观察，新 template-match-v1 仍受 50 条限制，导致第 51 条写入事务回滚。

现对 template-match-v1 同样读取完整有效观察，不更改报告判定规则，不截断或删除记录。核对 TopicService 保存、投影、历史、区域分析链路；历史分页的 limit 是分页大小，不是病例记录总量限制，保留。

修改 backend/app/services/report_policy.py；新增 tests/unit/test_template_observation_limit.py 和 scripts/probe_template_observation_limit.py。8 项定点测试通过。数据库回滚探针通过实际 TopicService.save/_view/get 验证 X-11/X-12/X-14 的第 51、52、53 条保存及读回，报告 gate 相同；全部回滚后病例仍 revision 59、原记录数不变。首轮探针误选 X-13 自动派生题，按既有规则拒绝并回滚；改为截图对应 X-14 后通过。

仅重载已登记 8215 API，网页和 worker 保留；ready=true、model_configured=true，主病例 GET 正常，实际未新增观察，模型调用 0 次。用户可重试原失败选项，尚未代用户保存这些实际答案。状态：IMPLEMENTED_NOT_ACCEPTED。
