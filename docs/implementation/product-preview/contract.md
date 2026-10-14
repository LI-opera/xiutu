# 资料与提案预览切片契约

本次是用户授权的执行顺序调整，少量WP14界面前置，不启动完整WP11/WP14，不改变WP00—10接受范围。实现于原React项目；后续把资料选择、来源面板、候选结果组件并入正式资料中心，不另建项目或业务引擎。

## 文件与接口

新增backend/app/product_preview.py：专用应用工厂，拒绝非test/synthetic或非新xiutu_test_preview_*目标；复用create_app所有既有路由及服务，不改生产main入口。新增POST /api/v2/cases/{case_id}/proposal-preview，输入为实际ProposalEnvelope；cookie/Origin/CSRF沿用writing；服务端查当前owner case与revision构造ProposalContext，只调用ProposalService，无可信规则注入、无发布、无观察/报告写入。case_id是资源定位，不是身份，越权404。结果accepted仅候选校验通过。

前端使用已有documents upload/list/version/chunks/content/review/reindex、runs GET/cancel、cases create/get、case evidence search/bind接口。新GET /api/v2/preview/config只返回演示标识与固定车辆筛选元数据；不返回DB路径或secret。原文纯文本呈现，不执行Markdown HTML/脚本。预览端点受同源安全规则保护，响应no-store。

frontend/src在原项目实现四步页面与共享API client；从专用应用OpenAPI生成TypeScript类型（脚本保留），没有第二套业务字段真相。构建产物由同一loopback应用提供，同源cookie，无代理身份绕过。新增scripts/product_preview.py管理本轮单独API/worker进程、独立新库和存储；默认不加载.env，清除模型secret配置，无LLM调用。

## 数据与测试候选

原虚构源按字节复制，source.json记录来源和SHA256，所有上传及演示元数据synthetic；只在服务端固定test/synthetic环境运行，浏览器不能切换profile或指定DB。模型沿用本地E5作真实索引/检索，不进行质量评测或付费请求。人工按钮仅确认合成演示源，不表示真实资料资格或规则获准。

预设候选是明确可查看的测试JSON，不是AI生成。用原文P01位置表行创建有据区域正例；同一原貌表行作location暴露句式不支持；使用真实引用但改成不被支持的主张；无Spec的measurement请求显示规格/工况缺项。候选不作为固定诊断树，只验证当前通用服务。任意资料也可手动选择片段、绑定证据并编辑候选JSON。没有新增部件专用规则或结论模板。

## 状态、错误与边界

任务轮询只呈现实际API状态，无百分比假进度；提供真实取消、刷新及明确错误。URL保留doc/version/case定位，刷新读取DB，不以浏览器缓存伪装状态。数据刷新/异步请求切换不能将旧文档结果混入新选择。

原因呈现区分：原始资料确实不足（需人工核对）、当前字段/句式映射不支持、校验拒绝/依据矛盾、产品尚未实现。不得把LOCATION_UNCERTAIN或不支持句式概称维修资料无依据；错误码与原始detail可展开，相关引用可打开版本原文。不存在的字段也明确无可定位引用，不造原文。

不做持久图、观察提交、正式报告、完整工作台、规则管理、通用NLP。真实资料NOT_MET及原截止未满足，E10既有限定结论、Linux BGE未验证、历史启动/SSE/Compose根因及同任务流程限制保留。

## 验证顺序

基准→薄接口及隔离门禁/认证/跨owner/CSRF测试→真实资料与worker/检索/预览链→生成schema、前端typecheck/build→浏览器成功/句式限制/缺规格/错误/刷新与截图；不运行历史全仓、前端第二环境或付费模型。只新增本切片证据/结果并在STATUS附加记录，WP11—17仍NOT_STARTED，完成后等待用户体验与集中检查。


## r1定点整改：上下文与历史来源

资料/版本/会话切换使用单调上下文代次，集中失效命中、引用、候选、结果、来源和审核确认；请求完成时核对代次，包含A→B→A。上传成功后才切换；失败保留原上下文和有效结果。普通轮询不改变代次，不清除编辑。结果仍仅候选校验，不改变WP10。

新增只读 GET /api/v2/preview/versions/{version_id}/chunks/{chunk_id}/source：cookie认证，UUID参数；服务器关联documents.owner_id、version.document_id和chunk.document_version_id，返回document_id/document_version_id/chunk_id/sha256/locator（OpenAPI PreviewSourceMapping）。无权限或关系不符404，未登录401；不接受owner/profile，不扩充manifest。该接口只映射已授权原文，不表示当前资料可作新证据。读取正文仍经既有document/version内容接口。历史命中不按latest_version_id替换；映射失败清空来源并明确报错。

create_preview的可信启动参数static_dir可指定隔离构建目录（不是HTTP参数），默认仍frontend/dist。本次测试仅localhost专用实例提供独立构建，未改用户5180的构建或服务。PREVIEW001/002限制不变。状态仍IMPLEMENTED_NOT_ACCEPTED，待定点复核。
