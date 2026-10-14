# WP-04 资料上传、解析、审核与版本契约

仅本地UTF-8 Markdown与未加密文本PDF，逐页标记扫描/缺文本。无OCR、embedding、检索、Agent或业务页面；测试语料synthetic，不证明真实维修效果。

## 所有权与版本

POST /api/v2/documents：multipart恰好file和metadata(JSON)两部分；metadata内document_id=null建立新逻辑文档，非空向本人文档加版本。document.owner_id来自认证；version/chunk继承document，ingest run.owner_id相同且绑定version。旧无owner资料不可访问。跨owner文档、版本、chunk/原文/审核和run统一404。

metadata：title、source_kind、source_reference、source_status(unknown/verified)、license_status(unknown/private_use/permitted)、scope{model,year_from,year_to,engine_family,engine_code}、synthetic。首次title/source_kind为逻辑资料标题/种类，各版本保留完整metadata快照。同一document内sha唯一；同hash同规范化metadata返回原version/当前任务状态，不重入队、不改审核/chunk；同hash不同metadata返回409 METADATA_CONFLICT，不静默改历史。新文档同内容不跨文档或owner去重。同key同请求重放原状态/响应，异请求409。

## 上传与存储一致性

配置UPLOAD_MAX_BYTES默认25MiB。流式multipart解析前和回调中分别限制总接收量(max+64KiB)、file实际字节(max)、metadata16KiB、header8KiB、2个part，不只信Content-Length，不先整体spool到磁盘。文件扩展名/UTF-8或PDF签名与结构交叉校验，浏览器MIME只作不可信提示。文件名含路径/控制字符拒绝；服务端UUID.bin作为唯一storage_key。

存储目录及祖先拒绝symlink/junction/reparse，拒绝旧项目和路径越界；open exclusive不覆盖，flush/fsync后再事务写版本/run/job/event。原文不可变、SHA256校验。失败/并发重复只移除本次UUID文件且先确认数据库无引用；提交结果不明确或清理查询失败时保留候选孤儿，不能冒险删已提交引用。硬中断可能留下孤儿，按证据中的UUID与引用清单人工只读核对后另行清理；本包不实现全局清理平台、不声称文件与数据库跨介质原子事务。

## 解析和状态

parse_status=pending/parsing/review_pending/needs_ocr/failed/cancelled。review_status沿用pending/approved/rejected/revoked，成功解析仅pending，不自动批准。无文本或明显图片缺项页令parse_status=needs_ocr，page_issues记录页码和原因；混合文档只保存能读页的chunk，但显式partial，不当完整资料。PDF复杂版式顺序不保证，无OCR。

Markdown保留标题路径、段落、列表、表格及字符/行定位；保留原始纯文本，不执行HTML/脚本/URL/外部图。长表按行/极长行分段并复制表头；上下文前置段落通过context locator引用，不因跨块丢掉步骤前置关系。超长段落采用明确文本边界分割不丢字符。

切块默认目标600/上限900/重叠80 BPE token，配置CHUNK_TARGET_TOKENS/CHUNK_MAX_TOKENS/CHUNK_OVERLAP_TOKENS；使用本地固定cl100k_base词表和明确版本，不等同DeepSeek实际计费token。词表随项目封存、运行时不下载。保存parser_version、chunker_version、tokenizer、token_count与locator。

解析/切块在业务事务外，持续检查stop，心跳独立。版本与ingest job一一关联当前run；所有chunk、解析摘要和任务成功/对应事件在JobStore有效lease/token且非cancel_requested的同一finish事务写入。失败、queued取消、running取消、死亡后尝试耗尽均同步version状态，不能run终止而version仍parsing。显式retry继承预算，版本转pending/绑定新run；旧token不发布。重复完成不重复chunk。

## API与审核

