# 修途实施状态

更新：2026-09-23。WORKBENCH-V2-INTEGRATION-01 已实施、**IMPLEMENTED_NOT_ACCEPTED**，仅对冻结绑定的虚拟 DKVB/P0299 合成病例启用正式 V2 页面；服务端保存、更正、复检与历史恢复的一条路径已验证，仍待用户亲自验收。见[实施记录](product-recovery/WORKBENCH-V2-INTEGRATION-01.md)。WP00—15仅按各自接受记录列明的限定范围接受；WP-13—15尤其不代表真实资料、真实维修效果、生产部署或整个 P4/P5 完成。真实资料门槛仍为 `NOT_MET`，真实模型第二项当前检查、浏览器内置 PDF 第2页视觉渲染和真实最终报告语义仍未验证。WP-16—17保持 `NOT_STARTED`。

| 工作包 | 状态 | 说明 |
| --- | --- | --- |
| WP-00 | ACCEPTED | 2026-09-18 用户明确接受；依据 wp-00-review-r1.md；见 phase-01/wp-00-acceptance.md |
| WP-01 | ACCEPTED | 限定已验证的核心技术交付；依据[r2审核](phase-01/wp-01-review-r2.md)及[用户接受记录](phase-01/wp-01-acceptance.md)。E10仍NOT_VERIFIED，资料仍NOT_MET；不是第一阶段无条件完成 |
| WP-02 | ACCEPTED | 用户限定接受八表迁移、领域校验、本地单操作员认证、会话create/get/list、所有权隔离、CSRF、事务幂等及整改；依据[r3复核](phase-02/wp-02-review-r3.md)，见[接受记录](phase-02/wp-02-acceptance.md)。用户明确接受r2/r3与整改同任务的流程限制；E10及资料门槛继续保留 |
| WP-03 | ACCEPTED | 用户限定接受持久任务、领取互斥、租约/心跳、过期结果保护、取消/重试、任务查询及SSE；成功处理器仅no_op。依据[r1审核](phase-02/wp-03-review-r1.md)，见[接受记录](phase-02/wp-03-acceptance.md)。用户已接受审核任务参与实现的流程限制；性能/监控/清理待办保留 |
| WP-04 | ACCEPTED | 限定资料导入与人工审核范围：本地MD/PDF上传、版本保留、原文定位、解析切块、人审历史及取消/租约/事务回滚下的发布保护。依据[r2复核](phase-02/wp-04-review-r2.md)，ISSUE-001关闭；见[用户接受记录](phase-02/wp-04-acceptance.md)。用户知悉同任务实施/整改/复核限制。r1整改前完整169通过；r2定点15通过，不表示整改后重跑完整入口。无OCR/embedding/索引/检索 |
| WP-05 | ACCEPTED | 限定本地向量、索引与混合检索技术范围；固定E5配置、持久索引任务、发布保护、原子切换、资格/适配过滤及原文定位。依据[r1审核](phase-02/wp-05-review-r1.md)，见[用户接受记录](phase-02/wp-05-acceptance.md)。用户知悉同任务实施与审核限制；E10及真实资料门槛保留 |
| WP-06 | ACCEPTED | 限定证据与规格比较技术范围：服务端冻结资料范围、不可变证据/定位、人工规格版本及审核、精确比较、撤销复核与使用阻断、引用硬校验门禁；依据[r1审核](phase-02/wp-06-review-r1.md)，见[用户接受记录](phase-02/wp-06-acceptance.md)。同任务实施与审核限制、E10及真实资料门槛保留，不代表整个P2接受 |
| WP-07 | ACCEPTED | 限定五业务工具与执行器技术范围：可信上下文/权限收窄、持久预算/审计、本地LangChain适配、比较幂等及超时/取消事务保护、观察只读、receipt v2安全重放与旧比较有效性检查。依据[r2复核](phase-03/wp-07-review-r2.md)关闭ISSUE-001/002；见[用户接受记录](phase-03/wp-07-acceptance.md)。用户知悉同任务流程限制；不是整个P3接受 |
| WP-08 | ACCEPTED | 限定三项只读业务MCP技术范围：真实SDK Streamable HTTP、应用/独立CLI、服务端授权及最终grant复验、应用预算/审计与无静默fallback、只读DB角色及Compose部署。依据[r2复核](phase-03/wp-08-review-r2.md)关闭ISSUE-001并补齐Compose动态权限；见[用户接受记录](phase-03/wp-08-acceptance.md)。同任务流程限制及保留项继续有效，不代表整个P3接受 |
| WP-09 | ACCEPTED | 限定模型网关、可信Skills、已验证配置factory、Windows本地BGE1024与旧E5384索引兼容。依据[r2复核](phase-04/wp-09-review-r2.md)关闭ISSUE-001/002；见[用户接受记录](phase-04/wp-09-acceptance.md)。同任务流程限制、Linux BGE未验证及真实资料缺项保留 |
| WP-10 | ACCEPTED | 限定合成资料下有界五类提案、批准规格硬校验、对象级去重/同组复测及两类可信结论模板；ISSUE-001依据[r3](phase-04/wp-10-review-r3.md)关闭，ISSUE-002—004依据[r2](phase-04/wp-10-review-r2.md)关闭。见[用户接受记录](phase-04/wp-10-acceptance.md)。规则仅可信应用装配、生产默认无规则；真实资料原截止门槛未满足，不接受整个P4 |
| WP-11 | ACCEPTED（限定） | 用户仅接受合成且精确适配资料下的持久诊断图、事务发布、等待和跨进程恢复技术能力；A406—A409据[r1审核](phase-04/wp-11-review-r1.md)在该范围内PASS，见[接受记录](phase-04/wp-11-acceptance.md)。历史449项完整回归非当前版本重跑；本轮审核16项、工具预算3实例及跨进程观察恢复1项定点通过，首次审核夹具错误保留。两次真实DKVB turn均publication=0，真实模型发布及DKVB资料适配未完成；真实资料NOT_MET、旧worker首发根因未确证。WP-12观察写入、生产恢复及真实维修效果未接受 |
| WP-12 | ACCEPTED（限定） | 合成且精确适配资料下的观察原子提交、保守区域收尾及仅unknown卡、事实更正和持久图恢复；[接受记录](phase-04/wp-12-acceptance.md)。[r1集中审核](phase-04/wp-12-review-r1.md)中A410/A412—A414限定通过，A411的ISSUE-001依[区域复核r2](phase-04/wp-12-review-r2.md)关闭；RECOVERY-001依[恢复复核r2](phase-04/wp-12-recovery-review-r2.md)关闭。旧版完整481通过/1警告，不是当前版本全量；当前r2定点8通过/2夹具错误、补正后2通过。真实模型发布、生产恢复、正式网页及维修效果不在接受范围 |
| WP-13 | ACCEPTED（限定） | 接受用户主动请求的进度/最终报告、六项最终门禁、冻结资料与结论、独立报告任务/校验/事务发布、历史 stale 表达及合成 MockTransport 最终报告技术路径；依据[审核 r1](phase-04/wp-13-review-r1.md)及[接受记录](phase-04/wp-13-acceptance.md)。最终标准入口514通过/1个Windows HTTP读错误/1警告，该唯一实例无代码变更定点通过；失败和定点证据分开保留，不声称完整入口全绿。unknown不会提升为最终结论；真实模型语义、真实资料和维修效果未接受。 |
| WP-14 | ACCEPTED（限定） | 接受正式 React 路由外壳、OpenAPI 生成类型/漂移检查、统一 API client、真实资料中心、病例入口、URL刷新恢复、主动历史搜索、完整分页及检索上下文隔离；依据[r1审核](phase-05/wp-14-review-r1.md)与[r2复核](phase-05/wp-14-review-r2.md)，ISSUE-001/002均关闭，见[接受记录](phase-05/wp-14-acceptance.md)。同任务链流程限制及未部署、真实资料/模型/维修效果限制保留，不含WP-15诊断交互 |
| WP-15 | ACCEPTED（限定） | 接受正式 `/workbench/:caseId`、病例/区域/检查/观察读取、completed选择与pending激活保护、四类观察及规格/工况校验、稳定幂等、更正stale、SSE/snapshot恢复、不可变PDF物理页定位、报告门禁/run恢复和三栏响应式布局；接受的真实链路仅为首项有据检查→浏览器保存观察→真实续轮保守`unknown`卡→刷新读回。依据[r1审核](phase-05/wp-15-review-r1.md)、[整改](phase-05/wp-15-remediation-r1.md)、[r2复核](phase-05/wp-15-review-r2.md)及[接受记录](phase-05/wp-15-acceptance.md)，ISSUE-001—006均关闭。整改后正式前端37项、r2补充前端8项、后端整改定点8项、r2真实HTTP/PostgreSQL补充2项通过，typecheck、api:check、独立构建及Ruff通过；证据按版本分列，不累加重复覆盖。同任务链流程限制保留。PDF插件视觉渲染/独立页图/OCR、真实资料、第二项真实检查、真实最终报告语义、生产恢复/负载/评测/部署/备份/迁移及维修效果均未接受；未部署5180/5196 |
| WP-16 | NOT_STARTED | 未执行 |
| WP-17 | NOT_STARTED | 未执行 |

