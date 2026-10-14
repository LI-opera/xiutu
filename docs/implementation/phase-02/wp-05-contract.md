# WP-05 索引与检索契约

仅后台索引和检索，非诊断；不创建 case_evidence。0005_indexes 接续 0004_documents，不改旧迁移。

## 模型
本地 intfloat/multilingual-e5-small，revision 614241f622f53c4eeff9890bdc4f31cfecc418b3，MIT；官方 FP32 ONNX、CPUExecutionProvider、384维。embed_documents/passages 与 embed_query 分别加 passage:/query: 前缀；attention mask mean pooling、L2。长文本按模型token窗口分割，逐窗向量按内容token数加权再L2，不静默截断；配置指纹 e5-small-onnx-v1。固定权重/tokenizer SHA256 验证后才能加载，无自动联网、远程代码或付费调用。数量、维度、有限性、非零范数严格检查。缺模型/推理失败为 EMBEDDING_UNAVAILABLE，非空候选不能降级成 baseline。

## 数据与任务
index_versions 固定模型配置、384维、chunk快照数量、profile、run和状态；chunk_embeddings 主键(index_id,chunk_id)，向量列vector(384)。其他维度需新配置与迁移，不允许混入。document_versions.active_index_id 保留旧可用索引。
审核保存当前 review_snapshot（历史记录仍追加）。approved且当前profile资格合格时同事务创建building索引及index run/job/event；其他情形只记录审核，给出阻断原因。既有approved版本用 POST /api/v2/documents/{id}/versions/{vid}/reindex，JSON {config_version:"e5-small-onnx-v1"}，Idempotency-Key必需，202 index_id/run_id。一个version同时最多一个building；并发不同key返回409 INDEX_BUILDING，同key原响应。显式reindex是新构建请求；通用run retry不用于index任务，原任务历史保留，自动尝试仍最多三次，仅明确瞬态错误可自动重试。

推理在事务外，独立心跳；每批写入在原物理租约连接短事务内，验证job/token/租约、run未取消及index归属，最终数据库clock_timestamp校验后提交。批次只是building隔离数据，不可检索。恢复尝试先在受保护事务内清理该building的旧批次，再重建。失败/取消/尝试耗尽标failed，旧active不动。取消后残留staging向量仅用于审计，未来清理。
最终发布按job/run→version→index锁顺序；取得版本锁后再验证，检查当前审核资格、run对应、配置、chunk集合/数量/维度，然后同事务ready+active切换+run/job成功+事件。沿用WP04所有SQL后的最终租约快照校验；失效整体回滚，原连接/advisory/行锁持续到commit。不存在“墙钟在COMMIT完成前永远不跨期”的网络保证，最终授权点是最后数据库时钟校验。新旧索引不覆盖，无并行building使旧任务越过较新构建。

## 资格与接口
默认formal profile：approved、解析无缺页、非synthetic、审核来源verified、许可private_use/permitted。private_use只限本地owner，不是公开分发授权。合成profile仅服务器RETRIEVAL_PROFILE=synthetic + APP_MODE=test + 通过共享test数据库门禁；只接受synthetic，不能通过请求参数切换。所有权来自认证，不接受允许版本清单覆盖。
GET version新增active_index_id/index_run_id，index_implemented=true；仅正式资格且active ready时formal_usable=true（仅资料候选资格，不是维修效果认证）。needs_ocr仍不能approved。审批不自动等于索引完成；building期间旧active继续可查，revoked/rejected立即不参与下一次搜索快照。

POST /api/v2/evidence/search，JSON {query,vehicle_scope:{model,year,engine_family,engine_code},top_k:1..10}，同源cookie/Origin/CSRF，额外字段禁止。无case快照。返回chunks（chunk_id、document_version_id、index_id、locator、适配状态/reasons、渠道/分数、必要文本）、excluded（仅当前owner）、trace。缺审核/来源/许可/scope冲突先过滤；无合格资料200空，合格资料尚无ready索引503 INDEX_UNAVAILABLE；有候选embedding不可用503，不伪装成功或baseline。基线仅评测CLI显式调用。

model/year/engine_family/engine_code逐项独立；明确冲突mismatch排除；缺少任何精确适配字段unknown，只通用参考；全匹配也仅“提交信息匹配”，不是车型认证。检索读取已授权ready索引快照，模型推理不持事务，结果返回前重新检查资格/active，变化返回409 SEARCH_SNAPSHOT_CHANGED供显式重试。

TF-IDF版本tfidf-cjk-v1：完整DTC、拉丁词、中文单字/双字片段；词频1+log(tf)，IDF log((N+1)/(df+1))+1、cosine。精确DTC优先召回，sparse/dense各30；pgvector精确cosine（不建ANN）；RRF k=60融合前20，确定性matched/精确DTC/RRF排序取top_k。非cross-encoder。trace保留渠道候选及分数、不记录query日志中的私人原文。

## 验证与边界
冻结合成调试集/留出集/相关性标签/配置及SHA256后评测，Recall@5宏平均、Hit@5、MRR@10、失败查询及延迟；初始Recall@5>=0.85目标保留。程序作者制定的合成标签不是人工维修真值。真实资料门槛NOT_MET，最迟WP10/真实效果验收前；E10 NOT_VERIFIED最迟WP09，本地embedding不替代DeepSeek。SSE首次超时根因未确认和既有待办保留。WP06未启动。

版本响应同时提供last_index_status/index_error及最近index_run_id；无旧active且最近构建失败时index_status=failed。有旧active则仍ready，同时显示最近失败，不掩盖构建错误。
