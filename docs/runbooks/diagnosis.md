# WP-11 隔离诊断图运行说明

历史运行说明：该诊断执行链的公共写入口现已退役，以下步骤只记录当时的隔离验证方法，不是当前模板工作台的启动或验收流程。旧图与候选诊断测试分别保留为 `tests/integration/legacy_wp11_graph.py`、`tests/integration/legacy_wp11_candidate_diagnostics_integration.py`，须显式指定文件；默认测试入口不收集这两份。`scripts/demo_wp11.py` 同样只指向历史测试。

本包只提供单步持久图、发布、等待及按**数据库已保存观察**恢复的基础。没有WP-12观察提交界面或最终报告；当前技术资料不能用于真实车辆维修。

1. 使用全新且明确归属的`xiutu_test_*` PostgreSQL库和隔离`DATA_PATH`。不得将这些命令指向5180、5196或现有业务库。设置`DATABASE_URL`和`TEST_DATABASE_URL`为同一隔离目标，并按项目原数据库目标门禁配置。不要在日志中打印连接串。
2. 在项目根运行`uv run --frozen python -B -m alembic upgrade head`，确认revision为`0009_graph`；然后运行`uv run --frozen python -B scripts/setup_graph_checkpoint.py`，显式初始化独立`wp01_wp11` LangGraph checkpoint schema。脚本不需要读私有`.env`，不在HTTP请求中自动初始化。已有业务库若计划迁移，应另行安排备份和审核，本包没有操作它们。
3. 启动独立API与worker。`POST /api/v2/cases/{id}/diagnosis/runs`需owner登录Cookie、Origin、CSRF、Idempotency-Key和当前revision；通过原run查询/SSE观察状态，`GET /api/v2/cases/{id}/diagnosis`读取当前检查。worker退出后可用另一个独立worker继续领取到期任务；已发布的步骤与等待状态由数据库publication/progress恢复。
4. 测试恢复时，先在**隔离库**中准备与当前步骤关联、revision有效的保存观察，再调用`POST /api/v2/cases/{id}/diagnosis/resume`提交其UUID与当前revision。没有WP-12公开观察写入API；不能向resume提交观察正文。

默认不发付费模型请求。真实DeepSeek仅在明确设置本包付费开关、有效私有模型配置、原共享5元费用账本和最新核价均成立时可用；预算失败不得清账本或自动改用本地假模型。API和worker都仅在`XIUTU_LOAD_PROJECT_ENV=1`时显式读取项目`.env`，进程环境变量优先；隔离测试不设置此开关，也不复制私有`.env`。业务MCP模式需独立只读MCP服务与受保护凭据，`remote_mcp`失败不回退`local`。确定性测试夹具直接入库的候选和观察仅证明事务/恢复，不是AI生成的维修建议。

诊断模型输出上限由服务端`DIAGNOSIS_MAX_OUTPUT_TOKENS`控制，默认1536、允许768—1536；病例请求和模型工具参数均不能修改。原WP-09普通网关默认768。该上限同时进入SDK请求和原共享账本的保守预留；截断仍失败，usage缺失不释放预留。真实探针只有在run=`waiting_input`、恰一条publication、有效当前检查及授权引用、独立读取进程看到同一步且模型调用数未增加时才返回成功退出码；测试框架本身结束不等于诊断发布成功。

跨进程checkpoint写入需要原worker物理锁连接、有效token和数据库时钟租约。成功发布后，若进程在最终checkpoint前退出，原publication仍是业务事实；后续reconciler推进`graph_progress`至等待。当前诊断显式retry拒绝，自动重试仅针对已列明瞬态错误且最多总3次；无资料、校验待补、预算耗尽等以失败状态和错误码保留，不产生虚假步骤。恢复或重新授权待补的正式用户交互尚未实现。

测试入口：在上述独立库完成迁移与checkpoint setup后，运行`./scripts/test.ps1`。单步免费演示见`python -B scripts/demo_wp11.py`；它启动受限测试fixture，明确标注非真实模型。审查原始证据和限制见[WP-11结果](../implementation/phase-04/wp-11-result.md)。
