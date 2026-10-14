# DKVB/P0299 专题检索与原页定位审核 r1

- 时间：2026-09-19 15:16—15:34（Asia/Shanghai）。
- 结论：**CHANGES_REQUIRED**。存在一项必须整改的来源映射错误；不建议现在接受整项“检索与原页定位”交付。
- 角色披露：本任务参与过本专题实施；本轮切换为审核角色，使用新数据和实际验证，但不称不同任务独立审核。未现场修改实现。
- 范围：仅本次专题差异；不重新审核旧工作包，不接受或启动 WP-11。

## 1. 基准与保护

已读取 STATUS、专题契约/结果及实现证据，结合实际 `dkvb_preview.py`、`dkvb_topic.py`、`dkvb-topic.tsx`、新增测试审核。当前交付9项、封存45项、封存构建3项全部匹配。Git为main、无HEAD（rev-parse退出128），不能据此省略未跟踪文件；完整Git状态/index清单已保存在 `evidence/dkvb-topic-review-r1/baseline.json`。

结束复核4798项源码、历史记录/证据及保护文件均无差异，Git index SHA256仍为 `c451d6e78b8f29fc818002923a19fb1a888139ced20679ad545f75e9692a9ec6`。封存构建未变，原包30项manifest大小/hash复验通过。详见 `protection-final.json`。

用户5180（PID8820）和5196（PID12172）始终保留，结束监听PID与开始一致；未改其数据、构建、令牌或配置。只停止本轮API/worker，见 `stopped.json`、`listeners-start.json`、`listeners-end.json`。没有访问私有.env/费用账本、付费请求、提交或暂存操作。

## 2. 本轮环境与证据区别

使用新库 `xiutu_test_preview_audit_e5c28fc8c0`、TEMP专用storage/registry、127.0.0.1:5197审核服务和独立worker；未复用执行者或用户数据库。复用已匹配的 `dist-sealed` 构建（JS `index-Cm_Gkvfa.js`），不重建/覆盖frontend/dist。

浏览器Cookie不靠端口隔离：审核外层包装只接受审核专用 `xiutu_dkvb_audit_r1` Cookie，转入原应用时仅映射此Cookie，返回时也改为审核专用名。其他同主机Cookie不传入应用；未替换认证、CSRF、权限、检索或来源判断。没有声称使用了不同浏览器profile。该包装及响应屏障仅存于审核证据 `audit_server.py`；没有部署到用户服务。

历史引用：执行者7项映射测试、22项旧页面状态回归、原四问/构建/保护证据。22项不是新增专题状态测试。本轮没有重跑全仓、模型质量评测、前端构建或旧包验收。

本轮亲测：7项交付测试＋3项新增边界测试，共**9通过、1失败**（失败保留，未修改断言、未循环重跑）。另运行新库导入、真实HTTP/SQL内容核对、重复导入/撤销检查、四问浏览器及受控迟到响应验证。脚本与浏览器检查不累加成pytest覆盖数。

## 3. 验收检查

### 检索白名单与真实BGE：通过本轮技术检查

`live-results.json`保存实际索引内容，不只文件名：逐chunk核对text、text_hash、ordinal、locator_json、heading_path与两份白名单正文通过现有parser/chunker生成的结果完全一致。5份文档/5版本中，只有两份Markdown生成2个索引、118条向量，SQL `vector_dims`均为1024。冻结manifest版本和index ID恰好匹配这两份正文。未发现测试剧本、未来观察、控制JSON、预期答案或旧冷却资料进入实际索引。

四问实际HTTP检索有非空结果，trace为本地BGE1024；模型没有替换为E5或静态结果。本轮不评价BGE相对E5召回质量。

重复导入退出0，5/5/2/118数量不变。随后只在审核库撤销正文：旧会话检索409，新建专题会话409；再导入退出1，明确拒绝automatic reapproval。审核历史保持撤销后的原状，版本/索引/向量数量未增加。见 `repeat-revoke-results.json`、`reimport-revoked.log`。未另外制造全部worker失败类型；pending/失败/拒绝不宣告ready的分支结合代码检查，不冒充逐态现场故障测试。

