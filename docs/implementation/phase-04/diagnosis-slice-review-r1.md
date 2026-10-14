# WP-13 前诊断闭环切片：限定范围集中审核 r1

审核时间：2026-09-21（Asia/Shanghai）。结论：**限定已实际完成链路 `REVIEW_PASS`；原两项当前检查目标仍未完成，切片维持 `BLOCKED`，等待用户决定是否调整限定接受范围。**本报告不记录接受，不启动 WP-13，也不把 `unknown` 区域卡解释为确诊、排除或最终报告就绪。本审核任务与此前实施、整改处于同一任务链，不声称不同任务的独立审核。

## 基准及证据分层

已核对 [STATUS](../STATUS.md)、[契约](diagnosis-slice-contract.md)、[预算策略](diagnosis-slice-budget-policy-r1.md)、[前模型整改](diagnosis-slice-pre-model-remediation-r1.md)、[候选修复整改](diagnosis-slice-repair-remediation-r1.md)、[续轮决策](diagnosis-slice-next-decision.md)、对应实现和测试。当前 `runner.py` SHA-256 为 `04BADD429171E23B7240D261B99AB1E91ECFB9E3C65F8CCED98945C20E4C910A`，与最终候选整改记录一致；`model_gateway.py` 为 `319382D44F31F2D2DBFD3F68C0DE2ED4C0BA4FE849AB628BA334117F9FDD50CB`，`model_budget.py` 为 `CF95B694F5EA6FFAA9A1125945DAD135F70BCE051F2851537F59052CA5A3C7E5`，`publish_service.py` 为 `2178DC8F4FE610AEDFDCAF1FB57CC9962A16E6E88AEF9AE331A028FA46D0717B`，`observation_service.py` 为 `35C3724D870F770044FA980F15722FEDF2C153279F727F81A44BAC694E325590`。Git index SHA-256 `C451D6E78B8F29FC818002923A19FB1A888139CED20679AD545F75E9692A9EC6`，与前述封存记录一致；原有暂存和未提交文件未清理、提交或改动。

执行者的[脱敏汇总](evidence/diagnosis-slice-repair-r1/summary.json)和本机受限 `.test-runs/diagrepair_live_416a9bd4/` 分别保存免费定点、真实初轮、浏览器观察、真实续轮及刷新证据。最终整改测试文件分为互斥的 5 项和 4 项，均通过；此前 7 项属于较早测试字节版本，旧完整回归也属于较早源码版本，均不冒称当前全仓重跑。真实首轮 `live.xml` 为 1 passed、命令退出 0。续轮业务断言脚本退出 **1**：run 实际 `succeeded`、发布了一张 `unknown` 卡，但断言要求第二项检查进入 `waiting_input`，故不能称两步目标通过。浏览器首次截图捕获超时及后续只读刷新成功分别保留，不能抹去首个失败。

本轮只读核对源码、报告、测试、有限私有诊断字段和原隔离库；未新建数据库、未运行模型或新增免费测试。`Get-Content`/`Get-FileHash`、`rg` 及针对原隔离库的只读 SQLAlchemy/psycopg3 对账命令均退出 **0**。私有诊断仅提取 `stage=initial`、`candidate_type=conclude_area`、`schema_status=valid`、`disposition=needs_input`、`issue_count=0`；未输出候选原文、资料正文、工具参数、连接信息或完整账本。

## 已交付链路的判定

