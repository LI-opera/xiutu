# 上传提示与资料待审核入口：实施结果

状态：**IMPLEMENTED_NOT_ACCEPTED**，完成时间：2026-09-19T12:34:28.052332+08:00。等待一次新增差异集中检查；不自行关闭PREVIEW-001/002。本次没有部署5180。

## 现在能做什么

新表单显示服务端实际文件上限、选中文件名及精确字节数。上限内和恰好等于上限可提交，超限按钮禁用并显示中文原因；后端仍按实际接收字节拒绝超限，413转为清楚的请求过限提示，失败不切换原资料上下文。

普通上传必须明确选择合成或非虚构待核实。两类使用既有DocumentInput；非虚构不再填入虚构车型，来源/许可unknown，车型/年款/发动机可空。文件名只是title；无来源说明保存“来源未知，待核实”，不假造出版来源。非虚构可查看真实解析结果、原文、分页切块和locator；不能走合成审核，不能索引或加入合成会话。专用虚构样例及原合成审核/索引/检索保留。

## 实现及边界

- backend/app/product_preview.py：配置返回Settings.upload_max_bytes；预览专用PreviewDocumentService在原review前通过owner/document/version读取不可变metadata，synthetic非true时403 PREVIEW_REVIEW_SYNTHETIC_ONLY。复用原DocumentService，正式服务及资格算法不改。
- frontend/src/material-intake.ts：明确性质、大小比较、413提示、元数据构造及年款验证。
- frontend/src/main.tsx：实际表单接线、未知字段、合成审核控件隔离、版本元数据/切块查看。成功才changeContext；失败保留原状态；既有代次守卫不改。
- frontend/scripts/material-intake.test.mjs、tests/product_preview/test_material_intake.py：新增定点回归。
- api-schema.ts及openapi.json由现有导出脚本生成；无手拼第二套API。同步本轮契约、runbook、issues进展及STATUS独立记录。

不修改旧迁移、Upload字节限制、formal/synthetic门禁、WP10判断或历史资料元数据。默认25MiB不变；表单合成示例采用固定演示范围是显式测试含义，非虚构不继承它。专用授权虚构文件仍有原授权来源/私人使用声明；普通本地上传不自动授予private_use。

## 命令、版本和结果

cwd均为E:/Work/xiutu-v5；精确时间/argv/退出码见evidence/material-intake/commands.json、api-fix-command.json。

| 命令/项目 | 结果 |
| --- | --- |
| node --test frontend/scripts/preview-context.test.mjs frontend/scripts/material-intake.test.mjs | 18通过，0失败/跳过；含原10项上下文与新增8项大小/元数据 |
| python -B scripts/export_preview_types.py | exit0 |
| npm.cmd --prefix frontend run build -- --outDir E:/Work/xiutu-v5/docs/implementation/product-preview/evidence/material-intake/dist | exit0，含tsc --noEmit；Node24.14.0；未写用户dist |
| 新库prepare_database、alembic upgrade head | 各exit0，仅准备本轮隔离环境 |
| pytest tests/product_preview/test_material_intake.py tests/product_preview/test_api.py ... | 首轮25通过、2失败、0错误/跳过，1条既有Starlette警告 |
| pytest tests/product_preview/test_material_intake.py -k nature_metadata ... | 修正夹具后仅2通过、3未选中，1条同警告；没有全套循环重跑 |

两个失败为测试存储配置：TestClient上传到tmp_path，进程内Worker的Settings仍读取实例DATA_PATH，导致SOURCE_UNAVAILABLE；只给该测试monkeypatch DATA_PATH=tmp_path，未改解析实现/预期断言。test-first-run.py、api-tests.log/XML保留原失败，api-fix.log/XML保留复跑。最终生产代码与已构建版本相同，只有夹具目录配置在首轮后修正；不冒称最终27项整组重跑。

后端1023/1024/1025字节边界使用仅本轮测试Settings=1024，分别202/202/413；文件字节计量不依赖Content-Length，超限没有文档记录。两类真实worker解析、原文/chunks、非虚构审核403及空manifest均经过PostgreSQL。前端相同边界比较和非虚构已知字段保真/未知null另有确定性测试。

## 浏览器亲测

独立 http://localhost:8198，新库xiutu_test_preview_a78c81939c15、新storage/actor/token及独立dist；与5180的127.0.0.1 cookie主机隔离。

- 普通入口选择“虚构/合成”，上传授权虚构文件原样副本（28494字节）；真实解析→演示审核→本地E5索引ready→检索有命中。不是付费模型或质量评测。
- 选择26214401字节人工占位文件；实际上限26214400字节，明确中文提示、按钮禁用，原就绪版本保留；没有提交此超限文件。
- 选择无效编码人工文件，真实后端拒绝INVALID_MARKDOWN_ENCODING；原版本、索引、编辑及原文保留。
- 选择“非虚构来源资料，尚待核实”，所有可选字段留空，上传143字节人工流程夹具。该载荷明确自称测试文件，不是伪造真实维修手册。上传成功清除旧编辑/命中/原文；实际解析完成、待审核、无合成确认按钮、检索禁用。
- 展开元数据：synthetic=false、source_status/license_status=unknown，全部适配字段null；原文、切块及locator真实可读。

browser-checks.json与nonfiction.png保存证据。一次浏览器断言因快照把JSON引号转义而失败；保留记录，改读实际pre.textContent后JSON解析验证同一条件，不改业务或弱化断言。没有重新上传以制造通过。

## 亲自验证及剩余缺项

本轮8198已停止，仅保留测试库/存储和证据供审核；5180继续原已接受版本，不包含本次改进。审核可复用现有环境运行上述状态/API定点命令，并以独立构建及隔离实例重复两类入口。部署需用户另行授权；不要直接运行默认build覆盖用户dist。

Markdown/支持的文本PDF沿用既有解析能力；本轮浏览器仅测试Markdown，未重新验证PDF整链。用户实际PDF路径、大小、文字层/扫描情况仍未核实，未访问该文件，不能声称支持或已测试220MB整本。无分片、拆书、OCR，超限文件仍不能上传。

非虚构声明不证明正确、许可、适配或正式可用。没有真实资料审核平台、正式索引/诊断会话或可信规则自动生成；元数据误填不改历史，需重新准确声明上传，许可仍待后续核实。真实资料NOT_MET及原截止未满足、历史SSE/Compose/启动根因、Linux BGE限制和同任务流程限制保留。

没有付费调用、读写真实费用账本、提交推送或进入WP11。本轮为执行者自测，不是审核/用户接受。
