# 预览切片 PREVIEW-003 / PREVIEW-004 整改 r1

日期：2026-09-19。状态：**IMPLEMENTED_NOT_ACCEPTED，执行者自测完成，等待两项差异的定点复核**。本报告不关闭审核问题、不代表REVIEW_PASS或用户接受；未重开WP00—10，未进入WP11。

## 范围与基准

读取STATUS、contract/result/issues、review-r1和对应证据及前端/预览API；项目及上级未发现适用AGENTS。开始核对r1基准与review-seal，3144个基准条目匹配，无未解释差异；issues.md仍为已解释的协调记录，未修改。

既有文件仅修改：

- `frontend/src/main.tsx`：集中上下文失效、异步代次校验、实际版本原文映射。
- `backend/app/product_preview.py`：最小只读映射接口及可信启动参数static_dir。
- `tests/product_preview/test_api.py`：追加4个映射/权限用例，原断言未改。
- `docs/implementation/product-preview/contract.md`：追加本次状态、映射及隔离说明。

新增：`frontend/src/preview-context.ts`、`frontend/scripts/preview-context.test.mjs`、本报告与`evidence/remediation-r1/`。未修改WP10算法、上传限制、资料资格、迁移、STATUS、接受记录、原问题清单或历史报告/反例。测试没有用修改历史断言的方式消除失败。

## PREVIEW-003：依赖状态及迟到响应

根因：原upload成功时只替换doc/vid并清空case，没有清理旧命中、候选、成功结果及原文。

现在changeContext集中处理资料/版本/会话变化：清空命中及trace、选中chunk、quote、候选JSON、校验结果、原文地址/正文/locator、审核确认、任务/版本临时显示；同步URL。使用单调ContextEpoch，避免A→B→A时只比较资源ID误认旧请求。候选验证、绑定、检索、原文读取和轮询完成后检查代次；来源读取包含正文读取完成后的检查。错误回调也不把旧上下文错误写回当前页面。

上传仅在成功响应且上下文仍有效时切换；失败不失效原状态。正常轮询不递增代次，不清空编辑。新建会话仍由既有服务冻结范围，不自行填充manifest。

实测（browser-checks.json）：

- A真实检索/绑定、合法候选通过；无效UTF-8 Markdown上传失败，显示INVALID_MARKDOWN_ENCODING，A原URL及绿色通过保留。
- 随后上传独立合成B成功：旧绿色通过、命中/选中、候选JSON和原文均清除；B显示其实际待审核状态。不是仅隐藏提示。
- 同上下文“刷新真实状态”前后编辑内容逐字一致；新建会话后编辑、引用和原文清空。
- 切换到最新v2，再在真实PG表锁等待期间切换B，解锁后仍显示B版本`94c20f7a-29a1-4358-ade9-44c8d82c0fa8`及待审核状态，无v2迟到状态污染。锁时间/等待记录见late-poll-lock.json，35秒上限自动回滚。
- Node测试证明失效代次下迟到成功callback不发布、A→B→A不恢复旧请求、当前请求正常发布。此项为可控异步单元证明；真实浏览器额外验证轮询锁等待，不宣称穷尽所有网络时序。

## PREVIEW-004：真实版本关系定位

原inspectHit仅查docs.latest_version_id，旧冻结命中在同文档已有v2后失去document映射。

新增只读 `GET /api/v2/preview/versions/{version_id}/chunks/{chunk_id}/source`，以当前cookie actor关联documents.owner_id、document_versions.document_id和chunks.document_version_id。返回固定PreviewSourceMapping：document_id、document_version_id、chunk_id、sha256、locator。未认证401；越权或不匹配404；模型/浏览器不能传owner/profile。无写入、无manifest改变、无最新索引替换。映射只提供授权原文地址依据，不意味着资料获准用于新证据；正文继续走既有document/version内容权限入口。

前端每次清除上一次来源，取得映射并核对chunk/version后读取指定版本。失败明确报错，不静默保留另一片段的原文。原文中的HTML/脚本仍不执行。

真实HTTP+worker/E5验证（version-routing.json）：

1. v1解析、人审、索引，浏览器创建冻结会话。
2. 同文档上传v2（原合成源加明确标记的测试段落），独立解析、人审、索引ready；不修改原虚构文件或v1。
3. 原会话manifest仅v1；旧命中映射仍指向v1，原文件SHA=`e4896ccde323186e8c2c01ca5187b3edfa25977b5a74cb6be45f1a682dedd888`，locator与检索返回一致。
4. 浏览器刷新旧URL、重新检索并点击位置表，实际原文链接仍为`.../versions/c12f38c5-e1d6-4d9a-aaf0-99d5f7c78422/content`，未替换为v2。
5. 新建会话按现行服务实际冻结范围，包含已ready的v2；不声称新会话只包含最新版本（现行服务可同时冻结符合资格的历史版本）。

