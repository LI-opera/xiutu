# WP-11 持久诊断图实施契约

范围：合成/已授权资料下，现有case→持久run/job→可信上下文与模型/工具→WP10提案校验→单事务发布一步→waiting_input→按数据库已存observation引用恢复。只读DKVB资料可作演示；真实资料NOT_MET。WP12的用户观察写入与多区域交互、报告及正式前端不在此包。

## 实际衔接和文件

已有cases(revision,graph_epoch,corpus_manifest)、runs(workflow_id,turn_id,input/output_revision,budget_json)、jobs(lease_token/owner/until)、run_events、observations、JobStore的专用advisory锁与心跳。现有ProposalService只验证候选，ProposalRunner有界一次修复，ModelGateway付费请求共用原5元账本，ToolExecutor及MCP有既有能力。此前无areas/steps/publication_keys或诊断worker。

新增0009_graph迁移及ORM：diagnosis_areas、diagnosis_steps、diagnosis_publications、diagnosis_candidates和graph_progress。既有0001—0008不改。graph_progress只存workflow、case、epoch、turn、阶段、当前step引用和候选引用，不存可覆盖业务事实的第二份观察/步骤。LangGraph PostgresSaver checkpoint表在独立wp01_wp11 schema由专用`setup_graph_checkpoint.py`初始化，不由HTTP请求setup；部署时先升级0009，再执行一次显式setup。

新增agents/graph.py和runner.py、services/publish_service.py、api/cases.py启动入口；修改worker.py与job_store.py仅使diagnosis结果在原advisory/lease/fencing事务内发布。CaseService.get附当前step/wait状态。API `POST /api/v2/cases/{id}/diagnosis/runs` 请求`expected_revision`，认证+Origin+CSRF+Idempotency-Key；202返回run_id，重放同响应、异请求409。GET原case及runs/SSE返回实际状态；无前端假按钮。CLI在隔离库演示。

## 节点与事务

图节点顺序为load_snapshot、validate_context、load_skill、load_saved_observation、update_hypotheses、plan_questions、agent_decide/execute_tools、assess_evidence、propose、validate、publish、wait/interrupt。节点仅返回增量；业务事实每次从DB读取。`workflow_id`由首个持久run生成、后续turn继承，绑定该case及epoch；每个turn有独立checkpoint thread(`workflow_id:turn_id`)，旧turn的checkpoint不能覆盖新turn。`turn_id`固定一次交互；自动尝试沿用持久工具预算及模型账本，不凭模型参数创建身份、权限、规则。首轮只发布一个当前步骤/区域。资料不足或不支持的提案停止并标明错误，尚无正式用户待补交互。

发布在持有原锁连接的事务内进行：锁case/job/run，验证owner、epoch、cancel、token、有效租约、原连接PID、授权资料；先按(workflow,turn,node)查publication key/hash，同内容重放且fencing仍有效则返原结果，不因revision已推进而拒绝；异内容冲突。未发布的新内容才检查input_revision。步骤/区域、case revision与等待状态、run.output_revision、事件、publication key同事务提交。获取阻塞锁后及所有SQL后用clock_timestamp、原lease截止快照复验；失败整笔回滚。worker失锁不保存checkpoint。

wait仅interrupt，不写业务事实。发布成功但checkpoint未落盘时，publication与graph_progress恢复记录为权威，重启reconciler将已提交发布推进至waiting_input；后续turn从数据库已保存observation及原publication启动自己的checkpoint，不重放旧模型输出。等待时job完成、run waiting_input，释放锁和槽。恢复只接受数据库已有observation ID及新run ID，核验case/step/revision/epoch和有效性；错误引用拒绝。WP12正式观察API未到期，测试可在隔离库事务直接准备观察。

## 预算和验证顺序

每turn最多工具6/检索3/模型4（包含429/5xx提供方重试）/结构修复1，初始120秒；模型上限仅由可信runner传入，恢复沿用同一turn既有请求记录，WP-09普通网关默认5次不变。检索和证据绑定耗时也计入，发布事务在所有SQL后按数据库实际时钟再次核对turn期限与租约，过期整体回滚。持久tool_executions与模型费用账本记录已耗用，worker重启不重置。自动尝试最多3次；当前诊断显式retry为fail-closed，已失败run不会凭新key清零预算。模型请求仍通过ModelGateway旧共享费用账本，预算/费用不足或MCP断连明确失败且不本地回退。正式的人机待补与失败后的重新授权流程留后续，不将失败标为成功或自动开启新turn。

WP-11 最终结构化步骤比 WP-09 小型探针需要更长的 JSON 输出。服务端 `DIAGNOSIS_MAX_OUTPUT_TOKENS` 默认及上限为 1536（允许 768—1536）；普通病例/API/模型工具参数不能设置它。既有 WP-09 网关默认仍为 768。网关把同一 `max_tokens` 同时交给 SDK 和原共享费用账本预留；`length` 截断仍直接失败，不拼接残缺 JSON，也不免除预算、120 秒或一次修复限制。

先迁移/接口/发布与恢复定点，后独立库双进程PG/worker、锁等待/取消/崩溃/预算验证，最后标准完整入口一次。确定性fixture与真实DeepSeek轨迹分列；真实调用必须在免费验证后且保守预算足够。未验证不得称通过。5180/5196完全不操作。完成前状态不写ACCEPTED。
