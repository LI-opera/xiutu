# DKVB-001 定点复核 r2

日期：2026-09-19。最终结论：**REVIEW_PASS（限定DKVB/P0299合成专题检索与原页定位技术范围）**。DKVB-001关闭；结合r1未变部分，建议用户决定是否限定接受。未替用户接受或部署。

## 范围与流程披露

仅复核DKVB-001整改。本任务参与过专题实施及前次审核，不声称不同任务独立审核。没有修改实现、STATUS、接受记录或历史证据，没有重新审核整包。

已读r1审核、整改报告、implementation.diff及对应测试/HTTP/浏览器/保护记录。当前4899项整改交付封存匹配。与整改开始基准相比，仅三个已声明文件改变：

- backend/app/dkvb_preview.py：references简介end由全文末尾改为首个2—6级标题起点，修正注释。
- tests/unit/test_dkvb_topic.py：新增真实标题/简介、直接引用和无分节短文回归。
- dkvb-topic-contract.md：状态文字同步。

解析、chunker、检索排名、前端和资料内容未改，原断言/失败日志未覆盖。原资料包与封存构建匹配。结束4900项保护文件无差异，Git index不变，见baseline.json、scope-check.json、protection-after-db-start.json。

## 定点判断

| 要求 | 结果与依据 |
|---|---|
| 标题/简介不继承后文PDF及DS | PASS。真实raw经现有parser/chunker重建的标题/简介两例、原审核失败反例均通过；隔离API实际标题检索仍命中同正文和locator，pages=[]、simulation_specs=[]。 |
| 简介自身直接引用仍返回 | PASS。首标题为二/三/六级的三例均返回S01/1、relation=chunk，排除后文S02/DS。 |
| 正常多级、多页、FACT/DEMO不退化 | PASS。既有和审核补充映射例通过；实时正常命中保留S02/6，PDF SHA256一致，页图返回PNG。历史四问和页面证据作为未变链路引用，不冒称本轮全部重演。 |
| 不删标题、不改资料或排名 | PASS。差异/hash核对无相关改动；本轮真实查询返回标题，不是删除命中规避错误。 |

修复在没有前置分节标题时将上下文截止首个分节标题；正常节仍按相邻标题分界，无分节短文保留其自身上下文。直接引用/同节关系标签及模拟提醒保留。未发现必须继续整改项。

## 本轮实际验证与历史证据

证据：`evidence/dkvb-topic-review-r2/`；cwd均为`E:\Work\xiutu-v5`。

1. `.venv\Scripts\python.exe -B -m pytest tests/unit/test_dkvb_topic.py docs/implementation/product-preview/evidence/dkvb-topic-review-r1/test_audit_boundaries.py --basetemp <本轮独立TEMP>/pytest --junitxml <本轮目录>/targeted.xml`
   - **一次运行，16 passed，0失败/错误/跳过，2.27秒，退出0**。
   - 完整argv、起止时间见test-command.json；原始targeted.log/XML保留。原审核反例内容未改。
2. 独立5199 API：`start.py`退出0。复用整改专用隔离库/storage及既有测试case，不使用5180/5196数据；无新导入、迁移或worker。复用匹配的dist-sealed（index-Cm_Gkvfa.js），未构建前端。
   - Cookie使用本轮专名xiutu_dkvb_review_r2，包装只隔离传输Cookie名称，不替换认证/检索/映射判断。HTTP客户端拥有独立cookie jar，未触碰用户浏览器Cookie。本轮不重复浏览器四问；引用整改页面证据。
3. 首次`check.py`退出1：实际title search返回503。单次诊断chunk GET和检索均DATABASE_UNAVAILABLE、retryable=false；Docker Linux引擎管道不存在、5433不可达。见http.log/http-results.json、diagnosis.json、environment-check.json。
   - 曾尝试直连细分诊断，审核脚本重复传connect_timeout发生TypeError，未建立连接，不作为产品反例。
   - 中间BLOCKED记录保留在blocked-draft.md，第一次审核进程停止记录见stopped.json。
4. 用户回复“我会启动，继续等待”，随后5433已恢复。只重启本轮API，运行`start-after-db-start.py`及`check-after-db-start.py`，**退出均0**。这是外部环境恢复后补齐未成功执行的抽查，没有修改业务实现、放宽断言或循环重跑测试。
   - 实际两条查询：原实际标题、正常泄漏问题。标题需在真实返回列表中存在；读取其chunk映射与原正文/locator一致，无后文页号及DS。
   - 正常FS-02命中保留S02物理第6页；授权PDF返回hash与映射一致，授权页图PNG成功。见http-after-db-start.log、http-results-after-db-start.json（包含起止时间、完整查询和选中来源）。
5. 结束停止仅自身审核API，见stopped-after-db-start.json。没有重跑16项、四问、旧22项、撤销/重复导入、白名单或历史全仓。

证据版本分别解释：

- r1：9通过、1映射失败，及真实四问/范围/权限/重复导入/撤销/页面状态检查。
- 整改自测：15通过、1夹具setup error；仅该项独立basetemp补测1通过；另有实际HTTP与页面证据。不能描述为一次16项整体通过。
- 本轮r2：最终版本16项一次通过；首次HTTP环境失败保留，用户恢复数据库后两条实际接口抽查通过。重复证据不累加成不同功能覆盖数。

## 接受建议与保留边界

DKVB-001已关闭，结合r1未变部分，无新的具体阻断缺陷，给出限定范围REVIEW_PASS。用户仍需决定接受及部署；本轮没有更新5196。

不将标题映射修复扩展成BGE优于E5、OCR、复杂版式识别、正式资料审核、真实车辆适配、AI诊断或维修效果通过。真实资料NOT_MET、PDF needs_ocr、同任务流程限制、Linux BGE未验证及历史SSE/Compose/启动根因未确认继续保留。数据库恢复后的成功不证明历史平台问题根因已查明。

## 保护与停止

5180 PID8820及5196 PID12172创建时间与基准一致，未重启或覆盖其数据、构建、访问配置。原资料、历史报告/证据、接受记录及Git index未改；本轮只新增报告和审核证据。无付费、无账本读取、无提交推送，不进入WP-11。审核实例已停止，等待用户决定。