## WP-13 前可体验诊断闭环切片（独立实施记录）

**ACCEPTED（限定已证明链路），未部署。** [接受记录](phase-04/diagnosis-slice-acceptance.md)依据[集中审核 r1](phase-04/diagnosis-slice-review-r1.md)：真实 DeepSeek 经原工具和提案校验发布一项有出处的检查，隔离浏览器持久保存观察，真实续轮发布保守 `unknown` 区域卡，刷新后读回。`unknown` 是待补，不是确诊、排除或最终报告就绪。原定观察后再发布第二项当前检查尚未完成，不能称两步闭环；真实 DKVB 资料门槛仍 `NOT_MET`。这只接受 `synthetic=true`、`formal_usable=false` 的隔离技术链路，不扩大 WP-00—12 接受范围，也不启动 WP-13—17。

保留缺项与范围：

历史与本次证据分别保留：[原结果](phase-04/diagnosis-slice-result.md)中的免费夹具检查、早期真实候选拒绝及过期续轮；[预算策略](phase-04/diagnosis-slice-budget-policy-r1.md)中的 v2 持续计量迁移；[前模型整改](phase-04/diagnosis-slice-pre-model-remediation-r1.md)中的隔离探针 checkpoint 初始化缺项与首次真实候选失败；[候选修复整改](phase-04/diagnosis-slice-repair-remediation-r1.md)中的最终版免费5项和4项分组通过、真实首轮/续轮及计量；[续轮决策](phase-04/diagnosis-slice-next-decision.md)中的 P01→Q02 条件依据缺口；[审核 r1](phase-04/diagnosis-slice-review-r1.md)的限定结论。真实续轮业务脚本因未产生第二项检查而退出1，首次截图超时记录不抹去。旧完整回归属于较早源码版本，本次未重跑；同一任务链实施与审核不称不同任务独立审核。旧页面实例5180/5196未部署本切片；原共享账本仍持续计量，保守预留及 usage 估算都不是平台账单。第二项检查、真实模型两步目标、真实资料与最终报告门槛仍待另行处理。

