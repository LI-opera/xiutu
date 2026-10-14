# DKVB-001 标题／简介映射定点整改 r1

状态：**IMPLEMENTED_NOT_ACCEPTED**。日期：2026-09-19。完成整改与执行者自测，等待仅针对本差异的复核；不是审核关闭、接受或部署。

## 最小修复

原因：references()在命中位于第一个二至六级标题之前时，没有进入章节分支，原end保持全文长度，使标题／简介继承后文所有来源和DS标记。

仅修改：
- backend/app/dkvb_preview.py：简介end设为首个二至六级标题起点；无此类标题时使用该短文自身。后续章节仍以相邻二至六级标题分界。同步修正原level-2注释。没有修改提取正则、排序、chunk、源资料、资格或前端。
- tests/unit/test_dkvb_topic.py：增加真实审核标题／简介片段、三级标题深度下简介直接引用，以及无分节短文的回归。真实片段取自原审核保留的raw，使用现有parser/chunker重建并核对locator，不依赖跨库UUID。
- dkvb-topic-contract.md：状态文字由“实施中”同步为IMPLEMENTED_NOT_ACCEPTED。

真实前后差异见evidence/dkvb-topic-remediation-r1/implementation.diff。

## 定点测试与保留失败

所有项目命令cwd为E:/Work/xiutu-v5。完整argv、时间和退出码见本轮各*-command.json。

1. 运行tests/unit/test_dkvb_topic.py及原审核test_audit_boundaries.py一次：**15通过、1 setup error**。原审核preamble失败反例、本次标题/简介/直接引用及原多页/子标题/混合FACT-DEMO正例均通过。
2. 唯一error是旧test_path_escape的tmp_path夹具访问默认TEMP/pytest-of-Administrator目录遭WinError 5，测试函数尚未执行。targeted.log/xml保留。仅为此项指定新的独立--basetemp后，**1项通过**，见path-only.log/xml。未改实现或断言、未重跑整组。
3. 不将这两轮写成一次16项全通过，也未重跑历史全仓、旧22项前端状态或模型质量评测。

## 真实接口与页面

新建独立测试库、storage、actor/registry，API/worker在127.0.0.1:5198运行。仅为本次验证导入同一未变资料包并建立BGE1024索引，不重做重复导入、撤销或白名单审核。复用已匹配dist-sealed（index-Cm_Gkvfa.js）；前端未修改、未重新构建。

http-results.json记录实际HTTP结果：
- 从新库找到与原审核反例相同正文及locator的标题chunk，返回pages=[]、simulation_specs=[]；section_context恰好截止第一节，未删除标题命中或更改检索排名。
- 四个真实BGE问题均返回结果：泄漏方法仍有S02/6，G31仍有S02/4，V465仍有S03/8及9，模拟阈值命中保留DS-02且不挂厂家PDF。命中正文hash与对应源版本内容核对通过。

浏览器验证：内置cua_repl两次及node_repl一次均在初始化阶段报“failed to write kernel assets”，未完成浏览器操作。随后使用机器已有Playwright及Edge，以全新headless上下文完成真实页面验证，没有安装软件或连接用户浏览器。

- 登录、新建会话、以真实标题查询并点击该标题命中：页面没有PDF页按钮或模拟规格链接，显示“该片段未提供本地PDF页映射”。
- 选择正常泄漏问题、打开FS-02命中：S02物理第6页按钮与PDF链接正确，完整页图1061×1500实际加载。
- browser-results.json、browser-title/normal.png及对应DOM文本保存结果。没有拦截伪造搜索响应、没有注入页面内部状态。

隔离实例复用审核helper的独立Cookie包装，改为xiutu_dkvb_remediation_r1；另有全新浏览器上下文隔离。仅改Cookie传输名称，未替换认证、来源或检索判断；helper的屏障未启用。本轮不重做迟到响应审核。

一次只读控制台摘要输出遇GBK编码错误，改为ASCII转义后读取同一结果；原HTTP验证文件完整，未重跑接口或修改业务。

## 保护、证据与停止点

baseline.json记录本轮开始4854项保护文件、原资料包31项（含manifest自身）、原构建及5180/5196监听PID和创建时间；结束比对见final-protection.json。历史审核报告及失败证据保持不变，原资料包、STATUS、旧迁移、前端构建和Git index不改。

本轮浏览器上下文已关闭；5198专用API/worker已按登记PID及创建时间停止，测试库/storage保留供复核。**5180和5196未更新或重启，用户5196尚未部署本次修复。** 后续启动工作区代码会加载新实现，本次没有执行用户实例重启。

未付费调用、未读取费用账本、未提交推送、未进入WP-11。原PDF needs_ocr、真实资料NOT_MET、同任务历史流程限制和原有未确认根因不变。完成后停止，等待定点复核及用户决定。
