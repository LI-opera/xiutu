# DKVB/P0299 可信诊断协议与引导闭环 r1 实施契约

## 范围与边界

本切片只服务于 `synthetic=true`、`formal_usable=false` 的 DKVB/P0299 DEMO。它不是厂家诊断树、真实车型验证、维修结论或生产规则注册平台。既有 WP-00—15 接受记录不变，WP-16/17 不启动。

专题资料包中的 `knowledge.json` 和 REL-01—07 仅作为作者材料；本切片不会自动信任或导入这些关系。只有本契约列明、由应用代码显式登记且绑定到具体病例、graph epoch、冻结 manifest、车辆 profile 和协议版本的关系，才可进入运行时。

隐藏病例答案、未来观察、`expected.json`、测试者剧本和控制 JSON 不进入检索、模型上下文或公开日志。模型不能创建、修改或提交 `transition_id`。

## 修改面

- 新增迁移 `0013_trusted_diagnosis_protocols.py` 及 ORM 表，保存病例/epoch 唯一的冻结协议绑定；不改历史迁移。
- 新增 `backend/app/agents/trusted_protocol.py`：版本化 schema、应用内显式 DKVB DEMO 注册表和不可变读取。
- 新增 `backend/app/services/protocol_service.py`：可信绑定、观察字段校验、唯一关系匹配、受限候选生成与 ProposalService 复核。
- 调整 `runner.py`、`publish_service.py`、`observation_service.py`、更正路径和诊断查询：协议决策先于模型自由生成；协议元数据进入服务端 validation/progress 视图；观察扩展字段只按当前冻结协议接受。
- 调整正式前端诊断类型、观察表单、工作台呈现及样式：DKVB 协议病例默认引导模式，技术标识默认折叠。
- 新增协议单元/集成/前端测试、独立 synthetic 体验引导和本结果报告。

## 协议 schema

冻结协议至少包含：`protocol_id`、`version`、`synthetic`、`formal_usable`、`applicable_vehicle_profile`、检查的 `check_id/current_stage/input_schema/evidence_refs/completion_conditions`，以及关系的 `transition_id/prerequisites/observation_matcher/next_check_id/need_input_fields/handoff_reason`。运行时绑定另含实际 `case_id/graph_epoch/manifest_hash` 与经当前病例 EvidenceService 绑定的候选及来源引用。

本轮显式登记：

1. `CHK05_LOCALIZED_TO_CHK06`：`leak_result=localized` 且 `leak_object_id`、`leak_location`、合法 `evidence_kind` 完整，观察有效且病例/版本/profile 匹配，才产生 CHK-06。
2. `CHK05_NOT_FOUND_TO_CHK08`：`leak_result=not_found` 产生 CHK-08；说明严格限定为“本项未发现局部漏点”，不得推导系统无泄漏、部件正常、故障排除、已修复或涡轮损坏。
3. `CHK05_INCONCLUSIVE_NEEDS_INPUT`：`leak_result=inconclusive` 产生有具体字段要求的 `need_input` 决策，并发布可继续填写的补充定位观察卡。
4. 为证明不是静态第二卡，`CHK06_COMPLETED_TO_CHK07` 仅在 CHK-06 明确完成后产生 CHK-07；仍保持 DEMO 与非正式边界。

来源映射：CHK-05 使用 S02-P5/P6；localized→CHK-06 使用维修知识手册 CHK-05/06；not_found→CHK-08 使用 CHK-05/08；inconclusive 使用 CHK-05 的补定位要求。DS 模拟内容保持 DEMO，不作为厂家规格。

## 调用顺序与信任边界

`已提交且有效的 observation → 读取病例/epoch 冻结 protocol binding → 校验当前 check、观察 schema、owner/case/profile/manifest/source validity → 匹配唯一 transition → 生成受限 next_check/need_input → ProposalService 原硬门禁复核 → WP-11 既有 fenced 事务发布`。

输出包含 `decision/protocol_id/protocol_version/transition_id/current_check_id/observation_id/next_check_id/evidence_refs/missing_fields/reason_code`。这些字段由服务端产生，浏览器和模型不能提高权限。当唯一候选已确定时，服务端直接生成结构；模型最多在允许字段和来源内组织用户说明。模型提出其他 check、伪造 transition 或扩大结论一律拒绝。

ProposalService 的引用、版本、车辆范围、位置、工况、动作、选项、权限、重复与发布门禁保持不变。协议路由不创建 supported/ruled_out/确诊/维修完成结论。

## 输入输出与恢复

观察 API 保持认证、CSRF、幂等、revision、epoch 和 owner 约束。协议扩展字段是当前步骤 validation 中服务端公布的有界字段；未绑定协议、未知字段、错误枚举、缺必填或与选择不匹配均在观察事务写入前拒绝。协议绑定和决策随数据库恢复；刷新从当前 step、validation 与已保存 observation 重建页面，不依赖 localStorage 业务事实。

## 验证顺序

1. 免费 schema/注册/字段与信任边界单元测试。
2. 隔离 PostgreSQL 集成测试三分支、CHK-06→CHK-07、幂等、撤销、错 owner/case/version/profile、伪造 transition、标题变化、更正后重路由和隐藏资料隔离。
3. 前端引导状态测试、typecheck、独立构建。
4. 独立 synthetic 实例浏览器走 A/B/C，并继续 A 或 B 的第二步；确认来源、刷新、一个主操作及无裸露 JSON。
5. 只有上述免费验证全部通过后，才允许一次真实 DeepSeek 浏览器路径；失败立即停止，不创建第二条付费路径。

## 停止条件

交付状态仅为 `IMPLEMENTED_NOT_ACCEPTED`。不修改 WP-00—15 接受记录，不启动 WP-16/17，不操作 5180/5196；5215 在独立版本验证完成前不覆盖。不提交或推送。
