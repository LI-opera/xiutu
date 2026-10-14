# WP-12 A411 区域收尾定点整改（2026-09-20）

状态：**IMPLEMENTED_NOT_ACCEPTED**。本文是执行者自测记录，不是审核或用户接受。只处理区域终态、保守卡与下一待生成区域的衔接；WP-13、正式前端及真实维修推断均未启动。

## 收尾条件与事务

原实现只有人工 `conclude` 能出卡，回答一步后的下一轮任务无法自动结束旧区域。现实现采用两个明确的额外结束信号：已校验的下一检查属于另一合格区域；或者在已保存观察后，WP-10 校验通过的 `conclude_area(assessment=unknown)`。`need_input`、一次观察、步骤暂时消失和模型声称“正常”都不触发完成。服务端忽略模型 finding 的结论语义，重新读取本区全部步骤与当前有效观察，核对 checked、有效 evidence/比较、同组冲突、冻结资料、活动任务、owner/epoch。不能收尾时整个发布回滚，保留待补错误与旧区域 active；不写“正常/排除/确诊”。

符合条件时，在原 worker 物理 advisory-lock 连接、owner/case/job/run 锁和有效租约内，将本区 `unknown` 卡、`area.completed` 事件、区域状态及新检查/area_close publication 同事务写入。新的 `0011_area_closure` 仅增加 graph_progress 的 completed 相位。发布 SQL 后仍检查数据库时钟、原 lease 截止快照与 turn 截止；失败整体回滚。area_close 提交后的 checkpoint 还取得 case 行锁并核对当前 graph_epoch，阻止随后事实更正使旧 worker 写回旧 epoch。显式 area_close 后，按创建顺序选择已有 pending 区域，用受信 area_activation 创建下一 run；无待生成区域则停在 needs_review，不造假检查。未实现受信 retired 合并/重复接口，任何 retired 行均不能凭自由文本理由跳过待测。

原 `POST .../areas/{id}/conclude` 仍是兼容的保守读取/记录入口，不单靠它把区域标记 completed。资料撤销、事实更正仍按旧 epoch/有效性门禁使历史结果需要复核。`unknown` 卡不等于报告就绪。

## 改动范围

- 新增 `backend/app/services/area_lifecycle.py`：同一事务的区域收尾判定与卡片、事件写入。
- 修改 `backend/app/services/publish_service.py`、`backend/app/infrastructure/job_store.py`：跨区域检查发布和明确 area_close 发布、错误归类、原 fencing 收尾。
- `reconcile_pending` 遇到已由事实更正推进的旧 graph_epoch 时只跳过该旧 publication；同 epoch 的结构不一致仍报错，避免历史旧记录阻断无关 worker。
- 修改 `backend/app/agents/runner.py`、`graph.py`、`checkpoint.py`：允许受限 `conclude_area` 意图，成功结束无假步骤，已提交后的 checkpoint 仍有 fencing。
- 新增 `migrations/versions/0011_area_closure.py`，更新 ORM/health 期望版本；旧 0001—0010 未改。
- 新增 `tests/integration/test_wp12_area_closure.py`，补充本契约。

## 免费验证与失败记录

隔离库 `xiutu_test_wp12_area_*`，合成资料、真实 PostgreSQL/API/worker，不启用付费模型。原完整入口 **472 通过/1 失败** 与旧 BGE 定点修正仍是此前版本证据，未改写或并入本轮统计。本轮证据在 `evidence/wp-12-remediation-r1/`，每次新日志独立保留。

