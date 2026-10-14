# 资料与提案预览切片：集中检查 r1

- 日期：2026-09-19（Asia/Shanghai）；结束保护核对 10:32:55。
- 结论：**CHANGES_REQUIRED**。建议仅整改下列两个页面一致性/定位问题后定点复核，不重开 WP-00—10，不扩展大书导入或诊断功能。
- 角色披露：本任务曾参与本切片实施；本次切换审核角色，未修改实现。这不是不同任务独立审核，也不是用户接受。
- 证据目录：`evidence/review-r1/`。只有该目录及本报告为本轮新增交付；审核临时库/存储保留，审核进程已停止。

## 1. 基准、隔离及保护

读取适用指令（项目及上级未发现 AGENTS.md）、STATUS、contract/result/runbook/issues、交付/封存/测试/浏览器证据，审查 frontend/src/main.tsx、api.ts、新预览应用、启动脚本与相关上传路径。未重新审核已接受工作包。

`baseline.json`：交付清单 **3100 项匹配**、seal 无差异；main 无 HEAD。`issues.md` 是交付后按用户授权新增的协调记录，单列解释，未当成篡改，也未修改。结束 `protection-final.json` 核对开始时保护的 **3103 文件及3个 dist 文件均无变化**；原虚构源 SHA256 仍为 `e4896ccde323186e8c2c01ca5187b3edfa25977b5a74cb6be45f1a682dedd888`。Git index 始终为 `c451d6e78b8f29fc818002923a19fb1a888139ced20679ad545f75e9692a9ec6`。历史报告、接受记录、迁移、STATUS、问题清单和封存未改；旧项目无写入。旧63项保护沿用交付证据，不宣称本轮重新审核旧项目。

确认运行中的 xiutu-v5 PostgreSQL 归属和 127.0.0.1:5433（docker.json）。初次普通权限检查受权限限制，正常提权后读取成功，未判为引擎故障。新建独立 `xiutu_test_preview_21a0f8be9b5e`，独立 storage、凭据及 API/worker。审核端口7075；没有停止、清空或重启用户5180，结束时其公开 health=200。没有读取私人 .env、真实费用账本或未提供路径的维修书。

操作注意：最初审核浏览器使用127.0.0.1:7075，同一浏览器的同名cookie不按端口隔离，可能使5180浏览器会话需重新登录。随后仅把审核实例改为localhost:7075隔离cookie。未读取/改写用户5180运行目录或服务端会话/数据；此项操作影响明确保留（origin-isolation.txt），不宣称完全无浏览器会话影响。

## 2. 本轮执行与历史证据区分

所有 shell 验证 cwd=`E:\Work\xiutu-v5`，使用现有 .venv，`-B`禁止新增源码缓存；脚本和输出均在本轮目录。完整命令、起止时间见 commands.json。

| 本轮动作 | 结果/证据 |
|---|---|
| `python -B scripts/probes/prepare_database.py --name xiutu_test_preview_21a0f8be9b5e` | exit 0，新库 |
| `python -B -m alembic upgrade head`（仅审核库） | exit 0 |
| `python -B -m pytest tests/product_preview/test_api.py -q --tb=short --basetemp <审核private>/pytest --junitxml <本轮>/api-tests.xml` | **18 passed，0失败/错误/跳过，1条既有Starlette弃用警告**；10:16:40—10:16:45，exit 0 |
| `python -B <本轮>/snapshot.py markdown-ready`及`pdf-ready-after-limit` | exit 0，真实版本状态/原文件哈希 |
| CUA浏览器：登录、导入、解析、人审、索引、检索、候选校验、原文、PDF、超限、刷新/切换 | browser-checks.json及截图，真实HTTP/worker/E5，无付费LLM |
| `python -B <本轮>/http_targeted.py` | exit 0，413/计数/存储保护、旧manifest、新版本，http-targeted.json |
| `python -B <本轮>/late_poll.py` | exit 0，独立库表锁35秒后回滚；实际PG Lock/relation最多2个等待请求 |
| `python -B <本轮>/audit_instance.py stop` | exit 0，仅结束匹配创建时间的审核PID；库/存储保留 |
| `python -B <本轮>/finalize.py` | exit 0，结束保护通过、5180 health200 |