- E10：依据WP09 r1/r2与当时用户接受限定收口，仅覆盖已验证deepseek-flash契约，不扩展到其他型号、全部strict或真实维修效果，不改写历史NOT_VERIFIED。WP-09原记录为4请求含失败，预留¥0.198184、usage估算¥0.024582，非平台账单；WP-11本轮真实调用和共享账本变化另见[整改结果](phase-04/wp-11-remediation-r1.md)，不重置5元授权。
- 真实资料门槛仍为NOT_MET；来源/许可、精确车型及发动机适配、正式规格、电路、拆装/复核章节及缺图，最迟WP-10/真实效果验收前补齐。 原截止要求目前仍未满足；此次合成技术接受不顺延、不标为通过。
- WP-08仅接受三项只读业务MCP技术范围；不代表正式Agent/UI、远程模型strict兼容、生产恢复、完整产品或真实维修效果，也不是第一阶段或整个P3无条件完成。

执行基准：main，HEAD 不存在（新仓库无提交）；WP-00 原暂存区未变；WP-01 修改/新增未暂存，请同时查看 git diff 和未跟踪文件。旧项目无 Git：初始[53项基线](phase-01/evidence/legacy-hashes-before.json)，当前[扩展63项保护清单](phase-01/evidence/review-r1/legacy-hashes-after.json)。扩展来自P2—P6共10份阶段文档；阶段总表的历史并行变化见[baseline补记](phase-01/baseline.md)，不视为业务源码被修改。

