# 诊断闭环切片：计量策略变更后的有界真实验证

2026-09-20（Asia/Shanghai）。**切片仍为 BLOCKED。**本轮只创建一个真实初始业务 turn；它在模型发送前以 `HANDLER_FAILED` 失败，DeepSeek 请求 0 次、工具尝试 0 次、publication 0 条。因首轮未发布，不提交观察，也不创建真实续轮；没有第二个付费首轮或通过夹具替代模型结果。

## 基准与免费准备

变更前 `model_budget.py` SHA-256 `035CA75B9864A55EB790669AE53947082CF7EFF12B73BD5BB07E96DBA26067D3`、`model_gateway.py` `78452B6D8F18F62FF82A5266A7A5163EB6E5DDCAADA3A8D246FF575FDA000584`、`runner.py` `278297B4924FA6DDAC12E9511C19318B21417BD7950C10432205F10C10FCF9BC`。本轮最终分别为 `CF95B694F5EA6FFAA9A1125945DAD135F70BCE051F2851537F59052CA5A3C7E5`、`319382D44F31F2D2DBFD3F68C0DE2ED4C0BA4FE849AB628BA334117F9FDD50CB`、`FD51E0DD0339E4396B47E64F08C8AD9D26EF8361A7827E10935A06C75A16FD3E`。`tests/live/test_diagnosis_slice.py` 本轮未修改。Git index 前后均为 `C451D6E78B8F29FC818002923A19FB1A888139CED20679AD545F75E9692A9EC6`。

首次免费 BGE 前置探针在新隔离库中于来源覆盖断言失败（exit 1，私有 `free-preflight.log/xml`）；已保存其原始失败。检查实际冻结索引和检索片段后，只将初始命中的邻域扩展从最多两处改为最多三处，仍走同一授权的 search/context 工具，受原六次调用上限约束，不硬编码候选答案。原隔离 case 的 BGE 1024 维命中及邻域随后覆盖五条合成来源句子；受影响定点 7 passed（exit 0）。这只是免费来源就绪证据，不等于模型会产生合法候选。迁移及 checkpoint 设置只针对全新 `xiutu_test_diag_paid_a37c1b2e` 数据库。首次 Alembic 命令缺少配置位置，exit -1，原日志保留；指定项目 `alembic.ini` 后 exit 0。原 5180/5196 服务、资料和索引未操作。

## 唯一真实首轮

命令：在受限目录 `.test-runs/diag-slice-paid-a37c1b2e/`，强制 `DATABASE_URL=TEST_DATABASE_URL` 指向上述隔离库，设置 `DIAGNOSIS_SLICE_LIVE=1`，运行 `.venv/Scripts/python.exe -m pytest tests/live/test_diagnosis_slice.py::test_one_bounded_synthetic_turn -q -s --basetemp <私有目录> --junitxml <私有目录/live.xml>`，**exit 1**。该入口上传明确 synthetic/formal_usable=false 的合成台架 Markdown，经真实解析、E5→本地 BGE-M3 索引切换、冻结 manifest、原 WP-10 合法候选免费预检，并启动本轮独立的只读 MCP 服务。新 case 的真实初始诊断 run 创建后，worker 返回 `HANDLER_FAILED`；`live-summary.json` 及数据库核对均为 `status=failed`、`publication_count=0`、`model_requests=0`、`tool_attempts=0`。受限候选诊断 trace 为 0 事件，说明失败发生在候选诊断路径之前；通用 handler 捕获未保留具体异常类型，**根因尚未确证**。不把它描述成模型候选被 WP-10 拒绝。

原共享账本本轮首轮前后聚合保守预留均为 **¥2.329216**、调用数均为 **18**，新增预留与 usage 均为 0/不适用；没有发生 DeepSeek 网络请求。平台账单未核实，不能从预留推断账单金额。观察、child run、续轮、第二步、刷新后第二步读取和两步浏览器闭环均 **NOT_RUN**，不称为已完成。MCP 进程由测试 `finally` 终止；本轮只留下隔离库及受限本地证据供定位。用户实例 5180/5196 未操作。

原始私有 `bootstrap.private.json`、`runtime.private.json`、MCP 配置与有限 trace 位于上述受限目录，只供操作者后续定位/清理，不进入公开证据；公开仅保存 [脱敏汇总](evidence/diagnosis-slice-metered/summary.json)。没有输出或封存密钥、原始候选、资料正文、工具参数、完整账本。此失败之后依授权停止真实验证，未反复创建 turn。后续应先用免费隔离复现定位 `HANDLER_FAILED` 的前模型异常，再决定是否另行授权新的真实尝试；本报告不构成审核或接受。合成样本不代表 DKVB 实车资料，真实资料 `NOT_MET`，WP-13—17 仍 `NOT_STARTED`。