18项本轮测试覆盖薄接口认证、CSRF、跨owner、模型字段/可信上下文拒绝、无规则及不发布等；不把历史18项与本轮18项相加为覆盖数。前端typecheck/build、原句式限制/缺规格四候选浏览器路径引用哈希未变的执行者证据；本轮另亲测有据区域成功及错误路径。未重跑全仓、第二环境或模型质量评测。

审查新应用服务端从认证上下文及所属case构造ProposalContext，未开放规则注入；accepted仅candidate，published=false。UI持续显示虚构演示、人工测试候选/非AI生成，未伪造诊断发布。LOCATION_UNCERTAIN等与字段映射限制的分类保留；无法定位的缺项没有虚构引用。

## 3. 正常PDF：本轮实际通过

新建明确合成、非真实维修资料的 `synthetic-text.pdf`，2437字节、2页（每页可提取文本），SHA256=`a7d091bbb94843208894d9b269092a41e447332c7bea22e800bb09340fa51f68`。

浏览器上传→真实worker解析→pending人审→显式合成演示审核→真实E5索引ready→输入 `AUDIT-PDF-COOLING-2026 fictional water pump`→返回第1/2页片段→点击第1片段显示PDF原文链接及page=1 locator。HTTP原文件字节/哈希与fixture一致，formal_usable=false。刷新后仍读取已完成/已审核/ready和同一版本，非假进度。见 pdf-fixtures.json、pdf-ready-after-limit.json、browser-checks.json、pdf-source.png。

PDF页经Poppler渲染并目视检查（pdf-page-1/2.png）。准备阶段首次大PDF填充产生无效startxref，错误保留，未用于正常PDF通过结论；之后生成并用pypdf验证有效的两页超限PDF。本机无fitz，改用已有Poppler，未安装依赖；字体warning未影响该ASCII合成PDF可读性。本轮未验证扫描件，不宣称OCR或复杂版式理解。

## 4. 必须整改

### PREVIEW-003（P2）：上传新资料后保留旧候选通过状态

- 位置：`frontend/src/main.tsx:75-76`（upload），及`120-121`（validate）。
- 复现：资料A完成检索/绑定，有据区域候选accepted=true；随后上传合成PDF B。界面/URL已切到B、case清空，B尚待人审，但旧A命中、JSON、原文与绿色“候选校验通过”仍在。再点击校验，出现“请先创建预览会话并绑定证据”，同时旧绿色通过仍显示。
- 证据：browser-checks.json中的valid_markdown_candidate、after_pdf_upload_state、old_success_without_current_case记录；valid-before-upload.png、stale-candidate.png。实际字段名以原JSON为准，未改写原记录。
- 根因：upload仅更新doc/vid/version/cid，未同步清理结果及其依赖上下文。与choose的清理路径不一致。旧审核勾选等同源残留合并本项，不重复开问题。
- 影响：当前资料与校验依据/成功结果脱节，违反契约“旧文档结果不混入新选择”。本轮未发现后端将旧候选错误发布或绕过owner；仍属必须整改的状态混淆。
- 最小要求：资料/版本/会话变化时集中失效所有依赖结果、选择/候选/审核确认及来源状态；结果明确绑定其上下文代次，过期结果不得呈现为当前通过。无需修改WP10判定。
- 定点复核：A通过→上传B、切版本/新会话后旧成功消失；失败上传则保留A真实状态；迟到异步返回不恢复A的成功。

### PREVIEW-004（P2）：冻结旧版本命中无法打开原文

