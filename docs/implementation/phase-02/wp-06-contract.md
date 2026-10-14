# WP-06 证据快照与测量规格契约

范围仅为证据和规格基础；无诊断图、报告生成或前端。0006_evidence_specs接0005，旧迁移不改。

## 事务与范围
新case的corpus_manifest由服务器按owner、profile、当前资格及适配冻结version/index/authorization_epoch；mismatch排除，unknown仅通用证据。旧空manifest保持空，不能绑定。新文档和active重建不更新manifest；会话检索只用固定ready索引，不替换active。通用WP05搜索不变。
同owner的资料审核、case创建、证据/规格写入、比较及引用门禁先取稳定SHA256生成的PG事务advisory锁，再按文档/版本、case/证据/规格顺序访问；审核和使用序列化，不等待模型/worker。索引worker不取此owner锁，只使用既有版本行锁/租约协议；冻结时按UUID排序锁版本。新上传在枚举后到达不纳入该次快照。活跃索引切换以版本行锁串行化，冻结保留旧ready索引。
资料审核的decision/scope/source/license实质变化递增authorization_epoch；对已绑定的证据、规格、比较标needs_review，case置needs_review（不递增诊断revision）。标记不可被重新批准清除；旧manifest epoch不匹配即阻断新使用；本包无刷新manifest接口。新会话/新规格版本才能重新建立依据。批量标记与审核同事务，不依赖异步通知。

## API
所有路径前缀/api/v2，owner只来自认证；跨owner路径资源404；绑定输入不在冻结manifest统一409，不区分他人或不存在资料，避免泄露存在性。POST均Origin/CSRF，持久写入另需Idempotency-Key；同key同规范化请求原响应，异请求409。重放保留历史响应，不能视为当前有效性；每次使用重新校验。
- POST /cases/{case_id}/evidence：chunk_id、document_version_id、index_id、start/end（Python Unicode码点、半开区间）、quote。须与真实chunk切片完全相同；重复文本用offset区别。201生成evidence_id，冻结quote SHA256、chunk hash、locator及offset、适配、资料审核快照/epoch、时间；客户端不可指定hash/locator/owner。
- GET /evidence/{evidence_id}：snapshot与current_validity分开；历史撤销后仍可读，source_content_url走已有授权原文API；chunk UUID不是evidence UUID。
- POST /cases/{case_id}/evidence/search：query、top_k1..10，车辆和manifest由case注入，不允许请求覆盖。沿用真实E5/混合检索；冻结范围失效409，不偷偷扩范围。
- POST /measurement-specs：evidence_id、component_key、quantity、unit、lower/upper（可单边，至少一个）、lower_inclusive/upper_inclusive、conditions（必需非空精确字符串键值）、可选supersedes_id。同源同case规格形成不可变spec_root_id/version；不提供修改正文API。首次pending；单边无界侧inclusive必须false；双边相等只允许闭区间，禁止倒置。
- GET /measurement-specs/{id}：不可变正文、当前审核与历史、有效性。
- POST /measurement-specs/{id}/review：decision approved/rejected/revoked、note。记actor/time/历史；批准必须证据有效且适配matched。对已needs_review规格拒绝重新批准；创建新版本重新审核。撤销/拒绝标记其历史比较需复核。
- POST /measurement-specs/{id}/compare：value（可null）、quantity、unit、conditions。201保存不可变比较记录及spec版本/证据快照，GET /measurement-comparisons/{id}读取历史与当前有效性。返回outcome、原输入、换算值、规格上下界、provenance、synthetic；不是部件正常/维修结论。

## 十进制和结果
数值仅接受有界长度的十进制字符串（含科学计数），拒绝JSON float/int/bool、NaN/Inf；<=30有效数字，指数绝对值<=30。数据库NUMERIC不设精度缩放，JSON数值用字符串，Decimal局部精度100；边界比较使用精确有理数比对转换公式，避免°F/°C循环小数四舍五入误判；展示converted为Decimal字符串并带exact标记。单位白名单temperature:C/F，pressure:Pa/kPa/bar，voltage:V/mV，resistance:ohm/kohm；不支持任意表达式。
顺序：值/quantity/unit有效性→当前规格/证据有效性→车辆matched→工况键值齐全匹配→换算边界。结果within_range/out_of_range/conditions_missing/conditions_mismatch/unit_mismatch/quantity_mismatch/value_missing/spec_not_approved/evidence_invalid/scope_unknown/scope_mismatch，均非自动诊断。非法单位/数量词或非法十进制422；合法但物理量不匹配返回未判定。缺工况不填0。

## 引用门禁
可调用服务validate_references(case, evidence_ids, spec_ids)在同一owner锁/事务重查归属、manifest、quote/hash/locator、当前epoch/资格和适配；调用者必须提供待使用的重要规格spec_ids；这些规格需approved及matched，不以普通文本代替。服务不推断自然语言声明包含哪些重要规格，语义识别留后续。返回allowed/reasons，synthetic只能技术演示，formal发布一律阻断。无证据拒绝。只提供未来报告调用服务和测试；report_gate.available仍false，未实现正式报告发布。quote存在不等于语义支持，LLM支持关系验证未实现。

E10 NOT_VERIFIED最迟WP09；真实资料NOT_MET最迟WP10/真实效果验收前。SSE首次根因未确认；性能/规模/清理/监控待办保留。本包全部示例为隔离合成数值，不是维修规格。
