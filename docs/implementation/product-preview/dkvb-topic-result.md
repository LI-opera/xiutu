# DKVB/P0299专题：资料检索与原页定位

状态：IMPLEMENTED_NOT_ACCEPTED。完成实现与执行者自测，等待集中检查；没有自行审核或接受。

现在可以在独立页面输入自然语言，真实检索两份整理正文，打开命中版本、chunk、原文上下文、来源PDF和完整页图。所有结果均为虚拟车辆专题演示，不能当作诊断或厂家标准授权。

## 体验地址与步骤

地址：http://localhost:5196/#dkvb 。须使用localhost以避免与127.0.0.1:5180同名cookie互相干扰。
访问令牌在本机 `.local-data/dkvb-topic/access.txt`，不要贴到报告或对外发送。登录后选择专题，点击“新建专题检索会话”，选择问题或自行输入问题，点击“检索专题资料”，再打开“整理正文与来源页”。来源页按钮显示物理页号及直接/同节引用区别，PDF链接带#page，完整页图在页面内显示。

四个建议问题：
1. 增压空气系统泄漏检查为什么不能用保压下降判断？（实测S02第6页）
2. G31的位置依据在哪里？（实测片段列S02第1和第4页；第4页定位）
3. V465调整应查哪份原文？（实测S03第8及第9页分别列出）
4. 演示压力跟随阈值是多少，是否属于厂家标准？（实测DS-02、±150明确为模拟，未挂厂家PDF）

在 E:\Work\xiutu-v5 执行：
```powershell
.venv\Scripts\python.exe -B scripts/dkvb_topic.py status
.venv\Scripts\python.exe -B scripts/dkvb_topic.py stop
.venv\Scripts\python.exe -B scripts/dkvb_topic.py start
# 已导入后可核验/复用，不会重复构建ready索引：
.venv\Scripts\python.exe -B scripts/dkvb_topic.py import
```
不要再次init，不要对5180执行任何停止或切换。脚本只匹配自身PID及创建时间；数据库和storage停机后保留。API与worker是同一个独立体验实例的两个进程，交付时保留运行。

## 实际数据与资格

独立库xiutu_test_preview_dkvb_a0f2f43b4a，storage `.local-data/dkvb-topic/storage`。5份文档/5版本，其中仅两份白名单Markdown获用户授权的合成演示审核、生成2个ready索引、118条向量；BGE-M3 1024维、固定revision5617a9f61b028005a4858fdac845db406aefb181，配置指纹见HTTP证据。未重做模型选型或质量评测。

3份PDFsynthetic=false，来源/许可unknown，未审核、未索引。实际解析均needs_ocr，按包内不可变PDF及已有页图查证；不声称PDF抽取完整。实际PDF物理页数1/6/9；PNG与PDF按包内S01/S02/S03固定映射、SHA256核对。两份手册synthetic=true、formal_usable=false。年款和发动机系列未知，不补造，适配返回unknown/通用参考。

manifest全文件大小/hash已验证，但仅两份Markdown入检索；3份PDF只查证，其他控制/病例/整理文档仅可校验hash，不进入索引或模型上下文。未请求外部链接、未注册知识JSON中的规则。没有模型生成或付费请求。

重复导入已验证：5文档、5版本、2索引、118向量不变。已批准版本复用；被撤销/拒绝版本停止导入，不自动重批；未完成任务或失败不能宣告ready。

## 修改与接口

新增backend/app/dkvb_preview.py、frontend/src/dkvb-topic.tsx、scripts/dkvb_topic.py、scripts/probes/dkvb_verify.py、tests/unit/test_dkvb_topic.py。main.tsx仅新增#dkvb页面分派；原上传/候选页面逻辑未改。无迁移；没有改旧索引、模型文件或已有服务资格算法。

GET /api/v2/topic；POST /topic/cases；POST /topic/search；GET /topic/cases/{cid}/chunks/{chunk_id}；GET /topic/sources/{sid}/{page}及/image。均处于/api/v2，认证/写入Origin/CSRF沿用已有服务，参数不接收owner/profile/路径。专题case的冻结manifest必须恰好包含本包两份白名单版本，否则拒绝。原文再复验owner/manifest/index/epoch/资格；PDF与页图不公开静态挂载。OpenAPI快照见证据。

## 验证与失败记录

命令cwd均为E:\Work\xiutu-v5，无真实模型费用账本访问。

- `scripts/dkvb_topic.py init/start`：退出0，已确认Docker项目标签与5433归属，创建独立库并迁移现有head。未操作既有卷或数据库。
- 首次import：退出1，httpx已登录客户端二次进入context导致RuntimeError；尚未上传。failure-01.txt保留。改用closing后import退出0，两正文真实解析/BGE完成。
- `pytest tests/unit/test_dkvb_topic.py`首轮：4通过/2失败，中文紧邻Sxx引用被\b漏识别。unit.log/XML保留。修复ASCII边界、/P9简写及子标题上下文后，受影响集合7通过，mapping-fixed.log/XML；未削弱断言。
- `scripts/probes/dkvb_verify.py`首轮及映射修正后分别退出0：4问题、真实BGE、冻结版本、PDF/PNGhash、401、错误case404、伪profile422。对应http-*目录分开保存，不合并覆盖数。修正后证据http-b8d822c0。
- 重复import退出0。最终final_probe.py退出0，针对新增DS结果标签、无PDF阈值归因、重复导入计数、跨owner ASGI404（可信依赖注入另一个actor，不冒称第二真实用户登录）。
- `node --test frontend/scripts/preview-context.test.mjs frontend/scripts/material-intake.test.mjs`：22通过/0失败，原预览状态回归，不冒称新增专题22项覆盖。
- `npm --prefix frontend run build -- --outDir <独立目录>`含tsc检查，各构建退出0。映射/DS展示/专题切换改动后只重新独立构建；最终dist-sealed，JS index-Cm_Gkvfa.js。Vite保留outDir不自动清空警告，不操作frontend/dist。
- 浏览器localhost独立cookie：四问检索、原文、S02完整页图（1061×1500）、PDF链接实际打开S02/6#page=6；最终DS结果卡片直接标DS-02，模拟正文没有PDF按钮。新会话、取消专题选择清空命中/原文；无会话禁用检索。刷新不显示旧来源，需新建会话。截图/DOM证据分版本保留。
- 浏览器一次相同URL导航并未刷新，随后登录选择器不存在；通过真实新导航确认重启后登录，不把取证操作异常当业务通过。记录见browser-notes。

## 范围与限制

检索排名未进行新增召回评测，部分首位是标题chunk，需要展开同节上下文；页面明确区分直接引用与同节引用，不能把全文所有结论都归给一页。模拟标准引用模拟正文，FACT也不代表来源/许可或实车适配已核实。

原PDF可能依赖浏览器PDF查看器执行#page定位，页图总是提供完整对应物理页；不伪造文本高亮。未实施OCR、任意大文件、正式审核平台、AI诊断、观察提交、自动下一步、报告、可信规则或WP11/12。

真实资料NOT_MET，原截止要求未满足；E10沿用原限定结论、Linux BGE未验证、历史SSE/Compose/启动未确认根因及既有待办保留。本轮只有Windows本地BGE检索体验，不改变历史接受范围。

## 保护与停止

5180未重启、未替换构建、未操作原数据或访问配置。旧frontend/dist、历史报告/接受/证据、旧迁移及Git index哈希核对见final-protection.json。原资料包重新验证无变化。交付只留5196体验实例，状态IMPLEMENTED_NOT_ACCEPTED，等待一次集中检查，不自行审核或接受。