WP-10以后各包的历史全量、整改与审核证据仍分别保留在各自结果/接受记录，不将不同版本测试累加为功能覆盖数。WP-14 原实施、r1审核、整改与r2证据分开保存；整改后正式前端24项、预览兼容24项、r1原反例4项、r2补充边界7项通过，typecheck、`api:check`及独立构建通过。未重跑约41分钟全后端入口。详情见[WP-14结果](phase-05/wp-14-result.md)、[r1审核](phase-05/wp-14-review-r1.md)、[r2复核](phase-05/wp-14-review-r2.md)及[接受记录](phase-05/wp-14-acceptance.md)。E10沿用WP09 deepseek-flash限定结论；真实资料`NOT_MET`、Linux BGE及历史启动/SSE/Compose根因未确认、其他待办继续保留。诊断切片的第二项当前检查仍未发布。

WP-07证据版本（分别保留，不累加重复测试为功能覆盖数）：

- [r1集中审核](phase-03/wp-07-review-r1.md)：整改前完整260通过（1条已知警告），补充6通过、5失败。
- [r1整改自测](phase-03/wp-07-remediation-r1.md)：首轮33通过、1个测试记录错误（UUID序列化）；修正测试记录后，受影响及补充5项通过，原失败证据保留。
- [r2当前版本复核](phase-03/wp-07-review-r2.md)：37项定点＋2项补充通过，ISSUE-001/002关闭，限定范围REVIEW_PASS。未重新运行整改后完整入口，不声称不同任务独立审核。本次接受未追加测试。

WP-07兼容限制与待办：旧无版本receipt返回RECEIPT_UNSUPPORTED，保留审计/历史读取，不自动重做副作用或扣预算；旧比较需复核返回COMPARISON_INVALID，规格重新批准不清除旧结果复核标记。owner粗锁、性能、监控、清理、uncertain处置及未来观察接入待办继续保留。

WP-06证据版本：执行者定点39通过、HTTP演示1通过、完整232通过（1条已知警告）；审核者角色完整232通过（1条已知警告），另18项补充通过。两轮分别保留，不合并为不同功能覆盖数；同任务切换角色，不声称不同任务独立审核。见[执行报告](phase-02/wp-06-result.md)及[r1审核](phase-02/wp-06-review-r1.md)。本次接受没有追加测试或审核。

WP-05证据版本：执行者首轮定点15通过、补充4通过、取消1通过；完整入口192通过/1警告，随后收尾4项定点通过。审核者对最终实现完整194通过/1警告，另2项发布回滚反例通过；同任务切换角色，不声称不同任务独立审核。两轮证据分别见[执行报告](phase-02/wp-05-result.md)和[r1审核](phase-02/wp-05-review-r1.md)。本次接受未重跑测试。冻结24段/12查询合成集Recall@5：baseline0.8472、hybrid0.9306；作者编写的合成标签不是真实维修人工真值。

WP-04测试历史（按证据版本区分，原接受依据保留）：

