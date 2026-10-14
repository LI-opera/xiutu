# WP-12 隔离观察事务演示

仅用于 `xiutu_test_*` PostgreSQL 和自行准备的 synthetic 资料。先按 [WP-11 运行说明](diagnosis.md)完成当前 `0011_area_closure` 迁移与 graph checkpoint 初始化；保留已有用户 5180/5196 实例不变。确保 `DATABASE_URL` 与 `TEST_DATABASE_URL` 都指向同一个隔离库，`APP_MODE=test`，`RETRIEVAL_PROFILE=synthetic`，不启用付费诊断开关。

免费 CLI：从项目根目录执行 `python -B scripts/demo_wp12.py`。脚本通过 TestClient 请求观察 API、由真实 PostgreSQL 保存下一 run/job，使用明确标记的确定性合成候选和 WP-11 图读回当前步骤，演示无法测量后的更正，以及两种已保存选择对应的不同后续检查。输出自动放到新的 `.test-runs/wp12-demo-*`。这不是一套人工维修步骤，也不证明 DeepSeek 对 DKVB 已发布检查。

手动 API：登录后创建有冻结 synthetic 范围的 case，启动 `/diagnosis/runs` 并等待 `/diagnosis` 返回 `current_step`；以该响应的 revision、graph_epoch、step ID 及当前 input schema 调用 [WP-12 API](../api/wp-12-observations.md)。返回的下一 run ID 可用既有 run 查询/SSE 跟踪；运行完成后重新读取 `/diagnosis`，不要把旧答复应用到新 revision。选择带已检查含义的选项时需要由操作者确认实际工况，无法测量记录原因。修正历史时先取消并等待活跃 run 终止，再以当前 revision 和原 observation ID 提交更正。区域 GET 是只读浏览，区域卡仅报告 unknown/conflicting/needs_input。

区域自动收尾只生成 `unknown` 保守卡：已校验的跨区下一检查或 `conclude_area(assessment=unknown)` 明确结束意图之外，不将回答、`need_input`、不可测量或冲突当作完成。先看区域列表中的 completed/card，再看当前步骤或 run 的待补错误；无 pending 区域会停在 needs_review，不造下一检查。不上传私人资料，不调用付费模型。实际车况、正式观察前端、自动确诊/排除、受信 retired 合并和 WP-13 报告不在此演示范围。
