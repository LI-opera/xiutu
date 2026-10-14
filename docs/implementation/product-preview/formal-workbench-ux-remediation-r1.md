# 正式工作台可用体验整改 r1

- 日期：2026-09-21（Asia/Shanghai）
- 状态：IMPLEMENTED_NOT_ACCEPTED
- 范围：WP-15 已接受工作台之上的本地体验整改；WP-16、WP-17 未启动
- 体验地址：http://localhost:5215/
- 直接病例：http://localhost:5215/workbench/3bcb3364-4ecd-4252-9d61-7a4aa1e21ef9

## 根因与价格策略

原体验管理器读取私有 .env 后使用旧模型名；持续计量 v2 只登记 deepseek-flash，因此旧 run 在出站前以 MODEL_PRICE_UNVERIFIED 拒绝，没有 usage。隔离体验管理器现由可信服务端固定 deepseek-flash，未修改或输出私有 .env。

免费预检确认账本 version=2、policy=metered_no_cumulative_cap。累计金额不再拒绝调用，也没有固定日期价格拒绝。未知模型、单 turn 四请求、120 秒、工具次数、一次修复及出站前期限检查继续生效。预检终态 not_sent，没有网络请求或费用。脱敏证据位于 .local-data/formal-user-experience-r1/ux-preflight-sanitized.json。

## DKVB/P0299 演示边界

P01/Q02 技术夹具不再作为用户入口。新病例显示虚拟探岳演示台架加速无力、P0299，以及“检查增压空气系统是否存在可定位漏点”。页面展示目的、位置、工况、操作、中文观察选项和原文入口。

页面始终标识 DEMO、SYNTHETIC、formal_usable=false、非真实车型维修验证。原专题包保持只读；三份 PDF 仍为非虚构待核实且 needs_ocr。新增 tests/fixtures/diagnosis-slice/dkvb-guided.md 是从已有 CHK-05 与 S02-P1/P2 有限事实派生的合成表达，不含隐藏答案，不预定观察结果，不声明真实压力、真实适配或维修结论。

只增加有限语法：装配图位置、禁止真实气源的演示工况、局部泄漏动作，以及“已定位／未发现／无法确定”三个选项。ProposalService 的来源、版本、车型、位置、工况、动作、选项和授权门禁保持不变。

## 工作台改动

- 顶部流程状态改为等待检查、等待填写观察、正在生成下一步、资料不足、运行失败、已完成，并给出下一步说明。
- 已保存观察默认显示中文卡片；原始 JSON 移入默认关闭的技术详情。
- failed 显示失败阶段、观察是否保存、可确认的费用状态和恢复建议；内部 code 只在技术详情中。
- CASE_NEEDS_REVIEW、AREA_UNFINISHED、CONCLUSION_MISSING 等改为中文说明；unknown 明确是待补。
- 依据按钮显示“查看依据 1/2…”，先展示来源性质、有效性和原文入口，内部 ID 移入技术详情。

修改文件：

- frontend/src/formal/diagnosis/presentation.ts
- frontend/src/formal/pages/WorkbenchPage.tsx
- frontend/src/formal/diagnosis/WorkbenchParts.tsx
- frontend/src/formal.css
- frontend/tests/formal-workbench-ux.test.ts
- backend/app/validators/support.py
- backend/app/validators/repetition.py
- backend/app/validators/proposal.py
- backend/app/agents/runner.py
- tests/unit/test_dkvb_demo_grammar.py
- tests/integration/test_wp10_proposals.py
- tests/fixtures/diagnosis-slice/dkvb-guided.md

私有运行文件 experience.py、ux_remediation.py、one_time_login.py 保留在 .local-data/formal-user-experience-r1，不进入公开封存。

## 浏览器和真实 turn

验证病例为 0e663d01-0fca-426b-84ae-d958ebecdb17。浏览器实际打开首项检查及依据，选择“局部泄漏结果无法确定”，确认演示工况并保存。观察保存后页面进入“正在生成下一步”。