- 位置：`frontend/src/main.tsx:84-85`（inspectHit）。
- 复现：A版本1审核/索引并创建冻结会话，随后同逻辑文档上传不同内容版本2（本轮HTTP新建，未改旧版本）；刷新旧会话URL，检索仍正确返回版本1。点击其中位置表片段，来源区仍“从资料、命中片段或拒绝原因打开原文”，没有该命中的原文或locator。
- 证据：http-targeted.json新版本ID `ae46d264-5c36-45d8-85d2-7d230b614746`；browser-checks.json的old_version_hit_source_missing；old-version-source-missing.png。旧版本 `098fe118-7f2a-4fd3-9aba-626515a927c6` 的后端原文已由markdown-ready.json验证，未被删除。
- 根因：只在docs列表用latest_version_id匹配命中version；合法历史version不再是latest，查找失败后静默结束。
- 影响：冻结会话保持旧依据这一正确行为，反而使“命中→原文定位”断链。不是要求新资料自动加入旧会话，也不是数据丢失。
- 最小要求：按命中的真实document/version关系解析授权原文，不依赖latest列表；解析失败明确提示并避免留下别的来源。维持后端owner/version关系校验。
- 定点复核：v1冻结→v2上传/索引后，v1命中仍打开v1原文/hash/locator，不能换成v2；新会话可按其真实manifest读取新依据。

## 5. PREVIEW-001/002核查与非阻断建议

**PREVIEW-001**：当前有效上限26214400字节（25MiB）。构造有效文本PDF 26214401字节，浏览器无size预检、仍可提交；实际返回 **413 UPLOAD_TOO_LARGE / Upload rejected**，不可重试。失败后原PDF仍ready，documents/versions/runs/chunks数量分别2/2/4/91均不变，存储文件集合不变，没有错误上传成功。界面默认上限提示存在，但未显示所选大小、未说明超出多少且错误中英文混杂。建议最小前端预检和中文错误说明，服务端实际接收字节限制继续保留；当前限定小型合成体验下列为非阻断改进。没有读取用户书，不能从文件名确认220MB、页数或扫描属性；不要求本轮支持整本大PDF，不调整门禁。

**PREVIEW-002**：确认upload把所有文件写成synthetic_preview/synthetic=true及服务端固定合成车型范围；不是真实文件自动识别。当前契约本来只承诺合成演示，formal_usable=false和固定模式未被浏览器参数放宽，本轮上传的PDF确为合成。因此本限定范围不据此否决整个切片。但现有“上传本地资料”的入口名称容易使用户误以为可接入真实手册；建议明确“仅上传虚构/合成演示资料”，在选择前解释车辆元数据是演示假设。后续若接入真实书，应另设真实来源待审核入口，保留unknown来源/许可/适配，不自动判synthetic或formal可用；属于新增需求，不在本轮实施平台。

其他非阻断：PDF当前为原文件链接+页码locator，未承诺内嵌逐页高亮；可后续改善阅读体验。不要求界面美化、完整诊断台、观察写入或大文件拆卷。

## 6. 迟到响应、冻结范围和边界

- 真实audit库表锁10:31:03—10:31:38造成轮询SQL等待，10:31:22切换PDF，解锁后显示PDF的正确版本/ready，未被旧MD响应改回；late-poll-lock.json及browser-checks.json对应。代码refresh在版本/任务返回后核对selection。该定点通过不抵消PREVIEW-003的确定性残留，也不等于所有网络调度穷尽证明。
- 新PDF不进入旧MD会话manifest；旧case查询PDF关键词仍只返回旧MD版本（http-targeted.json）。同文档新版本也未覆盖旧冻结版本。
- 读取原文与候选权限由后端服务保持；本轮18项测试未见薄接口越权。没有扩展正式资料资格，未修改WP10核心算法或结论规则。

## 7. 限定建议、未验证与停止点

建议先修PREVIEW-003/004，再对对应上下文/版本定位做一次定点复核；无需重跑历史全仓。正常小文本PDF链路、上传拒绝数据保护、冻结资料和薄接口边界已有本轮证据可复用。PREVIEW-001/002的清晰提示与真实资料新入口方案分别记改进/需求，不混成必须支持220MB或完成正式诊断。

本轮未测扫描PDF、真实手册、OCR、正式模型生成、通用语义/维修效果、生产恢复或完整WP14。真实资料NOT_MET及原截止要求未满足；E10沿用WP09限定结论；Linux BGE及历史启动/SSE/Compose根因未确认继续保留。本轮无付费调用。

没有修改实现、STATUS、issues、接受记录、旧项目、历史证据或Git index；没有提交/推送。用户5180服务保留。等待用户决定整改或接受策略，不进入WP11。
