# 预览切片 PREVIEW-003 / PREVIEW-004 定点复核 r2

日期：2026-09-19。结论：**CHANGES_REQUIRED**。

- **PREVIEW-003：UNRESOLVED（主要状态清理已修复，尚有旧轮询错误跨新会话显示的分支）**。
- **PREVIEW-004：RESOLVED（限本切片授权历史版本原文映射）**。
- 只需对下述剩余分支做最小修正及定点验证，不重开整包。PREVIEW-001/002继续按原改进/需求处理。
- 本任务参与过实施、整改及前次审核；本轮是审核角色，不是不同任务独立审核。未现场修改实现，不替用户接受。

## 基准及运行隔离

读取适用指令、STATUS、review-r1、remediation-r1、当前契约、代码、测试、整改封存和原反例。项目及上级未发现AGENTS。当前Git根E:/Work/xiutu-v5，main无HEAD；使用文件清单及index固定基准，没有仅依赖git diff。

`evidence/review-r2/baseline.json`与结束`protection-final.json`：**3184条保护文件哈希匹配，结束变化为空**；整改声明的4个既有文件/新增状态辅助代码及测试与封存一致，原报告、失败证据、STATUS、接受记录、issues和旧迁移未变。index保持`c451d6e78b8f29fc818002923a19fb1a888139ced20679ad545f75e9692a9ec6`。原虚构源哈希仍为`e4896ccde323186e8c2c01ca5187b3edfa25977b5a74cb6be45f1a682dedd888`，没有旧项目写入。

确认现有xiutu-v5-postgres-1运行、项目标签xiutu-v5、5433仅loopback。新建审核库`xiutu_test_preview_ce97f63b4deb`、独立private/storage；审核URL **http://localhost:6492**，合法Origin同值，未在用户127.0.0.1主机名下登录。独立构建在本轮证据目录dist，通过可信static_dir启动；未覆盖frontend/dist。

**5180仍为旧版，修复未更新到用户实例。** 未重启用户API/worker、未修改用户数据；结束5180 health=200。只停止本轮PID及创建时间匹配的6492 API/worker，保留审核库/存储。未读私有.env、真实费用账本或用户未指定资料，无付费调用。

## 本轮亲测与历史证据

cwd均为E:\Work\xiutu-v5；精确argv、开始/结束时间和退出码见commands.json。所有新输出在`evidence/review-r2/`。

| 本轮动作 | 结果 |
|---|---|
| `node --test frontend/scripts/preview-context.test.mjs` | exit0，4通过，0失败/跳过，state-tests.log |
| `npm.cmd --prefix frontend run build -- --outDir <本轮>/dist`（包含tsc --noEmit） | exit0，build.log，未触碰用户dist |
| prepare_database新库、`alembic upgrade head` | 各exit0，仅审核库 |
| `python -B -m pytest tests/product_preview/test_api.py -k source_mapping -q --tb=short --basetemp <新private>/pytest --junitxml <本轮>/api-tests.xml` | exit0，**4通过、18未选中、0失败/错误/跳过，1条既有Starlette警告** |
| `seed.py`、`seed.py v2` | 各exit0；真实上传、解析、人审、E5索引；最终OpenAPI引用PreviewSourceMapping |
| `verify_versions.py` | exit0；旧会话manifest、v1原文/hash/locator、新会话实际范围均验证 |
| CUA浏览器 | 失败上传保留、成功B清理、旧v1定位、编辑保留、上下文切换、映射失败、迟到响应；browser-checks.json |
| 审核时序夹具arm_old_error/arm_aba/arm_mapping_error/arm_aba_success | 针对代码发现的轮询错误缺口及必要来源失败反例；记录如下，未替换业务权限/校验逻辑 |
| instance_runner.py stop、finalize.py | exit0，只清理本轮进程；结束保护通过 |

不将此前22项与最后4项整改证据称为同一最终字节版本全量运行，也不与本轮4＋4累加为覆盖数。r1正常PDF及未变路径沿用原证据；未跑全仓、BGE质量、E10、第二环境或PDF解析全套。

## PREVIEW-003逐项结论

### 已通过

1. **A候选通过→上传失败**：本轮真实A候选accepted=true；无效UTF-8合成md上传失败，显示INVALID_MARKDOWN_ENCODING，原case/候选及通过结果保留。
2. **A通过→成功上传B**：旧命中/选择、候选JSON、通过结果、原文、审核确认清除；页面进入B实际状态。browser-checks.json有前后DOM，没有仅隐藏绿色提示。
3. **文档/版本切换、新建会话**：changeContext实际清空依赖状态；普通上下文编辑在轮询后仍保留。新会话不把旧候选当当前结果。
4. **代次检查接入实际页面**：main.tsx的upload、refresh、search、preset、validate、openSource/evidenceSource和run错误处理实际捕获/核对ContextEpoch，不只是单独测试类。来源正文读取完成后仍复验，A→B→A也递增代次。
5. **A→B→A的迟到响应**：审核专用ASGI中间件先执行实际服务和鉴权，再有界延迟一次响应。分别在v2轮询等待期间B→A，释放成功200或合成错误503后，页面保持当前v2、没有旧错误。对应aba-success/aba-error started/returned记录与DOM时间。成功响应内容与当前版本相同，因此页面观察只证明未见污染；“旧回调会被丢弃”的结论同时依据实际refresh代次分支代码，不靠相同内容的截图单独证明。