4个新增接口测试覆盖当前/旧版本准确映射、错误版本404、跨owner404，且每例注销后均401；原文内容与哈希一致。最后增加显式OpenAPI响应模型及SessionCookie声明，另定点4项通过。

## 实例与构建隔离

本轮使用新库`xiutu_test_preview_e076b521fc54`及新private/storage，真实API和worker；URL仅`http://localhost:5731`，APP_ORIGIN同步为该Origin。没有在127.0.0.1浏览器上下文登录新端口，也未放宽Origin/CORS。读取仅本项目受保护本地DB凭据用于连接，未读私有.env或真实模型账本，无付费调用。

构建命令明确指定`.local-data/preview-remediation-dist`；preview工厂static_dir是可信Python启动参数，非HTTP可控配置。用户5180的frontend/dist全程哈希不变，未重启其API/worker，结束health=200，**用户5180仍是旧版，修复未自动上线**。5731已仅按本轮PID及创建时间停止，库/存储保留。后续复核可复用证据脚本设计，但应使用新目录/实例，不覆盖本轮记录。

## 命令、版本与结果

cwd均为`E:\Work\xiutu-v5`；Node24.14.0，现有Python .venv。证据目录`docs/implementation/product-preview/evidence/remediation-r1/`，带数据库创建/迁移/首次切片测试的完整时间和argv在commands.json；最终映射时间和argv见mapping-final-command.json，浏览器记录含时间及实际DOM。

| 命令/检查 | 结果 |
|---|---|
| `node --test frontend/scripts/preview-context.test.mjs` | 4通过，0失败/跳过；state-tests.log |
| `npm --prefix frontend run typecheck` | exit0；typecheck-final.log |
| `npm --prefix frontend run build -- --outDir ../.local-data/preview-remediation-dist` | exit0；build-final.log；包含typecheck。Vite提示outDir在frontend根外且不自动清空，未加破坏性清理参数 |
| 原18项切片API（新库） | 18通过，1条既有Starlette弃用warning，exit0；api-tests.xml/log |
| `pytest tests/product_preview/test_api.py -q --basetemp <本轮>/mapping-tests --junitxml <证据>/mapping-tests.xml` | 22通过，0失败/错误/跳过，1条同warning，exit0；含新增映射测试 |
| 新增显式OpenAPI响应模型后 `pytest ... -k source_mapping ...` | 4通过，18未选中，exit0；mapping-final.xml/log。不是跳过强制测试，也不声称最终字节版本重跑全部22项 |
| `version_routing.py` | 首次exit1：验证脚本误期望审核200，实际202且approved/building；保留脚本和version-routing-first-error.txt |
| `version_routing_resume.py` | exit0；从同一已上传/已审核v2继续检查，未重复上传或审核；version-routing.json |
| `late_poll.py` | exit0；本轮库真实锁等待后回滚，无数据修改 |
| 浏览器 | A通过→失败保留→成功B清理；旧v1定位；刷新/新会话/版本切换及迟到轮询，见browser-checks.json及两张截图 |
| `instance_runner.py stop`、`finalize.py` | exit0；只停止5731，保护核对通过 |

验证准备中的另一次错误：编辑helper默认GBK读取UTF-8前端时停止，记录edit-first-error.txt；设置PYTHONUTF8=1后完成编辑，再分别保存final类型检查/构建输出。初始检查输出未覆盖。开发时只读检查发现源locator列名为locator_json，映射实现已在新增测试和浏览器执行前改正。没有产品测试失败后循环跑全量。

四轮数字不累加为独立功能覆盖数；未重跑历史364项、全仓、PDF解析全套、前端第二环境、BGE质量/E10或付费模型。最后OpenAPI模型变化未改变浏览器已验证的响应字段，最终4项验证该输出和权限；不冒称浏览器在这一纯响应声明变化后重新跑过完整链路。

## 保护、残余与停止

protection-final.json：仅上述4个既有文件变更；Git index仍`c451d6e78b8f29fc818002923a19fb1a888139ced20679ad545f75e9692a9ec6`，用户dist、STATUS、issues、历史审核/失败证据和接受记录不变，原虚构源哈希不变。没有提交、推送、旧项目写入或旧迁移修改。

PREVIEW001上传大小/提示、PREVIEW002真实资料入口保持原范围，未扩大上限或资料资格。真实资料NOT_MET、同任务流程限制、旧history、Linux BGE未验证、历史启动/SSE/Compose未确认根因和既有非阻断待办保留。本次迟到轮询通过不等于查明历史环境超时根因。

本轮仅执行者整改与自测，等待PREVIEW003/004定点复核；不自行关闭审核问题、不接受切片或WP14，不进入WP11。
