# WP-02 实施契约

仅数据库、领域、认证与会话创建/读取/列表。WP-00/01已接受；本包等待独立审核。E10 NOT_VERIFIED，资料 NOT_MET，原截止门槛保留。

## API与安全

- POST /api/v2/auth/login：JSON {token:string(32..512)}，Origin必须等于配置APP_ORIGIN；成功200 {actor_id:uuid,csrf_token:string,expires_in:int}，Cookie xiutu_session 随机256位、HttpOnly、SameSite=Strict、Path=/、Max-Age默认3600。HTTPS时Secure，HTTP仅允许localhost/127.0.0.1。会话保存在单进程内存，重启失效；本包单worker，不声称多worker共享认证。
- GET /api/v2/auth/session：需当前Cookie，返回同一会话actor/CSRF/剩余秒数；POST /api/v2/auth/logout需Origin和X-CSRF-Token，200 {logged_out:true}，删除并撤销当前Cookie。认证响应Cache-Control:no-store。
- OPERATOR_TOKEN由受保护本地配置环境注入，至少32字符；OPERATOR_ID为稳定UUID（默认固定本地操作员ID），同一操作员不同登录会话不会改变owner。缺令牌拒绝业务认证、health可用。登录不进入业务幂等缓存，每次成功生成新会话并撤销所携带旧会话；logout重复请求在会话失效后401。登录通过严格Origin与JSON请求防跨站，凭据不放URL。
- POST /api/v2/cases：认证+Origin+X-CSRF-Token+Idempotency-Key(1..128 ASCII字母数字._:-)，无expected_revision，201 CaseSnapshot。GET /cases及GET /cases/{id}需认证；不存在/其他owner统一404。没有PATCH/DELETE/run API。
- CreateCase：vehicle {model:1..100, year:null或1886..2100整数, engine_code:null或1..64, engine_family:null或1..100, vin:null或17位大写VIN字符}; fault_description:1..4000；fault_codes最多30个、每个1..32字母数字/连字符。所有输入extra=forbid、字符串strip；VIN/故障码大写，故障码去重排序。缺省fault_codes=[]，空可选字符串拒绝，year拒绝布尔和字符串。
- CaseSnapshot准确字段：id、vehicle、fault_description、fault_codes、revision、graph_epoch、status、corpus_manifest、created_at、updated_at、active_run、report_gate。创建draft/revision0/graph_epoch0/corpus_manifest=[]；active_run=null；report_gate={available:false,reason:"NOT_IMPLEMENTED"}。不返回owner/token/资料授权。此包无任务执行，已有活跃run仅保留空active_run契约，不声称查询任务状态已实现。
- 列表{items:CaseSnapshot[],next_cursor:string|null}，limit默认20、1..50；created_at DESC,id DESC键集分页。游标版本1，绑定owner并HMAC签名，含时间和UUID；非法/跨owner游标400 INVALID_CURSOR。签名密钥由本地操作员token派生，令牌更换后旧游标失效。
- 错误统一{error:{code,message,retryable,trace_id,details?}}；422 VALIDATION_ERROR（仅字段位置/类型，不回显输入），401 UNAUTHORIZED，503 AUTH_NOT_CONFIGURED/DATABASE_UNAVAILABLE，403 ORIGIN_FORBIDDEN/CSRF_INVALID，404 NOT_FOUND，409 IDEMPOTENCY_CONFLICT/REVISION_CONFLICT。未知内部错误500 INTERNAL_ERROR，不回显SQL/栈/连接串。

## 事务与幂等

共享db_target验证后重建参数创建SQLAlchemy引擎，不转发原DSN；UnitOfWork管理begin/commit/rollback/close。路由无SQL，domain不依赖框架或数据库。

业务幂等按(actor_id,route_scope,key)唯一；有效规范化请求JSON稳定hash。事务内INSERT ON CONFLICT DO NOTHING取得幂等键，冲突语句等待原事务完成后再读取已提交响应；同hash重放201/原响应，异hash409。新key、case、完整响应同一事务提交；异常全部回滚，不在异常失效事务继续查询。保留响应至少7天，本包不删除记录。重放必须重新通过认证/CSRF/Origin。登录凭据响应不缓存。revision冲突只在服务策略入口校验，不新增修改接口。

## 迁移清单与分期

新增0002_core，下接0001_environment。健康预期版本统一于infrastructure/schema_version.py；旧/缺/错误revision均不就绪。0001保持不变。

