# WP-12 实施结果（2026-09-20）

状态：**IMPLEMENTED_NOT_ACCEPTED**，等待一次集中审核及用户决定。观察提交、数据库事实、更正、区域保守卡和下一轮恢复已在隔离合成资料下落地；不表示审核或用户接受。

## 可用范围

- 已发布当前检查可经认证/CSRF/幂等/revision/epoch 保护的 API 提交 choice、measurement、composite 或带原因的 unavailable。有效 choice 必须是原检查选项；确认“已检查”状态时须提交实际工况，不能用资料前置句代替操作者确认。测量复用已批准规格与 Decimal 比较门禁。观察、步骤完成、revision、下轮 run/job、事件、幂等 202 在同一 PostgreSQL 事务提交。
- 公开旧 `/diagnosis/resume` 不再允许任意观察 UUID 推进。可信内部图仍从有效、已保存观察读取；新的 run 继续使用 WP-11 的租约、原连接 advisory lock、checkpoint 和事务发布。
- 更正追加 supersedes 行与原因，旧观察不可变，graph_epoch+1，旧步骤/区域结论标为需复核；活跃 run 时拒绝。区域浏览只读，激活待生成区域需服务端 area 引用且不得覆盖另一个待答检查。显式 `conclude` 接口持久保存该区域的保守卡，仅返回 `unknown/conflicting/needs_input`，带本区域观察与来源 ID；资料撤销标记卡需复核。当前没有自动区域收尾或 retired 合并操作。

## 改动

新增 `0010_observation_turns` 迁移、ORM 区域结论/观察更正字段、`observation_service.py`、`correction_service.py`、`area_service.py`、WP-12 集成测试、[API](../../api/wp-12-observations.md)和[免费运行说明](../../runbooks/diagnosis-observations.md)。更新 cases API、服务装配、图读取/发布与 job 终态、资料撤销联动、README/CHANGELOG。没有修改 0001—0009、用户实例或 Git index。测试入口原有两个同名 WP-11 测试模块导致收集失败；integration 文件仅改名，内容 SHA-256 不变，原失败保留。

## 验证与边界

全部使用隔离库 `xiutu_test_wp12_*`、合成资料、独立 worker，无付费请求。标准命令为 `./scripts/test.ps1`（设置 `TEST_DATABASE_URL`）与 `python -B scripts/demo_wp12.py`；准确结果如下，**不把重复用例的数量相加为新覆盖数，也不把最后一次完整入口写成通过**。

| 运行与源码版本 | 退出码/结果 | 原始证据 |
| --- | --- | --- |
| 前期 WP-12/WP-11 图定点 | 16 通过；较早版本 | `evidence/wp-12/wp12-targeted-a7c47c20*/pytest.txt` |
| 首次标准入口 | 1；同名模块收集错误，0 项执行 | `evidence/wp-12/full-82ff6076*/standard-test.txt` |
| 改名后标准入口 | 1；470 通过、3 失败、1 警告 | `evidence/wp-12/full-91089a2c*/standard-test.txt` |
| 受影响定点 | 10 通过、授权到期反例 1 失败；双时钟校验后该单项 1 通过 | `evidence/wp-12/repair-4ddd79bb*/pytest.txt`、`repair-1a1b41b4*/pytest.txt` |
| 最终生产实现的标准入口 | **1；472 通过、1 失败、1 警告，36:24**；WP-12 新增八项通过。唯一失败为旧 BGE `[lease]` 测试在暂存前先耗尽短租约 | `evidence/wp-12/final-full-9f3c01d2*/standard-test.txt`、`source-hashes.json`、`index-sha256.txt` |
| BGE 租约测试同步修正后的单项 | 0；1 通过；先观察 1024 维向量暂存，再由数据库时钟缩短租约，过期旧 worker 不激活 | `evidence/wp-12/repair-46da6507*/pytest.txt` |
| 最终免费演示 | 0；3 通过、5 未选；观察、更正、保守卡及两组保存选择 | `evidence/wp-12/final-demo-07adb73a*/demo.txt` |

完整入口的三项首轮失败分别为迁移测试表清单、取消后 case 状态及 MCP 凭据到期反例的时钟口径。前两项已定点修正；MCP 服务使用进程时钟，反例在持锁期间等待进程与 PostgreSQL 两者越过有效期后通过，生产授权逻辑未改。最后一次完整入口的 BGE 租约反例有 `before_finish` 屏障却无 `after_index_batch`，0 暂存向量；原测试把模型加载/编码时间也计入 6 秒租约。仅测试夹具改为先见真实暂存向量再让数据库租约过期，保留旧索引与 fencing 断言；生产租约和索引代码未改。最后一次完整入口之后仅改测试同步、演示选择和运行说明，**最终字节版本未重跑完整入口**，待审核据原失败与定点修正评估。

单项复验命令是 `.venv/Scripts/python.exe -B -m pytest -p no:cacheprovider 'tests/integration/test_wp09_models.py::test_e5_to_bge_atomic_generations[lease]' -q --tb=short --basetemp <新隔离目录>`；MCP 到期反例同样以其完整节点 ID 定点运行。均以 `DATABASE_URL=TEST_DATABASE_URL` 指向本轮隔离库，输出重定向到上表的新目录。最终文件清单与 SHA-256 见 `evidence/wp-12/delivery-hashes-sealed.json`（28 个明确路径，排除 `.env`、账本及私有临时目录）；先前 `delivery-hashes.json` 和 `delivery-hashes-final.json` 为文档收尾前的快照，保留但不作为最终清单。Git index SHA-256 始终为 `C451D6E78B8F29FC818002923A19FB1A888139CED20679AD545F75E9692A9EC6`。

同一故障/同一合成资料下的两个已保存选择，由确定性测试夹具选择不同且有来源的下一检查；这是持久分支机制证明，**不是** DeepSeek 自主判断或真实维修效果。用户可在独立 `xiutu_test_*` 库中令 `DATABASE_URL=TEST_DATABASE_URL`，禁用项目私有 `.env` 和付费开关，从项目根目录运行 `python -B scripts/demo_wp12.py`；人工 API 步骤见[运行说明](../../runbooks/diagnosis-observations.md)。当前只有保守区域卡，没有自动区域收尾、可信规则授权的自动排除/确认、完整报告发布或 WP-12 正式前端。DKVB 精确适配、真实模型发布与真实资料门槛 **NOT_MET** 及原截止要求仍未解决；无法测量与冲突不构成完成。旧 worker 首次失败、Linux BGE、历史 SSE/Compose 未确认根因仍保留。不操作用户 5180/5196，不进入 WP-13。