### 尚未关闭：同文档新会话后旧轮询错误仍显示（原PREVIEW-003剩余，P2）

- **位置**：`frontend/src/main.tsx:83-84`，自动轮询effect的`refresh().catch(...)`；上下文改变在45—49行，新建会话入口158行。
- **根因**：catch只检查闭包`ended`，没有检查发起该次轮询时的ContextEpoch。effect依赖是session/doc/vid，不包括case/代次。相同doc/vid的新建会话使changeContext递增代次，但effect未销毁，ended仍false。refresh的成功分支会检查代次，失败分支直接跳出到这条未保护catch。
- **实际复现**：已有case `710c6ee8-9b8d-46b3-a462-a1260a98f06a`、v1已就绪；审核中间件在11:10:38.402收到完成真实服务的轮询200后暂挂。11:11:00.164浏览器点击“新建预览会话”，DOM确认旧case及候选/来源已清除且无错误。该请求在夹具30秒上限到达后返回503 `AUDIT_HOLD_DEADLINE`。11:11:18.773页面却显示该旧上下文错误。之后的新正常轮询不能解释该特定错误码。
- **证据**：same-version-old-error-started.json、review_app.py的30秒上限分支、browser-checks.json的new_case_before_release/first_delay_after_new_case、stale-poll-error.png。首次DOM取值工具出现selector超时，导致人工release文件晚于夹具deadline；保留实际deadline错误，没有循环重跑成通过。这里证明的是**旧请求错误在新上下文显示**，不是宣称真实数据库发生了故障或重新引入旧成功结果。
- **影响**：用户已重置上下文，仍被旧请求误报当前失败，违反本次明确的迟到错误失效要求。未发现后端数据写坏、权限绕过或候选错误发布。
- **最小整改**：每次自动load发起时捕获代次，catch在显示错误前同时校验该代次/当前上下文及effect生命周期。不能只给成功分支加检查，不能一律吞掉当前上下文错误。顺带使新建会话入口的即时refresh错误经过同一有界处理即可，无需更改WP10或业务服务。
- **定点复核**：同doc/vid，挂起旧轮询→新建会话→释放错误，应不显示旧错误；当前上下文错误仍明确显示；A→B→A、成功迟到和同上下文编辑继续有效。无需重跑整包。

现有4项状态测试都只执行ContextEpoch/模拟callback，不能覆盖上述effect接线缺口；它们通过不等于所有页面回调均安全。

## PREVIEW-004：关闭依据

- 后端`product_preview.py:79-94`：映射查询同时关联documents→versions→chunks，限定actor owner、真实version和chunk。无客户端owner/profile，UUID本身不授权。该只读映射不修改manifest，不代表资料当前可用于新证据。
- 本轮4项source_mapping测试覆盖当前/旧版本准确返回、错误version及跨owner404，每项注销后401。旧原文内容与sha一致；SQL join保证document/version关系。
- OpenAPI最终声明PreviewSourceMapping，required字段document_id/document_version_id/chunk_id/sha256/locator、additionalProperties=false；本轮真实输出相符，见mapping-openapi.json及http-version-proof.json。
- 真实v1冻结会话→同文档v2解析/审核/索引ready后，浏览器旧命中仍打开`.../versions/eff488e9-bd5f-441b-b65c-fdaa91642661/content`。HTTP实测hash为原虚构源hash，locator与检索命中一致。v2=`578e8ad4-f976-4c35-bdf4-042b82bbdf6c`，旧manifest不包含它。
- 新case按真实服务返回manifest，包含符合资格的v2，也可包含符合条件的v1；未假定“只能最新版本”。
- 失败清理：先打开有效命中原文，再对另一映射响应注入明确503，页面显示错误，来源区退回空提示，无上一片段原文。注入仅在新审核应用外层，实际映射鉴权/查询先执行；401/404由正常接口测试证明，未以注入替代权限验证。

## 审核准备异常与证据边界

- 两次CUA读取textarea.value超出工具selector deadline；DOM快照确认元素和编辑内容，改用快照核对，没有修代码或放宽产品断言。
- 生成迟到成功夹具的首次shell引号错误在脚本执行前发生，随后here-string正确生成并只执行一次该用例。harness-errors.txt保留说明。
- 同文档旧轮询的第一次夹具达到有界deadline；其错误恰在新会话后显示，作为残留缺陷保留。不声称历史SSE/Compose/启动超时已解释或修复。
- 注入仅用于合成错误及确定时序；实际成功链路、版本关系、权限、DB读取、解析和索引均走当前服务。未重写或替换业务校验器。

## 接受建议和停止点

建议关闭PREVIEW-004，保留PREVIEW-003上述一个错误回调缺口；完成最小修正后仅复核该差异。总体暂不建议按“迟到成功/错误均正确隔离”接受。PREVIEW-001/002仍为原限制/改进需求，不扩大到大文件、真实手册平台、正式诊断或WP11。

同任务流程限制、真实资料NOT_MET及原截止未满足、E10既有限定结论、Linux BGE未验证和历史未确认根因均保留。未修改实现、STATUS、接受记录、原问题清单、历史证据或Git index；不提交推送、不付费。

5180仍运行旧构建，修复尚未更新到用户实例；审核6492已停止，等待用户决定。