写接口沿用cookie/Origin/CSRF/Idempotency-Key。POST上传新版本202 {document_id,version_id,run_id,reused:false}，同hash复用200（同key仍重放原响应）。GET /documents按created_at/id降序签名cursor分页、limit1..50；GET /documents/{id}/versions/{vid}提供metadata、parse/review/index状态、页缺项、run_id与审核历史。GET /.../chunks以ordinal cursor分页(limit1..100)，返回内容/hash/token_count/heading/page/char/行locator和上下文locator。

POST /.../review JSON {decision:approved|rejected|revoked,scope,source_status,license_status,review_note}，extra=forbid。记录actor/time/note/source/scope快照、追加document_reviews历史；同key不重复历史。待解析/失败/取消不能批准；needs_ocr不能批准，拒绝/撤销可记录。synthetic、unknown来源/许可即使人工approved仍不可正式使用；批准是人审记录，不自动认证来源。批准返回200并显示index_pending，index_implemented=false；其它状态index_not_implemented。全包formal_usable=false，无索引任务/ready/搜索API。

GET /.../content验证关系/owner与SHA，Markdown为text/plain+nosniff，不渲染HTML；PDF以attachment返回原文件+页数响应头，page参数校验范围，仅帮助定位、不改原文件。chunks只供解析审核浏览，不是检索资格。

0004增owner、版本元数据/解析记录/当前run FK、chunk locator/token信息及审核历史表/约束/索引；不改0001—0003，不建active_index_id。错误沿用安全envelope；413超限、415格式/编码、422输入、404权限、409元数据/审核状态冲突，异常不回显原资料/凭据。

## 验证与边界

D207—D209：真实PG、新库/存储目录、合成MD/PDF、真实worker/HTTP/SSE；覆盖并发去重/事务回滚、版本保留、取消/失租约/中断恢复、无半套chunk、审核门禁。完整入口一次，后续仅定向修复回归。E10 NOT_VERIFIED最迟WP-09，资料NOT_MET最迟WP-10/真实效果验收前。完成只IMPLEMENTED_NOT_ACCEPTED。

## 实现边界补记

PDF最多1000页及1000万抽取字符，超限明确失败；包含图像的页面保守列缺项，不把图中内容当已抽取。巨大表头（超过目标的一半）不能整段重复而同时保持900上限，采用源chunk完整保留+table_header文本/定位引用；普通表头逐块复制。长段落与行保留所有源字符，正文重叠约80真实token，表格重叠采用表头。

存储路径检查以仅运行用户可写的本地目录为前提；不声称抵御本机特权用户的并发路径替换。降级0004会删除新增字段/审核历史表，cancelled映射failed以符合旧约束；仅在本轮新建测试库演练，不对既有资料库降级。

资料approved之后显示index_pending表示等待WP-05实现，不代表已经建排队索引任务。所有formal_usable仍false；source/license审核声明由actor负责，软件不自动核实许可。

## ISSUE-001 发布有效性与回滚边界

finish保持同一专用物理连接、advisory锁及job/run行锁。首次校验后，获取version发布行锁可能等待，因此锁取得后再次验证worker/token、物理连接、run状态和有效租约。全部chunks、version摘要、job/run终态及事件SQL执行完毕后，事务COMMIT之前进行最终校验：用数据库clock_timestamp()对比首次校验锁定的lease_until快照，同时核对当前worker/token与pg_backend_pid。终态清空lease_until不影响该快照；事务锁持有期间其他worker和心跳不能改变它。所有finish分支均适用此最终门禁。

最终校验是发布授权判定点，之后没有额外应用SQL，仅提交；不把事务开始时间当当前时间，也不声称COMMIT网络往返/WAL确认一定发生在租约截止前。该判定点至提交仍持有行锁与专用advisory锁，不能被其他执行者接管。校验失败抛出LeaseLost，整个事务回滚，chunk、版本成功状态、终态和成功事件均不可见；worker退出失效尝试并释放自身连接，随后合法worker按原预算恢复。实际COMMIT通信故障仍可能存在提交结果不明确，不扩大为生产恢复保证。
