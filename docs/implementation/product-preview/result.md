# 资料与提案预览切片结果

时间：2026-09-19T09:55:03.532003+08:00。状态：IMPLEMENTED_NOT_ACCEPTED，等待用户体验与一次集中检查。WP00—10接受范围不变；WP11—17均NOT_STARTED。

现在可以在浏览器上传/选择本地Markdown或PDF，查看实际任务与不可变原文，用本地E5检索，并把标记清楚的测试候选交给现有ProposalService校验。已亲测授权虚构Markdown的完整链路；不是AI自动生成、诊断工作台或正式发布。

入口：<http://127.0.0.1:5180>；[体验及启动/停止步骤](runbook.md)。访问令牌只在本机忽略目录内。服务已留运行供用户体验，只监听127.0.0.1。本切片没有付费调用、没有读取真实模型费用账本或私有.env。

## 实际改动

- 原React项目frontend/index.html、src/main.tsx、src/style.css；新增src/api.ts与从实际OpenAPI导出的src/api-schema.ts。没有另建项目或前端依赖。
- 新增backend/app/product_preview.py：单独启用的薄工厂，复用原create_app/认证/资料/索引/检索/证据服务。新增带cookie/Origin/CSRF的POST cases/{id}/proposal-preview，只由服务端取得owner/revision和构造上下文，默认无规则、不发布。
- GET preview/config、preview/source为认证读接口；health只返回隔离实例标识。固定test/synthetic及专用DB前缀，拒绝付费模型凭据，不接受客户端profile或数据库路径。
- 新增scripts/product_preview.py、export_preview_types.py、verify_product_preview.py及tests/product_preview/test_api.py；文档契约、API/schema、原文来源映射与本轮证据。无新迁移、无既有后端业务源码改动。
- STATUS仅附加本切片当前停止点，不接受WP14。

## 真实数据与链路

专用体验库xiutu_test_preview_a276917a3275、独立storage UUID目录；测试另建两个新库，未复用历史审核库。运行状态详见[evidence/runtime-state.json](evidence/runtime-state.json)：0008_model_indexes，1份文档/1版本、89 chunks、1个ready的384维E5索引；ingest/index各1次成功，1个冻结会话、1份证据快照、0份measurement_specs。只有资料任务，没有诊断图或报告任务。

[source.json](source.json)核对原虚构源与既有可追溯副本SHA256一致：e4896ccde323186e8c2c01ca5187b3edfa25977b5a74cb6be45f1a682dedd888。没有增加手册片段或修改原句，没有把原文树/指令当成可信规则；筛选用SYNTH-F/SYNTH-C是单独演示元数据，不冒称源文有精确发动机认证。

## 本轮验证（不是审核结论）

| 检查 | 实际结果与证据 |
| --- | --- |
| 新增接口首轮 | 17通过/1失败/0错误/0跳过，1条既有Starlette警告，exit1；targeted.log/xml。失败是新增测试把原logout契约200误写204；未修改业务接口 |
| 修正预期后 | 18通过/0失败/0错误/0跳过，1条同样警告，exit0；[tests-b4a9bc53](evidence/tests-b4a9bc53/targeted.log)及XML/commands。涵盖认证、CSRF/Origin、owner越权404、context/profile注入422、默认无规则、来源hash、OpenAPI与退出撤销 |
| 前端 | 首次typecheck有3项可选字段类型错误，保留typecheck-first.txt。补正后typecheck/build通过；随后状态措辞、异步按钮保护、持续警示/定位收尾后再运行受影响typecheck/build，均exit0。最终29模块、JS241.32kB/CSS5.37kB；frontend-ui-commands.json含时间及命令 |
| 浏览器 | 真登录→上传授权源→真实worker解析→明确合成审核→真实本地E5索引→冻结会话检索→绑定真实引用→四候选→原文高亮；详见[browser-checks.json](evidence/browser-checks.json) |
| 成功/缺项 | 合法区域accepted=true/candidate/published=false；原貌位置表作为步骤位置返回LOCATION_UNCERTAIN；无支持主张CLAIM_UNCERTAIN；无规格measurement返回SPEC_REQUIRED及其他具体缺项 |
| 错误 | 非法JSON在页面报错；profile=formal额外字段由真实接口返回VALIDATION_ERROR；文件选择器提交非法UTF8 Markdown被INVALID_MARKDOWN_ENCODING拒绝，原已就绪文档保留 |
| 刷新/生命周期 | stop/start仅本轮进程，exit0；重新登录后原版本与索引状态保留。页面刷新保留doc/version/case定位；不假装候选已持久发布 |
| 布局/截图 | 默认窄屏可操作，1280×900双栏DOM核对无横向溢出，随后重置视口。实际截图见下；不声称完整WP14三尺寸验收 |

实际命令cwd均E:\Work\xiutu-v5，详见evidence/tests-commands.json、tests-b4a9bc53/tests-commands.json、frontend-commands.json、frontend-ui-commands.json。测试成功后文件仅移动到tests/product_preview/test_api.py（内容不变），配套runner选择更新；专用库测试不混入旧标准入口。未重跑历史全仓/第二环境/BGE评测/E10。

只读状态核对首次误查runs.attempt而exit1，后改读jobs.attempt成功，记录runtime-state-first-error.txt；没有数据或业务改动。首轮失败traceback含隔离TestClient的临时CSRF材料（对应进程已退出），原日志不对外分发；自动审批拒绝了覆盖脱敏/复制原件操作，本轮遵照拒绝保留原文件不动，不包含任何开发/模型密钥。

## 实际发现的适配差距

1. **原资料确实不足**：虚构Ux不是物理单位，原资料缺少真实车型标准/正式Spec；本轮库也没有批准测量规格。页面仅报告缺项，未补造阈值。
2. **当前字段映射不支持**：原位置表有位置文字，但作为location字段仍LOCATION_UNCERTAIN；需要未来独立讨论表格/自然句式映射。本轮保留原貌与算法。
3. **引用不能支持主张**：真实位置表引用不支持“立即更换且排除其他部件”；服务返回uncertain，页面不当作缺资料或确定维修矛盾。
4. **产品未实现**：真实AI候选生成、持久图、观察写入、报告、完整规则/规格编辑页面未提供。原文证据有多个时全部列出，尚无逐字段自动语义匹配来源的产品能力；按钮明确为“本候选依据”。
5. 预设四例限定该授权源的P01位置表，不是诊断规则；任意资料可看片段并手动编辑JSON。刷新不保存编辑草稿；文档选择不任意扩大/缩小服务器冻结manifest，新资料需新会话。原文按连续字符串高亮，重复相同文本的精确多位置导航仍是后续适配项，locator可展开核对。

没有通过扩大正则/添加部件模板制造通过。所有上述适配建议留待用户体验后集中处理，不借页面实施WP11或完整WP14。

## 保留与保护

真实资料NOT_MET且原WP10截止未满足；E10沿用WP09已限定结论，无新验证。Linux BGE、SSE/启动/Compose根因、同任务历史流程限制及原非阻断待办保留。无生产恢复、真实维修效果或完整阶段接受。

结束保护见evidence/final-protection.json：旧63文件与原虚构源、历史报告/接受/证据、既有迁移/业务代码和Git index核对。基线已有文件只允许frontend三文件与STATUS变化；无提交/推送或index调整。

## 实际截图

![候选通过，仅是候选](evidence/candidate-pass.png)
![实际引用高亮](evidence/source-location.png)
![缺少规格](evidence/missing-spec.png)
![真实上传错误](evidence/upload-error.png)
