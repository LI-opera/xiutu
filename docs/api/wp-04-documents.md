# WP-04 资料接口

所有业务请求要求当前同源cookie；POST还要求Origin、CSRF、Idempotency-Key。跨owner和错误document/version关系统一404；所有响应no-store。错误使用既有error.code/message/retryable/trace_id，422不回显输入。完整字段与schema见运行中的/openapi.json及[实施契约](../implementation/phase-02/wp-04-contract.md)。

| 接口 | 请求/响应 |
| --- | --- |
| POST /api/v2/documents | multipart恰好file、metadata JSON；metadata.document_id省略/空为新文档，指定本人文档为新版本。202新建；同文档同hash同metadata 200复用；同key重放原202/200；异请求同key409；同hash异metadata409。响应document_id/version_id/run_id/reused |
| GET /api/v2/documents | limit=1..50（默认20）、签名cursor；按created_at/id倒序，items和next_cursor，含latest_version_id；游标不跨owner或case接口复用 |
| GET /api/v2/documents/{id}/versions/{vid} | immutable metadata、hash、mime、parse/review状态、run、parser/chunker/tokenizer、逐页缺项、人审历史及明确未实现索引/正式资格 |
| GET /.../{vid}/chunks | limit=1..100（默认50）、cursor为上次ordinal（初始-1）；items和next_cursor，每块text/hash/token_count/heading/page/char/locator_json。每次仍验证owner和版本关系；ordinal不是跨资料授权凭据 |
| GET /.../{vid}/content | 原始MD text/plain+nosniff+CSP sandbox；PDF attachment原文件，解析后附X-Source-Page-Count；page>=1且不超过已解析页数，仅定位提示 |
| POST /.../{vid}/review | JSON decision=approved/rejected/revoked、scope、source_status、license_status、review_note；200并追加actor/time记录。解析未完成或needs_ocr不能approved；同key不重复历史。synthetic/来源许可unknown即使approved仍formal_usable=false |

上传限制：默认25MiB文件实际字节、总multipart额外64KiB、metadata16KiB、part headers8KiB和两part。超限413，格式/编码/加密415，字段/filename/结构422。streaming parser逐片写入，不使用会先完整spool的request.form/File入口；Content-Length不作为唯一判断。文件名称不参与路径，使用服务端UUID；路径/重解析绕过拒绝。

parse pending → parsing → review_pending/needs_ocr；终止失败failed、取消cancelled；显式重试继承WP-03剩余预算并转pending。审核状态与解析状态分别记录，解析不会把rejected改为approved。approved仅index_pending，index_implemented=false，所有formal_usable=false；无index任务和搜索接口。

PDF页定位来自逐页抽取；含图页保守记录image_content_not_extracted，无文本页no_text，整份状态needs_ocr，可看到已抽取文本但不能当完整资料。Markdown字符位置针对UTF-8解码（去BOM）后的原文，行号从1开始；PDF字符位置针对该页抽取文本。普通长表重复表头；超过半个目标预算的巨大表头保留完整来源chunks并用table_header定位上下文，避免为重复表头突破900上限。长行/段落按Unicode字符边界分割，依据真实BPE计数；完整原文可读取，不截断。

未实现：OCR、embedding、active_index_id、检索、正式资料页面、Agent/诊断。E10与真实资料门槛未收口。