### 来源映射：部分通过，有必须整改项

多级标题/下一节隔离、多页S03-P8/P9、混合FACT/DEMO标签反例通过。正常映射显式返回direct_chunk或section_reference，页面说明“同节引用不代表整个片段依据”，混合片段亦明确PDF不证明DS模拟值。

真实HTTP逐命中核对正文/版本/chunk，返回PDF的SHA256与对应注册版本一致，PNG SHA256与封存页图一致；不是任意文件路径静态暴露。浏览器亲测：

- 泄漏问题：打开S02物理第6页，完整页图正常显示（1061×1500）；
- G31：相关命中分别列S02第1/4页，FACT对象来源与DS模拟标记并列；
- V465：选中实际写有S03-P8/P9的命中，分别列页并打开第9页；
- 模拟压力阈值：选中“±150为作者虚构阈值”正文，显示DS-02及模拟规格链接，无厂家PDF按钮。

上述成功不抵消标题/简介的实际错误，见DKVB-001。

### 服务端权限与资料资格：本轮检查通过

未登录topic/PDF/image均401；未知case/chunk、非法source/page和路径片段404；同owner其他范围case检索409；错误CSRF403，伪owner参数422。跨owner ASGI检查返回404（用可信认证依赖注入其他actor，**不是第二真实用户登录**）。实际服务仍复用owner、manifest/index、epoch和当前来源资格检查。

三份原PDF为synthetic=false、source/license unknown、pending，实际needs_ocr、无向量；仅授权查原文，不因专题导入变为正式资料。PDF页图不是公开目录；来源ID、物理页范围和hash由服务端固定检查。

### 页面状态：本轮所测路径通过

四问均经实际页面触发，非探针函数冒充浏览器。使用响应屏障：服务端已完成真实search并得到200，屏障记录后取消专题、重新选中（A→空→A）、新建会话，再释放旧成功响应。页面仍0命中、0页图，未恢复旧来源；等待/释放时间记录确认未触发90秒兜底。见 `barrier-stale1-*.json`、`dkvb-audit-stale.txt`。

刷新后不恢复旧命中/原页，本轮审核包装下重新显示登录入口；未声称会话刷新恢复。代码中search/open/newCase成功、错误及finally均核对请求代次；切换清理hits/loc/page/case。未另外强制制造每个错误响应分支；这部分为代码检查，不能把旧22项测试算作新专题覆盖。

## 4. 必须整改

### DKVB-001 / P2：标题前简介错误继承全文来源及模拟规格

位置：`backend/app/dkvb_preview.py:53`（references），尤其59—65行的初始区间与循环；影响73—75行的context/DS提取。

最小反例：`# 总标题\n这只是简介。\n## 一 FACT\n来源S02-P6\n## 二 DEMO\nDS-02模拟150\n`，传入正文“这只是简介。”及其实际char_start。

预期：简介只使用自身有界上下文；没有引用应返回无PDF映射，不应继承后文DS。

实际：返回S02/6、DS-02，`mapping_scope=containing_section`，section_context为全文。新增测试 `test_preamble_does_not_inherit_whole_document`失败。首个二级至六级标题尚未到达时，start/end仍为0/全文长度。

真实交付数据也复现：标题chunk `43b0a088-dca2-4132-a981-f63af5cbda33` 正文仅总标题，却返回**11个PDF页引用及DS-01/DS-02**。完整正文和响应见 `live-results.json.intro_counterexample`。这不是纯人工构造的不可达分支。

影响：标题/简介常见检索命中会把其他节的来源和模拟规格展示为其“同节引用”，错误扩大证据关系。“不代表支持全部内容”的通用提示不足以纠正根本不存在的同节关系，违反本次原页定位承诺。