- 初始执行记录：首次完整入口收集冲突修正后，168 passed、1次SSE超时；随后定点通过，首次超时根因未确认，见[原结果](phase-02/wp-04-result.md)。
- [r1集中审核](phase-02/wp-04-review-r1.md)：**整改前基准完整测试169通过**，另有发布租约窗口反例失败；不是整改后全量结果。
- [r1整改](phase-02/wp-04-remediation-r1.md)：14项定点及原反例1项通过；临时父目录准备错误保留，原失败证据不覆盖。
- [r2定点复核](phase-02/wp-04-review-r2.md)：**15项通过**，ISSUE-001关闭，限定范围REVIEW_PASS；未重新运行完整入口。SSE首次根因仍未确认。

WP-08原交付证据（整改前历史）：首轮业务集成4通过；新增定点1通过/1测试方法名错误，修正后该例1通过；协议契约17通过。完整入口首次因新测试文件同名收集失败（0测试执行/1收集错误），仅重命名契约测试后，当时125项源码哈希对应完整301通过、0失败/错误/跳过、1条已知弃用警告，exit0。Compose三工具/只读挂载实测及配置生成/拒绝覆盖也通过。不得将重复定点与完整统计相加为覆盖数。详见[原交付报告](phase-03/wp-08-result.md)及其证据；这是原执行阶段记录，后续审核、整改、复核及本次用户接受分别记录如下。

以上WP07及更早统计均保留其历史基准。WP08完整301项属于整改前基准，不代表整改后全量重新通过，不回写旧审核结论；旧receipt安全拒绝、旧比较需复核、同任务历史流程限制及owner粗锁/性能/监控/清理/uncertain/观察接入待办不变。

WP-08审核、整改与复核证据（不累加重复测试为覆盖数）：

- [r1集中审核](phase-03/wp-08-review-r1.md)：整改前完整301通过，1条既有警告；补充1通过、2失败（授权缺陷反例及Compose等待器），另一次Compose启动探测失败均保留，原结论CHANGES_REQUIRED不改。
- [r1整改](phase-03/wp-08-remediation-r1.md)：首轮10通过、1个共享allowlist夹具失败，修正后仅该项1通过；修复镜像Compose补测成功，属于执行者自测。
- [r2定点复核](phase-03/wp-08-review-r2.md)：当前版本11项定点通过；Compose一次有界启动通过，67项容器源码匹配，数据库权限及挂载/rootfs实际拒绝写入。ISSUE-001关闭，限定范围REVIEW_PASS；不声称整改后完整301项重新通过。
- [本次用户接受](phase-03/wp-08-acceptance.md)：仅接受列明技术范围，未重跑测试。同任务实施/整改/复核，不声称不同任务独立审核。

WP-08保留限制：最终授权判定后网络发送期间不保证即时撤回；Compose历史启动异常底层原因未确证，成功不等于查明或修复Docker平台；SSE首次超时根因未确认。旧receipt安全拒绝、旧比较需复核、owner粗锁、性能/监控/清理/uncertain处置等待办继续保留。E10须另行取得模型/调用范围/预算授权，最迟WP-09验证，本次不授权付费请求；真实资料门槛NOT_MET最迟WP-10/真实效果验收前补齐。

WP09当前收口与历史E10描述区分：上述WP01—08的NOT_VERIFIED均为当时基准，不改写原报告；WP09已依据r1/r2限定通过并获用户接受，仅覆盖实测deepseek-flash。Linux BGE部署仍未验证，真实资料NOT_MET最迟WP10/真实效果前；同任务流程、混合模型排序及既有非阻断待办保留。


## 独立产品验证切片：资料与提案预览

2026-09-19T09:55:03.532003+08:00：用户授权调整执行顺序，前置少量WP14界面能力，状态ACCEPTED（限定本地合成资料与人工测试候选预览），用户于2026-09-19T12:07:33.456891+08:00接受，见[接受记录](product-preview/acceptance.md)。见[切片契约](product-preview/contract.md)、[结果](product-preview/result.md)、[启动及体验步骤](product-preview/runbook.md)。