唯一真实续轮最终为 AREA_NEEDS_INPUT。页面显示运行失败、服务端门禁尚未满足、观察已保存和管理员处置建议。数据库中观察 1 条、revision=2、publication 共 1 条（仅原首项检查），没有新增下一检查或结论卡。该结果没有被伪装成成功。

计量：聚合保守预留从 4.833088 增至 5.180096；本 turn 两次 deepseek-flash 请求均 received、usage=reported。请求 token 分别为 5907+159 与 5020+159，finish_reason 均为 stop，tool call 均为 0。预留和 usage 估算不是平台账单。失败后未创建第二个 turn。

## 验证

最终免费验证：

- test_dkvb_demo_grammar.py：1 passed。
- test_dkvb_guided_demo_step_is_bounded_and_source_backed：1 passed；使用全新 xiutu_test_* 数据库并迁移后运行。
- formal-workbench-ux.test.ts 与 wp15-workbench.test.tsx：17 passed。
- TypeScript typecheck：通过。
- 独立 Vite build：通过，输出 .local-data/formal-user-experience-r1/dist-ux-final；只有依赖包 use client 指令被忽略的非阻断警告。

保留失败记录：首次漏设 TEST_DATABASE_URL；误用持久体验库；新隔离库未迁移导致 ready=503。迁移后同一集成用例通过，没有放宽断言。

浏览器亲测中文状态、当前检查、依据、观察提交、处理中、失败解释、折叠技术详情和刷新持久状态。

## 体验步骤

令牌文件：E:\Work\xiutu-v5\.local-data\formal-user-experience-r1\access.txt。

1. 打开直接病例链接。
2. 如提示登录，从令牌文件复制令牌。
3. 阅读 DEMO/SYNTHETIC 边界和 P0299 现象。
4. 阅读首项检查的目的、位置、工况和操作。
5. 点“查看依据 1”打开来源。
6. 推荐选择“局部泄漏结果无法确定”，勾选演示工况。
7. 点“保存观察并启动下一轮”；此操作会触发 DeepSeek 并产生少量计量。
8. 查看下一检查或有解释的资料不足/失败状态，刷新确认观察和状态仍存在。

进度报告由用户主动请求；最终报告继续受服务端 ReportPolicy 门禁。

## 运行与停止

当前前端 5215、API 8215、MCP 8315 和 worker 均运行，数据库为 xiutu_test_formal_user_e4faa7fa2769；storage、病例、资料和会话保留。

停止命令：

    E:\Work\xiutu-v5\.venv\Scripts\python.exe -B E:\Work\xiutu-v5\.local-data\formal-user-experience-r1\experience.py stop

该命令只停止本实例登记的进程，不清数据库或 storage。

## 限制

- 这是合成技术演示，不是 DKVB 实车维修验证。
- 真实资料仍 NOT_MET，未实施 OCR。
- 唯一真实续轮未发布第二项检查；当前是安全的资料不足路径。
- 未证明确诊、排除、换件建议、真实维修效果或真实最终报告。
- 本切片未接受，WP-16、WP-17 未启动。
- 未操作 5180/5196，未提交或推送。

## 用户复验后的显示补正

用户在直接病例提交“未发现局部泄漏”后，真实续轮同样返回 AREA_NEEDS_INPUT。该结果再次确认现有资料缺少从当前观察转向下一项检查的条件关系；不是价格门禁，也不是用户操作错误。

本次只修正页面表达，未调用模型、未改变后端状态或诊断门禁：

- 顶部由“运行失败”改为“资料不足，暂时无法继续”；
- 明确观察已保存，系统没有编造下一检查或维修结论；
- run 卡改为“资料不足／当前流程已保守停止”，隐藏与用户无关的费用管理员提示；
- 中栏明确显示“本区域暂时无法收尾”，并解释“未发现局部泄漏”不等于部件正常、故障排除或维修完成；
- needs_review 和 active 分别显示为“需要人工核对”和“当前区域”；
- 保留技术详情中的内部 code，供定位使用。

补正后 focused frontend tests 17 passed，TypeScript typecheck 通过；浏览器在用户当前病例中确认新文案实际生效。该补正没有产生新的 DeepSeek 请求。