最小整改：为首节前内容建立真实有界preamble区间（截止首个相关标题），或无所属节时只解析该chunk直接引用；不得退回全文。保留直接/同节关系标签、多页与混合DS警告，不能通过禁用全部来源解决。

定点复核：保留本次失败；加入实际标题chunk、简介、简介直接引用、正常多级标题/多页/混合片段正例。用同一包确认标题不再显示11页/无关DS，正常四问来源不退化。无需重跑历史全仓或模型评测。

## 5. 非阻断建议与未验证范围

- 契约仍写“实施中”，与result的IMPLEMENTED_NOT_ACCEPTED不一致，可在后续文档整理时明确；本轮不改。
- `references`注释写level-2，实际匹配2—6级，应在修复时准确描述上下文层级语义。
- 前端专题生命周期目前主要由本轮实际屏障与代码检查证明；后续可把此接线检查纳入自动化，不将旧22项当作新覆盖。
- 原PDFneeds_ocr、复杂版面理解、OCR、任意大文件、真实维修资料建设、真实车辆适配、AI诊断/观察/报告均不在通过范围。真实资料NOT_MET及原截止未满足状态保留；E10沿用原限定结论、Linux BGE未验证及历史SSE/Compose/启动根因未确认不改变。

## 6. 命令、失败记录与原始证据

所有项目命令cwd为 `E:\Work\xiutu-v5`；以下证据均在 `docs/implementation/product-preview/evidence/dkvb-topic-review-r1/`，不覆盖执行者记录。

| 操作 | 实际命令/入口 | 退出/结果 | 证据 |
|---|---|---|---|
| 定点pytest | `.venv\Scripts\python.exe -B -m pytest tests/unit/test_dkvb_topic.py docs/implementation/product-preview/evidence/dkvb-topic-review-r1/test_audit_boundaries.py`（JUnit本轮目录） | 1；9 pass/1 fail | targeted.log/xml |
| 独立环境 | `runner.py init`及迁移 | 首次fixture Origin不支持，修正审核环境后迁移0 | setup.log、migration-corrected-command.json/log |
| API/worker | `runner.py start` | 旧dead PID混入审核自身活性断言失败；新API/worker实际已启动，后续真实健康/HTTP成功 | api/worker两轮log、runner.py.first |
| 导入 | `runner.py import` | 修正环境后0 | import-corrected-env.log及import-* |
| 实际索引/权限/四问 | `python -B .../audit_live.py` | 0；检查通过，同时明确记录已确认映射缺陷 | live-results.log/json |
| 重复导入 | `runner.py import` | 0；数量不变 | reimport.log |
| 撤销检查 | `python -B .../audit_revoke.py` | 首次UTF8读为GBK失败，尚未执行业务；仅修正审核脚本编码后0 | revoke-check.log、revoke-check-encoding-corrected.log、audit_revoke.first.py |
| 撤销后重导入 | 上述审核脚本子进程runner.py import | 1，预期安全拒绝 | reimport-revoked.log、repeat-revoke-results.json |
| 浏览器屏障 | `runner.py gate stale1 /api/v2/topic/search` / `release stale1` | 0/0；实际等待后释放，无旧内容 | barrier-stale1-*.json、dkvb-audit-stale.txt |
| 停止 | `runner.py stop` | 0，仅本轮进程停止 | stopped.json |

浏览器截图/DOM：dkvb-audit-page.png及q1/q2/q3/q4、stale、refresh文本。取证时一次V465按旧排序选择了另一命中，随后按实际可见正文选择P8/P9；不是检索失败，未重跑查询冒充修复。临时访问文件读取权限问题通过审核临时目录中转解决，中转已删除，未把令牌写入报告/截图。

## 7. 接受建议与停止

建议仅整改DKVB-001并定点复核后再决定接受。其余已测白名单、真实BGE、幂等导入、权限及正常四问证据可复用，不扩大为OCR或正式资料平台整改。

本轮只新增本报告和审核证据，未修实现、未记录接受。审核实例已停止，用户5196与5180继续运行。
