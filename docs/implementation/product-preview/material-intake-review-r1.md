# 资料接入改进集中审核 r1

结论：**CHANGES_REQUIRED**。PREVIEW-001的本轮大小提示/门禁已满足；PREVIEW-002的非虚构待核实与服务端隔离基本成立，但普通上传更换文件仍继承上一份声明，存在一项P2必须整改。暂不建议接受或部署本次新增差异；仅定点修复INTAKE-001后复核即可，不重开已接受预览切片或WP00—10。

本任务曾参与预览切片及本轮改进实施，本轮切换为审核角色，**不是不同任务独立审核**。没有修改实现、STATUS、issues、接受记录、旧项目、迁移或Git index；没有付费调用、读取真实模型账本、部署5180或进入WP11。

## 基准与保护

- 开始核对material-intake/delivery-hashes.json的3308项及seal.json的27项，全部匹配；具体文件SHA256、Git根/分支/状态/cached和未暂存摘要见本轮baseline.json。main无HEAD，已记录rev-parse HEAD的失败，不以无提交跳过审核。
- Git index：`c451d6e78b8f29fc818002923a19fb1a888139ced20679ad545f75e9692a9ec6`，开始/结束一致。结束再比全部开始保护文件无变化，包括历史报告、封存、接受记录、实现及用户frontend/dist。
- 交付文档只新增本报告与evidence/material-intake-review-r1，运行工件另存本轮私有隔离目录。旧虚构原文只读，结束SHA256仍为`e4896ccde323186e8c2c01ca5187b3edfa25977b5a74cb6be45f1a682dedd888`。
- 本轮已有资料/版本、审核、资格和上传服务按新增调用链审查，不重新验收旧包。未找到项目/适用祖先AGENTS.md。
- 本轮实例http://localhost:7138，数据库xiutu_test_preview_96d8c23031f5，私有独立storage及access配置见instance.json的目录指针（未封存秘密）。与用户127.0.0.1按主机隔离cookie。专用构建在本轮dist，JS为index-DAjSMcJE.js。
- 只复用已运行xiutu-v5-postgres-1（项目标签xiutu-v5，127.0.0.1:5433）。首次沙箱Docker读取被拒绝，正常提权后确认running；不是引擎故障。未重建/停止数据库。审核结束只按PID/创建时间停止本轮API和worker，测试库保留。
- 5180公开health为200；frontend/dist与开始一致，仍是此前已接受版本index-C4HAaDd2.js，**没有部署本次资料接入改进**。没有登录5180、重启其进程或读写其资料/会话。

## 本轮实际执行

cwd均为E:/Work/xiutu-v5。完整argv、时间、退出码见commands.json、audit-command.json、http-command.json；原始stdout和JUnit在同目录。未调用会改写源schema的导出器。

| 本轮命令/路径 | 结果 |
| --- | --- |
| node --test frontend/scripts/preview-context.test.mjs frontend/scripts/material-intake.test.mjs | 18通过，0失败/跳过；含原10项代次/guardedRefresh与8项接入测试 |
| npm.cmd --prefix frontend run build -- --outDir <本轮evidence>/dist | exit0，执行tsc --noEmit和Node门禁；独立Vite构建；outDir在项目外不清空的提示为预期 |
| prepare_database.py --name xiutu_test_preview_96d8c23031f5；alembic upgrade head | 各exit0，只准备本轮新隔离库 |
| pytest tests/product_preview/test_material_intake.py tests/product_preview/test_api.py -q --tb=short --basetemp <本轮私有目录>/pytest --junitxml <本轮>/api-tests.xml | **27通过**，0失败/错误/跳过，1条既有Starlette/AnyIO弃用警告；4.47秒 |
| pytest <本轮>/test_audit_intake.py ... --basetemp <本轮>/audit-pytest --junitxml <本轮>/audit-tests.xml | **1通过**，0失败/错误/跳过，1条同警告；补重复/伪造审核、已填写元数据、跨owner |
| python -B <本轮>/http_checks.py | exit0；真实无Content-Length超限413、无新增资料、PDF字节hash/页码核对、数据库归属 |
| CUA真实浏览器操作 | 合成上传/解析/审核/E5检索/候选通过、失败保持、非虚构PDF解析/定位通过；跨文件声明串用反例实际失败，保留截图与browser-checks.json |

