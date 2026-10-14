# WORKBENCH-ADAPT-C01 · 正式病例建议接线

状态：`IMPLEMENTED_NOT_ACCEPTED`（2026-09-24）。用户接受的 B02 范围是 DKVB/P0299 合成专题工作台体验与执行流程，**不代表真实车辆诊断能力验收**。阶段 C 接线已实现，模型替身验证通过；真实 AI 效果尚未验证。

## 范围与数据流

在原有五区、综合分析和 AI 区布局内，新 `POST /api/v2/cases/{case_id}/analyses` 仅接收期望 revision、幂等键和真实调用确认；浏览器不提交自称完整的观察列表。服务端验证病例归属、B02 专题绑定、首次分析准备状态与安全停止，读取全部有效观察、接诊、计划、派生、冲突、缺项、来源正文和图纸引用，再在单个事务中冻结输入与入队。后台调用替身或受控模型适配器，校验固定结构、引用及建议范围后持久化。`GET` 列表/单项返回快照版本、状态、旧建议过期标志和处理/复检关联。病例保存不受分析任务阻塞。

新表 `case_analyses` 由增量迁移 `0016_case_analysis_advice.py` 建立，不改旧病例和 CHK 路径。结果是病例建议，不是最终维修报告；现有报告门禁及 `synthetic=true`、`DEMO`、`formal_usable=false` 边界保持。事实修改后旧结果仍可读，标记“基于较早记录，需重新分析”；不会后台自动重发模型请求。同一 revision 的已完成/在途逻辑请求去重，旧任务不能覆盖新事实；一次真实逻辑请求最多调用模型一次，失败、超时或结果不确定均不自动付费重试。

## 实际提供的资料与边界

`backend/app/topics/tanyue_dkvb_p0299_c01_context.json` 隔离登记了两段经过 PDF 页面核对的正文摘录：DKVB/DPLA《增压空气系统》PDF 第 1 页检查空气软管/管路座合及泄漏的说明，第 5 页压力不得超过 0.5 bar 的安全限制。登记原文件 SHA-256 `0cb9ccb8650646779b4056db3614bbf656e48c430d13d30afc5f0dde0f4c4e44`、来源 ID、章节、页码与专题图资源引用。快照还按当前相关题确定性选入专题网页长内容卡，明确标为**编辑性演示内容**，不能冒充维修手册；图纸只提供引用，模型没有读取或解析图片。无正文的来源会列出缺口，技术操作不得仅凭标题或题目文案获得资料支持。不全库混搜、不建向量/OCR/网络资料路径。来源正文远不覆盖全部 78 题的厂家操作与判据，缺失时建议仅能补充检查或交接。

## 输出、处理与费用

输出含概述、支持与未确认方向、最多六步的有条件检查/处理、事实和资料依据、复检及停止/交接。服务端拒绝不存在于冻结快照的观察/来源引用，以及缺证据时的确诊、直接换件等越界语义；结构有效不等于真实模型临床/维修可靠。AI 区可从引用跳转具体观察并查看摘录/图资源。处理入口只打开 RET-01，不自动填“已维修”；实际处理保存后关联建议，独立新复检轮次沿用 B02。旧建议过期后不提供执行导航。综合区继续标为服务端规则摘要，不冒充 AI。

本地 5215/WP15 开发实例明确启用 `XIUTU_C01_MODEL_MODE=stub`，并关闭真实调用授权和密钥。页面显示“模型替身验证结果，非真实 AI 生成”。真实适配复用现有 DeepSeek 网关但本轮关闭；拟用当前配置 `deepseek-flash`，输入最多 48,000 字符、输出最多 1,536 tokens、每个逻辑请求最多一次真实调用。真实体验需用户另行授权并在请求前确认资料范围与费用；上下文超限直接停止，不静默丢弃关键事实。

## 修改与验证

主要修改：`backend/app/topics/tanyue_dkvb_p0299_c01_context.json`；`backend/app/domain/case_analysis.py`；`backend/app/services/case_analysis_context.py`、`case_analysis_service.py`、`case_analysis_runtime.py`；`backend/app/api/case_analyses.py`；ORM、迁移、schema version、主路由、worker/job store/run service 与 B02 处理关联；`frontend/src/formal/design/workbench-v2/FormalCaseAnalysis.tsx`、`FormalWorkbenchB01Page.tsx`、`formal-workbench-v2.css`；`scripts/wp15_workbench.py`、`scripts/verify_c01_stub.py` 和定点测试。

定点单元测试 `tests/unit/test_case_analysis_c01.py` 5 passed，前端 `npm run typecheck` 通过。独立 HTTP 替身探针在原 8215 API 验证完整病例建议持久化、资料引用、缺证据仅交接、修改事实后过期、重复请求、失败/非法引用、建议关联处理与新复检；浏览器 5215 确认两种建议范围、过期标识、观察跳转、资料展开以及处理按钮只导航不自动写入。分析病例 `132d2b28-1824-4161-864d-205dc1315106`；缺证据病例 `a1548837-6e20-4df9-86d2-db20141a217f`；干净体验病例 `cb7eaff8-0f56-48e7-9a12-98d0bbc011b5`。均为独立 DEMO，未修改用户原病例。本轮未作真实付费请求、全仓回归、旧数据清理或阶段 D 工作。

剩余：厂家资料正文覆盖不足，G71 专项/PRS 超调判据仍缺；真实模型输出质量、费用与安全性未验证；对现实车辆仍不可形成最终维修结论。需用户另行授权有限真实模型体验后再评估，不自动进入后续阶段。
