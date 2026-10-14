# WP-06 API：证据快照与规格比较

仅技术基础，非诊断/报告。所有URL前缀 `/api/v2`。运行时 `/openapi.json` 描述请求模型、安全要求及输出envelope；完整语义见[契约](../implementation/phase-02/wp-06-contract.md)。所有读取按owner，越权路径404；绑定输入不在冻结manifest统一409，不区分他人/不存在的源资料；POST要Cookie、Origin、X-CSRF-Token，持久写入另要Idempotency-Key。

| 方法/路径 | 请求 | 响应 |
|---|---|---|
| POST /cases | 现有vehicle、fault_description、fault_codes | 201，corpus_manifest由服务器冻结；客户端不能提供 |
| POST /cases/{id}/evidence/search | query、top_k | 固定case车辆/manifest搜索，chunk_id不是evidence_id |
| POST /cases/{id}/evidence | chunk_id、document_version_id、index_id、start、end、quote | 新建201/同位置复用200，evidence_id、snapshot、current_validity、source_content_url、synthetic |
| GET /evidence/{id} | 无 | 历史快照与当前有效性分列 |
| POST /measurement-specs | evidence_id、component_key、quantity、unit、lower/upper、包含标记、conditions，可选supersedes_id | 201 pending，不可变正文及spec_root_id/version |
| GET /measurement-specs/{id} | 无 | spec、source、review_history |
| POST /measurement-specs/{id}/review | decision、note | 200及审核历史；批准需来源有效、适配matched |
| POST /measurement-specs/{id}/compare | value、quantity、unit、conditions | 201，不可变comparison及result |
| GET /measurement-comparisons/{id} | 无 | comparison、current_validity；旧within_range不代表当前有效 |

`start/end`是原chunk中Unicode码点的半开区间；quote保持空白，必须严格等于切片。定位和SHA由服务端生成，不允许客户端传hash/locator。重复文本使用不同offset区分。空manifest拒绝绑定；重建后会话仍使用旧ready index。撤销/范围变化会使epoch失效，重新批准也不恢复旧manifest和已标复核的依据。

合成规格示例（仅隔离test profile，不是实际车辆标准）：

```json
{"evidence_id":"替换为真实返回ID","component_key":"SYNTHETIC-COMPONENT","quantity":"voltage","unit":"V","lower":"1","upper":"2","lower_inclusive":true,"upper_inclusive":true,"conditions":{"engine":"off"}}
```

比较示例：`{"value":"1000","quantity":"voltage","unit":"mV","conditions":{"engine":"off"}}`。所有数值以十进制字符串传入，不用JSON number。未知单位/非法数值422；物理量不一致、工况缺失等返回明确未判定outcome。缺值null不当0。温度C/F含偏移，转换展示若为循环小数标converted_exact=false，但边界判定为精确比值，不依赖四舍五入展示。

来源无效/待审/撤销/unknown绝不within_range。合成通过仍synthetic=true、diagnosis=false。`EvidenceService.validate_references`可为未来工具调用，默认formal=true拒绝合成和未知适配、失效引用/规格。没有报告API，case.report_gate.available继续false；未做LLM支持关系检查。

错误：VALIDATION_ERROR/CITATION_INVALID(422)，NOT_FOUND(404)，CORPUS_NOT_ALLOWED/SOURCE_INVALID/INDEX_INVALID/SCOPE_MISMATCH/SCOPE_UNKNOWN/SPEC_SUPERSEDED/SPEC_LINEAGE_INVALID/IDEMPOTENCY_CONFLICT(409)；连接异常沿现有安全分类，不返回SQL或输入秘密。幂等重放是旧结果，不解除当前撤销标记；新使用必做当前有效性校验。