每个测试实例本轮只执行一次，没有通过循环重跑掩盖失败。JUnit为本轮独立输出。没有重跑历史364项、第二环境、模型质量评测或未变PDF全套。

## PREVIEW-001：本轮子项满足

1. 页面GET preview/config读取真实32768字节测试上限（非默认25MiB）。选择32767/32768文件时可提交，32769时按钮禁用，中文显示精确大小、上限及不支持拆书/分片。页面接线为main.tsx:186—201及upload():105—106，非写死显示。
2. 27项内实际后端1024测试上限：1023/1024返回202，1025返回413。另对运行实例发送32769文件的HTTP分块请求，**不带Content-Length**，后端413 UPLOAD_TOO_LARGE，文档列表前后相同。Upload.on_part_data在写该片段前累计实际字节；不是仅相信前端或声明长度。
3. 413中文映射由本轮前端测试与main.tsx run.catch接线确认；真实HTTP413另有证据。**本轮没有在浏览器人工注入413**，不冒称该HTTP请求是页面发起；页面真实编码失败则亲测原版本/索引、命中、候选编辑、accepted及原文均保持。
4. 成功从A切换到PDF时，旧候选编辑/accepted和命中失效；原文按新版本重取。现有代次守卫仍用于实际refresh、upload及上下文路径，18项复用已覆盖的迟到/ABA状态测试，本轮没有重演全部历史时序。

未实现需求仍保留：大文件支持、220MB整本、分片、拆书、OCR；用户实际PDF路径、大小、页数和文字层均未核实。这不是上传容量提升或真实书籍验收。

## PREVIEW-002：已满足部分与必须整改

已满足：

- 初次进入普通表单性质为空且上传禁用；切换synthetic/nonfiction会清空适配输入。非虚构留空时source/license=unknown、scope均null（本轮接口及前端测试）；已填写源说明/车型/2020—2022/Family-A/Code-A准确入库，不自动变成verified/private_use。
- 非虚构页面明确声明“待核实，仅支持解析与原文查看”，没有合成审核控件，检索禁用；正式资格仍false。该标记只是用户声明，不验证书籍真实性。
- PreviewDocumentService.review:57—64先按owner/document/version读取已存不可变metadata。真实同key重复审核两次均403 PREVIEW_REVIEW_SYNTHETIC_ONLY，伪造synthetic额外字段422；没有审核历史、active索引或合成manifest。跨owner读取/审核404，原认证和CSRF测试通过。重建索引请求亦不获准；没有通过复用服务放宽资格。
- 明确选择synthetic的普通上传可实际完成解析、人工演示审核、E5索引、5条检索命中及合法测试候选。专用授权样例入口的代码保持原专用元数据，不读取或修改用户实际手册。

### INTAKE-001 / P2 / 必须整改：新文件继承上一份性质及来源/适配

位置：`frontend/src/main.tsx:185`文件onChange仅setFile；`:189`只有性质变化才setIntake(emptyFields)；`:107`提交直接消费全局nature/intake。`:111`成功changeContext也不重置上传声明。

最小复现（本轮实际浏览器和真实数据库）：

1. 选择audit-text.pdf（707字节人工PDF），选择非虚构待核实，填写来源`SYNTHETIC audit declaration A; no real manual claim`、车型Audit-A、2020—2022、Family-A、Code-A，上传成功。
2. 选择内容无关的next-unrelated.md；不再次选性质、不填B的来源/适配。页面仍为nonfiction且全部A字段保留，上传按钮可用。
3. 直接上传B。版本`8e9d3c68-61b5-40ea-909b-bd66c50bf1cc`的实际metadata（见browser-checks.json的new-file-inherits-declaration及刷新记录）仍为A的来源/完整scope，title已变为next-unrelated.md。刷新后仍可读相同错误关联，不只是展示缓存。