建立cases、documents、document_versions、chunks、runs、jobs、run_events、idempotency_keys；准确列/默认/CHECK/FK以0002_core内冻结Table定义及交付migration-manifest.json为准。UUID主键，run_events为bigint identity；时间timestamptz；枚举CHECK。FK显式RESTRICT，禁止默认级联删历史。幂等三字段主键；document_id+sha256、version+ordinal、jobs.run_id唯一；runs非空case在queued/running/cancel_requested时部分唯一，waiting_input不占槽。runs含input_payload与parent_run_id。revision/graph_epoch/序号/attempt等非负，max_attempts正数且attempt不超过上限。

active_index_id暂不建，WP-05随index_versions及其FK一并加入。WP-04实现资料导入/审核/解析；WP-05建index_versions/chunk_embeddings；WP-06建case_evidence/measurement_specs；区域/假设/步骤/观察/结论在WP-10/11按正式业务依赖补充；tool_calls与publication_keys在相应工具/发布包落地；reports在报告包落地。本包无这些表及业务接口。

降级仅逆序drop本迁移八表/其索引，不删除vector或外部schema。仅新测试库演练；真实开发库与WP-01保留库不升级。

## 验证与边界

领域单测→新库空库upgrade/0001到0002/降级再升级与health→认证/错误→真实HTTP创建读取列表→独立owner→真实事务并发幂等/活跃run/唯一键/回滚→WP-01 PG/vector/图/MCP回归→前端壳构建。默认testpaths及test.ps1包含unit/integration/contract/probes；OfflineOnly明确排除所有数据库相关用例，仍运行真实本地MCP。无付费模型请求、资料API、worker或业务UI。

## 最终契约补记

OpenAPI通过securitySchemes明确SessionCookie，以及写入时SessionCookie与CSRFToken同时必需；Origin与Idempotency-Key标为required。业务/认证响应统一Cache-Control:no-store。空cursor字符串返回422，非空但无法验证的游标400。认证容量上限1000个未过期会话，超过返回503 AUTH_CAPACITY；不提供账号/多角色系统。owner/actor为外部认证UUID，当前无accounts表，故无伪accounts外键。

八表完整字段、可空性、默认值、CHECK、FK删除行为、唯一键和索引以[evidence/wp-02/migration-manifest-final.json](evidence/wp-02/migration-manifest-final.json)实际数据库内省为交付清单；冻结迁移不导入可变app metadata。未来结构修改需新revision。所有SQL关系FK均RESTRICT。

## r1整改契约补记

- 当前可写持久化自由文本（fault_description、vehicle.model、engine_code、engine_family）复用PersistedText校验，只拒绝实际U+0000，在业务service/事务之前返回422 VALIDATION_ERROR、retryable=false；不删除或替换字符。字面量反斜杠加u0000不视作NUL，中文、合法Unicode及正文换行沿用原长度/strip规则。VIN、fault_codes和Idempotency-Key继续由既有字符白名单约束拒绝NUL；可选发动机字段仍接受null、拒绝空字符串。
- 数据库错误不解析异常文本。明确DomainError业务冲突仍409；SQLSTATE 28类认证失败、3D000数据库不存在，以及无SQLSTATE/无SQL语句的连接阶段OperationalError返回503 DATABASE_UNAVAILABLE、retryable=false；不猜测具体原因，不把503等同可重试。这些保守分支优先于connection_invalidated。其余有依据的连接失效、SQLSTATE 08类/57P01—03返回503 DATABASE_UNAVAILABLE、retryable=true。连接池超时、40001/40P01/55P03/57014返回503 DATABASE_BUSY、retryable=true。
- SQLSTATE 22类返回500 DATABASE_DATA_ERROR、23类返回500 DATABASE_CONSTRAINT_ERROR，均retryable=false且无原始错误/SQL/参数。此边界没有足够业务上下文把所有数据库约束违反归责客户端；不能把所有IntegrityError改成422。用户输入由DTO先返回422；已定义业务冲突由服务显式DomainError表达。其他数据库/程序错误安全返回500 INTERNAL_ERROR、retryable=false。
- 标准test.ps1自行创建.test-runs父目录，拒绝普通文件和项目路径/父目录重解析点；保持UUID子目录、不删历史、不改变缺TEST_DATABASE_URL时完整模式拒绝行为。

整改结果见[wp-02-remediation-r1.md](wp-02-remediation-r1.md)。WP-02保持IMPLEMENTED_NOT_ACCEPTED；r2复核后的ISSUE-003最小修正见[wp-02-remediation-r2.md](wp-02-remediation-r2.md)，等待不同审核窗口仅复核本次差异，不表示已接受。
