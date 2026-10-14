# WP-04 资料上传、解析、审核与版本交付

状态：IMPLEMENTED_NOT_ACCEPTED。完成时间：2026-09-18T13:26:26.514368+08:00。本记录是执行者实现与自测结果，等待一次审核及用户接受；未生成审核通过结论，未进入WP-05。

## 现在能做什么

可导入本地UTF-8 Markdown及未加密PDF，保存不可变原文和版本，通过真实ingest worker解析/切块、查看chunk和原文定位、记录人审历史。普通文本PDF逐页定位；扫描或含图缺项明确needs_ocr，混合文档保留能读取页面但不冒充完整。人审approved显示index_pending且index_implemented=false、formal_usable=false。没有OCR、embedding、索引、检索、Agent、真实诊断或资料管理页面。

用户按README静默配置本项目凭据、新建唯一xiutu_test_*库并upgrade head后执行：

```powershell
uv run --frozen python -B scripts/demo_documents.py
```

依次上传合成Markdown/文本PDF/扫描PDF，经真实HTTP/SSE等待，显示chunk定位，读取原文件。对正常解析的合成材料输入yes记录一次演示人审；它不是用户对真实材料的专业审核。实测自动演示仅加--demo-approve-synthetic，见demo.txt；临时目录C:\Users\ADMINI~1\AppData\Local\Temp\xiutu-wp04-demo-0qjfhz4l保留合成文件、结果与日志。

## 基准、范围和保护

工作根E:\Work\xiutu-v5；main，无HEAD。开始核对WP-03接受后文件与其审核/结束保护声明，1047项基准见evidence/wp-04/baseline.json。HEAD缺失不影响SHA256与index固定。开始index SHA256：c451d6e78b8f29fc818002923a19fb1a888139ced20679ad545f75e9692a9ec6。旧项目63项、0001—0003、db_target、历史报告/证据和WP-00—03接受记录开始/结束一致；结束详见protection-final.json。没有提交/推送/暂存操作，不修改旧项目。

- 新增0004_documents：资料owner（遗留NULL拒绝访问）、不可变版本metadata/当前run、解析记录、chunk locator/token计数、document_reviews历史。旧迁移不改，health预期0004_documents；没有active_index_id。
- 新增domain/documents、infrastructure/storage/upload/ingest_state、services/document_service/ingest、retrieval/parsers/markdown/pdf、retrieval/chunker/tokenization及本地词表；扩展job_store/worker/run_service以原子发布和同步终止状态。
- 新增api/documents与实际响应模型/OpenAPI；扩展main/settings。新增合成fixtures、单元/真实HTTP集成测试、demo_documents。README、接口、契约、测试说明、兼容矩阵和状态同步。
- 所有新增/变更文件的前后哈希见change-manifest.json，最终交付清单见delivery-hashes.json。实际导入当前backend/app，由versions.txt记录。

## 关键实现与衔接

上传使用python-multipart低层流式回调：实际文件25MiB（可配）、multipart额外64KiB、metadata16KiB、header8KiB、两part。超限在继续写片段前拒绝，不先完整spool、不只依赖Content-Length。扩展名/UTF-8或PDF结构校验，拒绝损坏/加密；不访问外部资源。服务端UUID独占文件，存储路径及祖先拒绝reparse/旧项目/越界，fsync后才事务创建version+run+job+queued事件。

同文档行锁序列化hash复用；同hash同metadata不重复任务/chunk、不改审核；同hash异metadata409，新内容新版本，不跨owner/文档复用。失败后仅清理本次UUID且确认数据库无引用；不确定提交时保留候选孤儿。硬中断可能留下孤儿，不声称跨介质原子事务或生产恢复。

解析在业务事务外；有效worker/token/租约、当前run和未取消检查之后，同一finish事务写全部chunk、version摘要和成功状态/事件。cancel_requested优先；queued取消、失败、回收耗尽、显式retry同步version，不留下run终止而parsing的正常路径。新worker仍使用WP-03专用advisory锁与独立心跳，三次总预算不变。

cl100k_base固定BPE词表SHA256=223921b76ee99bde995b7ff738513eef100fb51d18c93597a113bcffe865b2a7，运行时不下载；默认600/900/80，保存parser/chunker/tokenizer版本。普通表格重复表头；巨大表头源片段完整保存并通过header上下文引用；超长行/段落不丢字符。PDF页码与缺项真实记录，但复杂版式未校验。全部输出是解析审阅材料，不能当正式检索候选。

## 本轮真实环境、命令与结果

复用已确认xiutu-v5/postgres容器（Docker29.4.0、Desktop4.69.0、127.0.0.1:5433，digest sha256:00ba258a66dac104fd5171074a0084462a64a1369d8513f3d0a634e2f24d15bc）。Windows一次Get-NetTCPConnection未返回对应监听项；以Docker实际映射/标签及真实PG连接交叉核对，未据此停止服务或接管端口。新库xiutu_test_wp04_b5946ac3cb7945c59dcdde00，PG16.14/vector0.8.2；迁移集成测试另建自身唯一库，均保留。只清理本轮probe schema和自己创建的子进程，未删除既有库/卷。

