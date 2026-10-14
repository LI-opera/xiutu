# WORKBENCH-V2-INTEGRATION-01 实施记录

状态：**IMPLEMENTED_NOT_ACCEPTED**（仅限 synthetic/DEMO、`formal_usable=false` 的 DKVB/P0299 首条正式病例纵向路径；待用户亲自验收）。不代表正式工作台 V2 全面替换，也不代表实车确诊。

## 职责与接线

| 内容 | 原型来源 | 正式病例来源/处理 |
| --- | --- | --- |
| 车辆、主诉、故障码 | `prototypeIntake.ts` 页面状态 | `/api/v2/cases` 冻结的接诊快照、`case_id` |
| 五区域、34 部件卡、78 问题及选项、图片 | `prototypeKnowledge.ts`、`prototypeCatalog.ts` | 导出为版本化 `backend/app/topics/dkvb_p0299_v2.json`；只读专题内容 |
| 答案、历史和更正 | `prototypeKnowledgeState.ts` reducer | 原有 observation 提交/更正 API 和有效记录；专题 ID 原子写入同一观察 payload |
| 区域进度、问题小结 | 原型本地派生 | `/cases/{case_id}/workbench-v2` 从服务端有效观察投影；旧记录不充当当前事实 |
| 下一步与报告门禁 | 原型分支 | 原有冻结 CHK-3.1.0 保守协议、服务端诊断运行和报告门禁 |
| AI | 原型 `/prototype/ai-analysis` | 正式 V2 暂禁用；没有调用模型或将其输出写为观察 |

运行入口为 `main.tsx` → `FormalApp.tsx` → `WorkbenchPage.tsx`：仅冻结绑定、专题内容哈希及车型/发动机/故障码均符合虚拟 DKVB/P0299 的正式病例进入 `FormalWorkbenchV2Page.tsx`，`?legacy=1` 可回退旧 `RegionalCaseWorkbench.tsx`；其余历史病例（含过期专题哈希）继续旧工作台。`/design/workbench-v2` 仍由 `WorkbenchV2PrototypePage.tsx` 转到 `WorkbenchV2ContentPage.tsx`，仅作原型，不是正式保存。

正式接线复用原有病例、来源审核、观察幂等、更正、诊断运行、协议快照及报告门禁，不建立平行存储。新增 `topics/dkvb_v2.py` 显式适配层及 `workbench_v2_projection.py` 只读投影。专题版本 `2.0.0` 与内容 SHA-256 随接诊快照冻结；资料来源仍是合成夹具，不是实车维修依据。

本轮代码文件：`backend/app/api/cases.py`、`backend/app/repositories/cases.py`、`backend/app/services/observation_service.py`、`backend/app/services/workbench_v2_projection.py`、`backend/app/topics/{__init__.py,dkvb_v2.py,dkvb_p0299_v2.json}`；`frontend/src/formal/pages/WorkbenchPage.tsx`、`frontend/src/formal/diagnosis/WorkbenchParts.tsx`、`frontend/src/formal/design/workbench-v2/{FormalWorkbenchV2Page.tsx,formal-workbench-v2.css,topicIdentity.ts}`；`frontend/scripts/export-workbench-v2-topic.mjs`、`scripts/{wp15_workbench.py,r1_experience_seed.py}`、`tests/unit/test_workbench_v2_topic_adapter.py`，以及随接口更新的 `docs/api/openapi.wp14.json`、`frontend/src/generated/api-schema.ts`。状态/实施记录仅更新本文件、同目录 `README.md` 和 `docs/implementation/STATUS.md`。

本次明确接通：`CHK-04 / air.seating_suspect` → `AIR-07 / partially_seated`（对象、位置、观察依据）；`CHK-05 / leak.localized` → `AIR-15 / connector`（位置、定位依据），`leak.not_found` → `AIR-15 / none`；`CHK-06 / repair.completed` → `RET-01 / reseat`；`CHK-07 / retest.record` 且新三帧确实恢复 → `RET-04 / recovered`。服务端校验当前受控检查和专题版本。接诊 CHK-01—03 与最终 CHK-11 沿用原正式表单，不伪装为78块均可提交。其余74个问题块有标题、说明、选项、字段及资料入口，但缺少相应服务端选项/字段校验和冻结协议路由，显示待接入，不能只在浏览器中保存。

## 一条真实 `case_id` 的最小验证

隔离合成实例：`http://localhost:5215/workbench/a1d4ccb2-2a38-4d0a-bd4a-3b7fcfbf551e`。现有 5215/8215 与 WP-15 隔离数据库/worker；仅将该隔离库从迁移 0012 升至 0015 并加入受控合成资料，不涉及其他运行库；未创建新端口、未调用 DeepSeek。

- 浏览器创建正式病例后提交 CHK-01—03，保存 AIR-07；刷新后显示 `1/16` 且下一步为 AIR-15。
- 更正 AIR-07 位置及依据：旧 observation `3a1c1d9f-7ded-48f7-a86e-b52c25347e55` 保留、失效；新 observation `c4e0acf5-859c-45ed-a90c-5e07b690d728` 有效，服务端重新路由至 AIR-15。
- AIR-15 观察 `59301bf8-e1ec-406d-8e54-a10ec734a514`、处理 `be9b2104-e8f4-4c9d-a50b-219416544b6d`、新复检 `bd55b104-8db4-404c-9770-c64eb919ce5a` 分别保存。复检数值更正后 `110035ee-1d0c-4a8c-9955-5fe8acf19929` 成为有效记录，原复检仍保留历史。
- 浏览器故意提交与“恢复”不符的复检值，服务端拒绝；表单保留输入，改正后点“重试保存”成功。从 `/history` 重新进入后恢复同一病例、`2/16` 空气区进度、处理/复检记录与服务端小结。
- 报告门禁仍为 `available=false`，页面明示演示小结不是最终报告。旧未绑定专题病例 `79e116ed-e06d-47f7-8765-ac0666870d80` 仍进入旧正式工作台。
- 桌面和 430px 浏览器目视检查无明显损坏，430px `scrollWidth=415 < innerWidth=430`；专题图片 M03 加载成功。
- 前端 `npm run typecheck` 通过；仅运行专题适配/投影与 OpenAPI 定点测试，8 passed。未做全仓回归或独立审核。

## 代码保留与下一工作包

当前正式运行：`FormalWorkbenchV2Page.tsx`、`formal-workbench-v2.css`、生成的 `topicIdentity.ts`、后端专题 JSON/适配/投影及现有病例/观察/诊断服务。当前原型运行：`WorkbenchV2ContentPage.tsx`、`prototypeKnowledge.ts`、`prototypeKnowledgeState.ts`、`prototypeCatalog.ts`。待退役但本轮不删除：旧 `prototypeData.ts`、`prototypeState.ts` 与引用它们的 `PrototypeAreaGrid.tsx`、`PrototypeActionWorkspace.tsx`、`PrototypeCaseHeader.tsx`、`PrototypeComponentList.tsx`、`PrototypeSynthesisPanel.tsx`、`PrototypeVehicleSummary.tsx`；预计在后续完成专题数据统一消费并确认原型回归不再依赖时退役。

下一工作包需逐项建立其余74块的正式字段/选项验证、保存映射及受控路由；完善不可用/更正后的区域复核语义、跨专题配置与测试；如需正式 AI，另建显式授权/审阅与建议记录契约，不能直接沿用原型接口。真实资料 `NOT_MET`、自由模式和实车效果不在本轮范围。