影响：不能确保每份文件获得独立明确的性质声明；旧来源及适配会污染新版本的不可变元数据。前一份若选择synthetic，下一份也无需重新确认即可沿用该性质。后者是同一表单状态根因的代码推论，本轮保存实测为nonfiction→nonfiction，不夸称另做了一轮错误合成审核。来源/许可仍unknown且非虚构审批门禁有效，所以没有证据证明已绕过正式资料资格；但违反本轮“不能从上一份资料继承”的明确要求。

最小整改：把性质与来源/适配草稿绑定当前所选文件。选择不同文件时默认清空并要求重新明确性质；若设计复用声明，必须有针对新文件的显式确认，不能隐式沿用。**同一文件上传失败应保留可修正的草稿及已有资料/候选/原文上下文**；不要用全局清空修复本问题。无需修改后端资格算法或历史入库元数据。

定点复核：A带声明→选B无声明→阻止提交/空字段；明确给B填写后准确入库；synthetic→另一个未知文件也需重新声明；同文件失败重试保留输入；现有成功/失败上下文测试不回退。仅新增前端状态与一次实际页面验证即可，不要求重开整包。

证据：browser-checks.json、inherited-declaration.png、pdf.png；原代码及SHA在baseline.json。本次没有修改实现或历史测试，浏览器失败结果pass=false原样保留。

## 小型文本PDF亲测

本轮使用tests/wp04_fixtures.py生成单页PDF，内容显著标为SYNTHETIC training / Not repair evidence。707字节，SHA256 `3e0429e80aa13de1cae825ad7c684239934536bb18803ee079b748c306e4fa59`。

通过新的非虚构声明表单测试其待核实处理路径，并不是把该测试载荷当成真实手册：上传→真实worker解析review_pending→1个page chunk→页码1 locator→授权原文链接。HTTP取回PDF与上传文件及version.sha256完全一致；page_issues为空、review pending、无active_index。页面显示layout_verified=false，未宣称复杂版式正确理解。browser-checks.json和http-results.json记录详情。

最初浏览器取证脚本用locator字段寻找数组未命中，实际响应字段为locator_json；随后按真实DOM读取保存同一响应，没有修改实现/业务断言或重跑上传。不是PDF解析失败。

## 历史证据、未验证与非阻断建议

- 执行者首轮前端18通过，接口25通过/2失败；之后仅修夹具DATA_PATH并复跑2项。原失败、test-first-run.py和修正后结果都保留。本轮最终接口27通过是新结果，不改写原历史，也不累加为不同覆盖数。
- 原preview acceptance/deployment限定范围保持；本轮状态测试复用已闭合的代次保护，不重新审核PREVIEW003/004。未做全仓、第二环境、BGE/E10、扫描PDF或用户实际PDF验证。
- 非阻断建议：当前索引门禁仍展示英文review_not_approved，可补中文释义；来源未知/许可待核实的说明已清楚，不因此拒绝整个服务端能力。正式资料审核平台、真实资料检索与元数据纠正机制继续作为后续需求，不在本轮要求完成。
- 真实资料NOT_MET、原截止要求未满足、历史SSE/Compose/启动根因未确认、Linux BGE未验证、既有同任务流程限制和其他待办继续保留。本轮成功不代表历史平台问题根因已解决。

## 停止点

只建议接受本轮已证明的大小提示、待核实解析和服务端隔离子项；**整项改进先修INTAKE-001再决定接受/部署**。5180未更新。没有写接受记录或修改STATUS。审核实例已停止，数据库/存储保留供定点复核；等待用户决定。