新增依赖由uv add解析uv.lock，再uv export --frozen --no-dev --no-emit-project --format requirements-txt导出requirements。实装pypdf6.19.0、markdown-it-py4.2.0、python-multipart0.0.32、tiktoken0.14.0。frozen同步、uv pip check均退出0，重新从锁导出与requirements逐有效行/哈希一致；没有第二份手工依赖真相。未重建两套venv，未改前端/重复前端构建。

命令cwd均E:\Work\xiutu-v5；每次真实命令、起止时间、退出码与原始输出在同名.json/.txt，JUnit使用正斜杠独立路径。run_command.py仅静默加载本项目受保护配置并脱敏；不读取旧.env、不打印连接串。

| 运行 | 命令要点 | 退出/实际结果 |
| --- | --- | --- |
| migration | python -B -m alembic upgrade head（本轮新库） | 0；0004_documents |
| parser-tests | pytest tests/unit/test_documents.py | 0；12 passed，无fail/error/skip |
| integration-first | pytest 新资料集成文件（当时名test_documents.py） | 0；8 passed |
| integration-additional | 同文件补真实SQL入队/发布故障 | 0；10 passed |
| full | pwsh -NoProfile -File scripts/test.ps1 | 2；收集时两个新测试文件同模块名，1 error，未执行全套；原输出/XML保留 |
| full-after-collection-fix | 同完整发布入口；将新集成文件改名test_document_ingest.py | 1；168 passed、1 failed、0 errors/skips、1既有警告；失败是既有SSE心跳/认证过期ReadTimeout |
| sse-targeted | 原失败用例单独复现 | 0；1 passed，约16.98秒认证过期关闭 |
| final-targeted | 原SSE两用例，-k sse | 0；2 passed、22 deselected；约17.16秒过期关闭，重连/注销/越权通过；不计作资料用例复跑 |
| review-gate-targeted | 明确指定资料版本/审核与上传/owner两用例 | 0；2 passed，新增rejected/跨owner审核断言通过 |
| demo | python -B scripts/demo_documents.py --demo-approve-synthetic | 0；MD/文本PDF成功，扫描needs_ocr，approved不等于indexed |
| frozen/dependency-check/final-lint | uv sync --frozen / uv pip check / ruff check本包文件 | 均0 |

**完整入口没有取得一次零失败：不将168+定点结果改写为“169 passed全量通过”。** 单项及随后SSE组合复跑未修改SSE实现/断言/超时，均通过，首次读取超时未再次复现、根因未确认。保留失败与定点证据，交审核者评估；不能称为已定位并修复。唯一已知警告仍是Starlette/AnyIO BlockingPortal弃用。初期lint的导入/格式问题已修正，最终final-lint.txt通过。

## D207—D209自测证据（非审核结论）

| 项 | 已实际验证 |
| --- | --- |
| D207 版本/上传 | 同key原响应重放与异请求409；同hash复用且审核状态不重置；新版本旧原文仍可读；两个HTTP请求被同一文档行锁同时阻塞后放行，仅一个version/job；超限/伪格式/路径/owner拒绝；SQL回滚候选文件清理 |
| D208 解析 | 真实Markdown长表/Unicode/超长段落覆盖全部源字符、token上限/hash；文本PDF逐页、真实image XObject扫描PDF及混合页；损坏/加密拒绝；独立worker取消/过期锁/旧token/进程死亡恢复/耗尽；第二chunk触发真实SQL异常时整个发布回滚，恢复只发布一次 |
| D209 人审 | 解析后pending不自动approved；rejected不进入正式可用，重复上传不覆盖；synthetic/unknown批准仍formal_usable=false；needs_ocr拒绝批准；同key历史只记一次；跨owner读取/审核404 |

受影响WP-02事务/认证/幂等/约束与WP-01目标门禁、健康、真实vector、跨进程checkpoint、MCP往返/断连在完整入口实跑；迁移测试0004→0003→0004及原升降级保留vector/外部sentinel。没有把探针推导成正式检索、生产恢复或维修效果。

## 必须关注与非阻断待办

未发现已定位的WP-04核心失败；**一次完整回归SSE超时仍未查明根因**，虽两轮定点通过，审核应保留此运行可靠性风险，不将其静默消除。当前提交审核，不替用户决定接受。

非阻断待办：大文件/复杂PDF的进程级资源隔离和性能优化、上传时长/并发配额、监控与孤儿文件巡检；不是本包已实现的生产保障。PDF抽取顺序不保证复杂版式，含图页保守缺项；巨大表头以完整来源/上下文引用而非无限重复。存储目录必须仅运行用户可写，当前路径检查不抵御本机特权用户并发更换目录。全局清理平台/真实资料页面留后续。

E10继续NOT_VERIFIED，模型/范围/预算另行授权，最迟WP-09。真实资料门槛继续NOT_MET，来源许可、精确车型/发动机、规格、电路、拆装/复核章节及缺图最迟WP-10/真实效果验收前补齐。本次没有私人手册或真实语料验证，不宣称维修效果。WP-05—17 NOT_STARTED。