| 运行 | 结果 | 证据 |
| --- | --- | --- |
| 新测试首轮 | 3 个夹具缺失错误；补 fixture import | `targeted.txt` |
| 新测试第二轮 | 3 个合成句子同段、完整段落门禁失败；改为独立段落，不放宽校验 | `targeted-r2.txt` |
| 新测试第三轮 | 3 通过 | `targeted-r3.txt` |
| 图终态首轮 | checkpoint schema 尚未初始化，1 失败；在本轮隔离库运行既有 setup 脚本 | `area-end.txt` |
| 图终态复验 | 1 通过 | `area-end-r2.txt` |
| 观察/图/区域受影响回归 | 22 通过 | `affected.txt`, `affected.xml` |
| 扩展区域阻断首轮 | 5 通过、1 失败：测试将退休区设成目标，先触发原 `AREA_NOT_ACTIVE`；改用无关退休区 | `targeted-final.txt` |
| 退休区定点复验 | 1 通过，未审计 retired 不可跳过 | `retired-r2.txt` |
| checkpoint epoch 加固前的标准完整入口 | **退出码 0；479 通过、1 条既有依赖弃用警告，38:43** | `full-standard.txt`，独立库名见 `full-db-name.txt` |
| 完整入口后追加的同组冲突反例 | **退出码 0；1 通过**。只新增测试，业务代码未变；真实 PostgreSQL 中同规格/工况的合格与超限观察阻断完成 | `conflict.txt`、`conflict.xml` |
| area_close 后 epoch 更正边界 | **退出码 0；1 通过**。发现并封住新终态对 checkpoint 的过宽许可 | `epoch-checkpoint.txt`、`epoch-checkpoint.xml` |
| epoch 加固后的受影响回归（复用夹具库） | **退出码 1；25 失败**，旧测试留下的过期 waiting publication 使新 worker 在全局对账中抛 `CHECKPOINT_INCONSISTENT`；该日志保留，不作为最终通过证据 | `affected-final.txt`、`affected-final.xml` |
| 受影响回归（全新库，定位旧 epoch 对账前） | **退出码 1；23 通过、2 失败**。新增 epoch 故障夹具保留了旧 waiting publication，暴露上述跨测试/跨任务阻断；不是区域收尾断言失败 | `affected-fresh.txt`、`affected-fresh.xml`、隔离 worker 日志 |
| 最小旧 epoch 对账修正后受影响回归（再次全新库） | **退出码 0；25 通过**，涵盖旧观察/图恢复及新增区域终态、冲突、epoch 故障边界 | `affected-final-clean.txt`、`affected-final-clean.xml` |
| 最终业务代码标准完整入口 | **退出码 0；481 通过、1 条既有 Starlette/anyio 弃用警告，38:27**。包含旧 epoch 对账修正与新增反例后的最终业务源码 | `full-standard-final.txt`、`final-r2-source-hashes.json`、`full-final-db-name.txt`、`index-final-before.txt`/`index-final-after.txt` |

`targeted-r4` 等命令均为 `.venv/Scripts/python.exe -B -m pytest -p no:cacheprovider tests/integration/test_wp12_area_closure.py -q --tb=short --basetemp <全新目录>`；受影响回归添加 `tests/integration/test_wp12_turns.py tests/integration/test_wp11_graph.py`。冲突和 epoch 反例各仅运行其单项节点 ID。完整入口命令为 `./scripts/test.ps1`，设置 `TEST_DATABASE_URL`/`DATABASE_URL` 指向独立 `xiutu_test_wp12_full_*`，先 `alembic upgrade head` 和 `scripts/setup_graph_checkpoint.py`。第一次完整入口的源码 SHA-256、迁移及 Git index 基准见 `final-source-hashes.json`、`index-before.txt`/`index-after.txt`；**479 项是 checkpoint epoch 加固和旧 epoch 对账修正前的版本，不充当最终业务源码的全量结果。** 最终版本的源码哈希见 `final-r2-source-hashes.json`，完整入口后逐文件 SHA-256 无差异。Git index 运行前后均为 `C451D6E78B8F29FC818002923A19FB1A888139CED20679AD545F75E9692A9EC6`；没有提交或推送。

## 保留边界

当前仅 `unknown` 保守自动卡；没有自动确认/排除、可信 retired 合并流程、WP-13 报告或正式网页。跨区域切换仍依赖有来源且经 WP-10 原门禁接受的下一检查，未给出合法下一项时维持待补；不使用固定树强推。测试夹具直接准备 pending 区域与候选以验证事务衔接，**不代表真实 DeepSeek 自主选区**。DKVB 精确适配、真实模型发布和真实资料门槛 NOT_MET 均保留。旧 worker 首次失败根因未确证；5180/5196 未操作，费用账本未读取，未付费。等待一次集中审核，不自行接受或进入 WP-13。
