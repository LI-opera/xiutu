# WP-05 索引与混合检索 API

当前以运行服务`/openapi.json`为准。Cookie、Origin、CSRF与既有本地单操作员认证一致；reindex另要求Idempotency-Key。owner由认证确定，跨owner读写404。没有WP06 evidence快照接口。

- `POST /api/v2/documents/{id}/versions/{vid}/review`：符合服务器profile资格的approved返回202，并含index_run_id；不合格则200记录审核，index_exclusion说明当前owner资料的限制。重复key重放原响应。
- `POST /api/v2/documents/{id}/versions/{vid}/reindex`：`{"config_version":"e5-small-onnx-v1"}`；202 `{index_id,run_id,status:"building"}`。同版本已有building返回409 INDEX_BUILDING。无资格409 INDEX_NOT_ELIGIBLE。通用run retry不用于index，新构建使用此入口。
- `GET /api/v2/documents/{id}/versions/{vid}`：新增active_index_id、index_run_id、index_status、index_exclusion；index_implemented=true。building不取消旧active；只有正式资格且可用active时formal_usable=true（候选资格，非维修保证）。
- `POST /api/v2/evidence/search`：`{"query":"P0301 点火异常","vehicle_scope":{"model":"待核实车型","year":2020,"engine_family":"系列","engine_code":"具体代码"},"top_k":5}`。top_k=1—10。没有profile、owner或客户端允许版本清单参数。

成功200返回chunks/excluded/trace。chunk含chunk_id、document_version_id、index_id、text、locator、applicability（matched/unknown与reasons/general_reference_only）、channels/scores、synthetic/formal_usable。scope明确冲突mismatch先排除；unknown仅通用参考。定位使用原GET版本content/chunks接口，保留版本不可变原文。

无合格资料200空；合格资料未有ready索引503 INDEX_UNAVAILABLE；实际本地模型不可用503 EMBEDDING_UNAVAILABLE，不能作为无匹配或偷偷降级。推理期间资格或active变化409 SEARCH_SNAPSHOT_CHANGED。空集合trace的reason说明无合格候选。excluded仅当前owner的版本。trace包含索引对应的返回结果、query SHA256、候选渠道/分数、配置和耗时；不写私人query原文到服务日志。请求者需要留存检索追踪时应保存响应；本包未建永久查询日志平台。

默认formal排除synthetic、未审核、撤销、needs_ocr、来源/许可未核实；许可private_use只用于本地owner，并非公开分发许可。仅服务器synthetic测试profile可检索合成资料，启动须APP_MODE=test且数据库通过xiutu_test_*隔离门禁。禁止生产请求通过参数切换。正式资料不足时返回空是正确行为。

算法为TF-IDF与精确cosine各30，RRF60融合前20，再确定性适配/完整故障码优先，top_k并受8000上下文token上限。不是cross-encoder，不生成任何替代维修知识。现有active_index在新building故障时不变，撤销审核即不进入新搜索快照。

版本响应同时提供last_index_status/index_error及最近index_run_id；无旧active且最近构建失败时index_status=failed。有旧active则仍ready，同时显示最近失败，不掩盖构建错误。