已有React内可操作本地资料上传/真实解析索引/冻结会话检索/测试候选校验/原文定位；新增薄预览接口复用WP04—10，不改WP10算法，生产默认无可信规则。本地URL http://127.0.0.1:5180 。仅新专用synthetic测试库/存储，所有候选明确非AI生成。原执行阶段证据：接口18项定点、前端typecheck/build及四候选/错误/刷新亲测；首轮失败保留。后续r1/r2/r3审核及整改证据分列于接受记录，当前限定接受依据r3，不将原执行统计冒称最终全量重跑。

WP00—10原接受范围保持；此预览切片不等于WP14正式接受。该切片的历史部署与停止点见[部署记录](product-preview/deployment-r1.md)；后来获授权的WP-11另见本文件工作包表及[实施结果](phase-04/wp-11-result.md)。真实资料NOT_MET及原截止未满足、E10限定结论、Linux BGE未验证、SSE/启动/Compose根因与既有待办均保留。


### 上传提示与非虚构资料待审核入口（后续改进）

2026-09-19T14:10:12.606782+08:00：ACCEPTED（限定上传提示与资料待核实入口），见[接受记录](product-preview/material-intake-acceptance.md)。INTAKE-001依据r2关闭；r1接口/PDF等证据与r2的22项及浏览器证据分列，同任务限制和首次取证异常保留，不声称最终全量回归。PREVIEW-001仅提示/门禁、PREVIEW-002仅性质与待核实解析子项完成，大文件/OCR/正式资料审核检索及真实资料NOT_MET保留。原切片及WP00—10范围不变；后续WP-11状态见工作包表。原5180已更新并通过必要冒烟，见[本次部署记录](product-preview/material-intake-deployment-r1.md)；原库/storage/访问身份保持。


## DKVB/P0299资料检索与原页定位切片（独立实施记录）

ACCEPTED（限定专题资料检索与原页定位技术范围），见[接受记录](product-preview/dkvb-topic-acceptance.md)。DKVB-001依据r2关闭；r1、整改自测及r2证据分别保留，同任务审核限制及首次数据库环境失败不抹去。三份PDF仍needs_ocr/非虚构待核实，两份整理正文仍synthetic、formal_usable=false；不代表AI诊断、观察闭环、正式资料资格或真实维修效果。用户授权更新现有5196，仅加载已审核后端；5196已仅更新API并通过原会话/标题映射/S02原页冒烟，见[部署记录](product-preview/dkvb-topic-deployment-r1.md)；原库/storage/身份及前端保持。登记worker当前不存在，本轮未操作。5180不操作，原接受范围保持；后续WP-11状态见工作包表。真实资料NOT_MET及原截止未满足、历史未确认根因和既有限制保留。


## DKVB/P0299可信诊断协议与引导闭环 r1（WP-15 后产品纠偏切片）

**IMPLEMENTED_NOT_ACCEPTED。** 见[契约](product-preview/dkvb-trusted-protocol-contract-r1.md)与[结果](product-preview/dkvb-trusted-protocol-result-r1.md)。本切片为 `dkvb-p0299-guided-demo@1.0.0` 登记版本化、服务端可信且仅限 `synthetic/DEMO/formal_usable=false` 的有限关系：CHK-05 localized→CHK-06、not_found→CHK-08、inconclusive→可继续填写的补充定位卡，并登记 CHK-06→CHK-07 以证明不是静态第二卡。关系绑定 owner/case/epoch、冻结 manifest、车辆 profile、有效观察与来源；最终候选仍经过 ProposalService 及原事务发布门禁。浏览器 A/B/C 三路及 A 的第二步已在独立 5225/8225 实例通过，刷新和来源定位通过；集成1项、受影响前端20项、typecheck、OpenAPI check、Ruff及独立构建通过。使用本机BGE-M3建立1024维隔离索引；确定性协议路径没有工具或DeepSeek调用。真实资料仍`NOT_MET`，未登记关系、真实维修结论及生产能力未验证；WP-16/17未启动，WP-00—15接受记录不变。