| 检查 | 结论 | 本轮核对与证据界限 |
| --- | --- | --- |
| 可信身份、冻结范围及引用 | **PASS（隔离合成范围）** | `runner` 从持久 run/case/graph epoch 装配上下文，经既有工具执行器读取冻结 manifest；发布前 `HardGate` 重新验证来源、所有权、epoch、版本和资格。原隔离库只读核对：manifest 恰有一份 `synthetic=true`、`formal_usable=false` 的 BGE-M3 1024 维 ready 索引；首项 6 条引用均属于该冻结来源且当前有效。未把模型返回的 UUID 当授权。 |
| 真实模型、工具、校验与首项发布 | **PASS（首项）** | 脱敏真实探针记录 DeepSeek 3 次请求、工具 4 次尝试；首项经过原 `ProposalService`，run=`waiting_input`、`publish` 恰一条、当前检查持久存在，独立进程读回同一步骤及 revision。`publish_waiting` 在同一事务检查 owner、epoch、revision、租约/fencing、当前来源与候选，提交步骤、事件、case revision 和 publication；本轮数据库再次核对 publication 与 step/run 对应。没有证据支持将该检查称为 DKVB 真实维修建议。 |
| 浏览器观察与续轮关联 | **PASS（一次合成观察）** | 独立浏览器按服务器步骤 schema 保存一条观察，刷新仍读到；只读数据库核对观察属于首项且 `checked=true`，case revision 从 1 到 2，child run 指向该 observation 和 parent。`ObservationService.submit()` 在 owner/case/parent 锁及 revision/epoch 校验下，同事务写观察、完成步骤、修订号、child run/job、事件及幂等响应；公开旧 resume 不接收任意观察 JSON 推进。先前 WP-12 的并发/更正范围沿用其限定接受，未在本轮重审。 |
| 真实续轮、区域事务与刷新 | **PASS（保守收尾），第二检查未完成** | 续轮 DeepSeek 2 次请求、工具 4 次尝试，run=`succeeded`，只发布一条 `area_close`；服务端核对已保存观察和当前来源后生成 `assessment=unknown` 卡。只读库核对首项 `completed`、观察 1 条、case revision 3、`needs_review`、无当前待答步骤；卡仅关联该观察及 6 条有效来源。独立刷新仍显示观察和待复核状态。没有第二项当前检查，续轮业务验收脚本退出 1，原两步目标未完成。 |
| 一次修复出站脱敏 | **PASS（已测支持载体）** | 真实首轮走过有限修复路径。当前 `runner` 仅向一次修复提供被拒结构化候选和有限 code/path，修复结果仍重新经 `ProposalService`。网关在预算预留/SDK发送前复制、校验和脱敏字符串、多文本块、工具调用 JSON 参数及工具消息，拒绝不支持载体。最终版免费 MockTransport/隔离库测试的 5+4 项覆盖第三次实际请求体、合成邮箱替换、原候选不变及修复失败分支；本轮未再产生付费请求或公开私有候选。 |
| 共享账本与单 turn 门禁 | **PASS（本地计量控制）** | 原 v1→v2 迁移保留历史调用、状态和 usage，策略为持续计量、无累计金额拒绝上限；锁内原子预留、唯一 key、deepseek-flash/API 白名单、发送前期限复查及四请求/120 秒限制仍在代码和免费预算/网关测试中。真实链路账本由 21→26 条调用，累计保守预留 ¥2.839008→¥3.734104，新增 ¥0.895096；5 次均报告 usage，按本地价格估算 ¥0.080946。未读取或修改本轮真实账本；这些数是执行者封存证据，**不是平台账单**。 |

## 续轮选择与未完成范围

[免费定点决策](diagnosis-slice-next-decision.md)核对当前 P01 观察、合成原文、检索与 12 条已绑定引用后归为 **A：资料或条件不足，保守收尾合理**。Q02 的简介、位置和检查动作存在，但原文没有“P01 外观完好后转向 Q02”的条件关系；当次引用也未覆盖 Q02 两个选项。直接使用该 turn 已绑定引用经原 `ProposalService` 检查 Q02 候选，得到两个 `EVIDENCE_REQUIRED:choices`。未证明补足引用后 Q02 应当成为下一步，也未证明通用推理能力。模型的 `conclude_area` 不构成第二项检查，`unknown` 不能提升为确诊、排除或报告就绪。

本次 `REVIEW_PASS` **仅建议用于**“真实模型产生一项有据检查 → 浏览器保存合成观察 → 真实续轮保守 `unknown` 收尾 → 刷新读回”的技术链路。原切片要求的观察后再发布第二项当前检查仍缺证据，因而继续 `BLOCKED`；是否按已证明范围调整并接受，应由用户决定。真实资料门槛 `NOT_MET`，DKVB 精确适配及真实维修效果、生产恢复、最终报告和 WP-13 均不在本次通过范围。本轮未发现对上述限定链路必须整改的具体缺陷；若后续要求 P01→Q02，须先补可追溯且经审核的条件依据，再验证引用覆盖和正反例，不能为演示预置答案。

本轮仅新增本报告，并只修正 STATUS 首段与最新证据矛盾的表述；切片状态仍 `BLOCKED`。未修改实现、契约、历史报告/证据、Git index，未操作 5180/5196，未调用付费模型或部署。
