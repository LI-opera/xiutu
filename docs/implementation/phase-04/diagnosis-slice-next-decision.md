# 诊断闭环切片：续轮 Q02 免费定点决策

记录时间：2026-09-21 01:14（Asia/Shanghai）。**分类 A：现有资料缺少从 P01 当前观察转向 Q02 的条件关系，保守 `unknown` 收尾合理。**这只判断本次合成台架续轮；不代表模型在其他资料上必须收尾，也不把未发布第二步写成真实模型闭环成功。切片仍为 `BLOCKED`，不修改验收标准或启动 WP-13。

## 核对依据和结果

- [合成台架原文](../../../tests/fixtures/diagnosis-slice/bench.md) SHA-256 `5642124A1326A8861259F75A76CE35C621EDE74ACA2822E574A280BEEA65BF70`；`synthetic=true`、`formal_usable=false`。第 19、21、23、25、27 行分别有 Q02 简介、位置、外观检查动作和两个观察选项，第 9 行有 `engine=off` 工况。第 3、29 行说明对象和观察仅为测试输入。全文没有“P01 外观完好后应检查 Q02”或等价的条件分支；也没有诊断、正常判定或维修结论依据。
- 只读查询原隔离库 `xiutu_test_diagrepair_live_416a9bd4`：case revision 3，冻结 manifest 恰含 [免费预检](evidence/diagnosis-slice-repair-r1/summary.json)所记录的同一 BGE-M3 1024 维索引；一条 P01 choice 观察为 `checked=true`、`appearance_state=intact`、`engine=off`。首轮 step 已完成；续轮 run `succeeded`，仅发布 `area_close`，区域卡 `assessment=unknown`、`basis=observations_without_trusted_conclusion`、引用一条观察和 6 条当前有效来源；无第二项 step。它没有将“完好”升级为部件正常或排除故障。
- 续轮工具审计：`search_manuals` 一次、`get_evidence_context` 三次，均成功；搜索的 5 个命中中有 Q02 简介和动作，邻块返回了 Q02 位置。根据 [runner.py](../../../backend/app/agents/runner.py) 的 `source_chunks[:12]`、12 条该 turn 的 `graph-*` evidence 绑定及审计记录，可重建提供给模型的引用覆盖原文第 1、3、5、7、9、11、13、15、17、19、21、23 行；**未覆盖 Q02 选项的第 25、27 行**。模型没有另行发起资料工具调用。这里是引用覆盖缺口；它本身不能补出原文缺失的 P01→Q02 条件关系。原始出站请求体未封存，故“提供给模型”的判断基于代码及该 turn 的持久绑定/审计对账，不冒称网络包实录。
- 在该隔离库用**现有 `ProposalService.validate()`**、当前 revision 和 P01 检查历史，按 Q02 原文第 19/21/9/23/25/27 行构造非数值候选。仅使用续轮实际已绑定的引用时，结果 `accepted=false`、`disposition=needs_input`，问题恰为两项 `EVIDENCE_REQUIRED:choices`；没有绕开资格、来源或语义门禁。**未证明补齐第 25/27 行引用后该候选会通过**，更没有证明“此时应选 Q02”。

## 命令、限制和建议

在 `E:\Work\xiutu-v5` 使用 `.\.venv\Scripts\python.exe -` 运行只读 SQLAlchemy/psycopg3 元数据、工具 receipt、fixture 行号及卡片有效性查询，和上述 `ProposalService.validate()` 定点调用：最终各命令退出码 **0**，服务结果为上述明确拒绝；没有创建 turn、调用模型或修改原病例。最初一次连接因默认 psycopg2 未安装而退出 1，改用项目已安装的 psycopg3；一次行号审计 SQL 因参数类型转换语法错误退出 1，修正后只重做该只读查询。另尝试创建并删除唯一命名的隔离库克隆来补齐两条 Q02 evidence，**自动审批以会修改持久数据库为由拒绝，未执行**；因此完整有据 Q02 正例列为未验证。受限原始候选、DSN、工具参数和完整账本未进入本记录。

推荐按 **A 路线**：把当前真实链路如实整理为“有出处的 P01 检查 → 保存观察 → 保守待补/unknown”，由用户决定是否调整此切片的限定验收范围。若产品确需依据 P01 结果自动推进 Q02，先补一条**通用、可追溯且经审核的条件分支依据**，明确哪类 P01 观察、工况与适配范围触发 Q02；不能把 Q02 自身的检查描述当作分支依据，也不能为演示直接改写原资料。之后再定点核对 bounded 检索/引用是否将 Q02 选项一起提供，并以有据正例及误放行反例验证。当前不因 12 条引用上限这一覆盖现象单独判定“资料已足够、只需改提示词”。

核对前 `runner.py` 哈希与 [整改记录](diagnosis-slice-repair-remediation-r1.md)一致，为 `04BADD429171E23B7240D261B99AB1E91ECFB9E3C65F8CCED98945C20E4C910A`；Git index SHA-256 为 `C451D6E78B8F29FC818002923A19FB1A888139CED20679AD545F75E9692A9EC6`。本轮没有修改实现、测试、合成资料、STATUS 或历史证据，也未操作 5180/5196。该决定不是切片审核或接受。
