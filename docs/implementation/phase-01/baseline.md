# 旧版基线

日期：2026-09-18（本地 UTC+8）。旧根 E:\Work\v4-double；新根 E:\Work\xiutu-v5。新根开始时不存在，创建前明确核对。旧根 git rev-parse/status 均返回 not a git repository；没有分支、HEAD 或 Git 变更记录，不虚构干净状态。以 evidence/legacy-hashes-before.json 和 after.json 固定 53 个源码、静态资源、脚本、依赖/模板与文档；不含 .env、环境、业务数据或缓存。旧根嵌套 AGENTS 搜索及 E:\、E:\Work\ 父链均无适用文件；首次未排除旧 .test-runs 的扫描遇到 ACL 拒绝，排除缓存后扫描完成。

## 入口、依赖与运行

- 解释器：E:\Work\v4-double\.venv\Scripts\python.exe，Python 3.12.10。
- app/main.py 创建 app，app/application.py:create_app 注册路由/生命周期。首页实际返回 app/static/workbench.html，加载 workbench.js、workbench.css、final-aside.css、intake-layout.css。其他静态文件不能据旧说明随意删除。
- requirements.txt / requirements-dev.txt / requirements-lock.txt 为旧依赖声明/历史锁；本包没有安装或修改依赖。锁是否可在干净环境重建不在本包宣称范围。
- app/diagnosis.py：动态诊断和固定演示树；research.py：模型/网络；catalog.py：Markdown/TF-IDF/适配；repository.py：SQLite/revision/事件；models.py：数据校验；workflow.py/planner.py：旧流程。
- 原运行命令：在旧根执行 `.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8014`，或 scripts/start.ps1。
- 实际配置解析：data/diagnostic.db、data/repair_docs、data/attachments、logs，绝对路径见 preflight.json。配置可加载根 .env 和 .venv/.env，本包只输出路径与 DeepSeek configured 布尔值。configured=true，真实调用 NOT_VERIFIED，未付费探测。
- E盘开始可用 48,473,112,576 bytes。端口 127.0.0.1:8014 活跃 PID5328，进程解释器 E:\Work\python\python.exe；父 PID13004 为旧项目 .venv\Scripts\python.exe，启动参数均为 uvicorn app.main:app。证据 legacy-service.json；父进程核对见结果。未停止/重启服务；没有读取业务会话内容。

## 本次测试

先完整检查两份测试：测试 fixtures 显式注入 tmp_path 的 DB/docs/images/logs；资料只读复制到 tmp_path；模型 generate/HTTP 和 DDGS 使用替身，Settings 默认无密钥。新增 WP-00 harness 再阻断 socket 网络与测试目录外 SQLite，禁写 bytecode，禁 pytest cache/plugin autoload；仅允许 Windows asyncio 内部 socketpair，不允许一般回环 HTTP 请求。

本地 01:06:43—01:06:48：**67 passed, 0 failed, 0 errors, 0 skipped, 1 warning，退出码0**。警告为 Starlette 使用 AnyIO BlockingPortal 弃用别名。测试目录 E:\Work\xiutu-v5\.test-runs\wp00-20260918-02；完整日志/JUnit/时间与命令见 evidence/legacy-*。

首次 01:06:00 运行出现 17 passed / 50 setup errors / 7 warnings：新增 harness 误拦 Windows asyncio 的 socket.socketpair。原因是执行隔离器而非旧业务代码。保留 attempt-01 的全量输出与哈希，只调整新 harness 的内部 socketpair 白名单后，用全新目录重跑。两次旧项目53文件哈希均一致；没有为了通过基线修改旧代码。

## 备份恢复

最终有效备份：E:\Work\xiutu-backups\phase-01-20260918-0115。
独立恢复：E:\Work\xiutu-backups\restore-20260918-0115。

SQLite read-only 源连接调用 Connection.backup；目标 integrity_check=ok。资料复制逐文件 source before/after/destination SHA256 一致，结束再次检查文件集合与哈希。manifest 记录源目录、相对路径、大小、SHA256、UTC时间、脚本版本与哈希。恢复前校验全部哈希并拒绝已有目录，恢复后 SQLite schema/完整性/表行数与备份一致，全部8文件哈希一致。

| 表 | 备份行数 | 恢复行数 |
| --- | --- | --- |
| attachments | 0 | 0 |
| audit_events | 741 | 741 |
| session_state | 42 | 42 |
| sessions | 88 | 88 |
| sqlite_sequence | 1 | 1 |

配置附件目录为空。SQLite 是事务一致快照，资料是逐文件稳定副本；没有声称数据库与文件为跨资源原子快照。活跃旧服务可能继续写库，因此不要求备份后原库行数恒定。SRC-001 两张相对图缺失；SRC-002 两张外部图已获用户授权，备份到 supplemental 并全部恢复校验通过，详见 data-readiness。备份覆盖实际配置数据及清点的5项补充资产，没有备份 .venv/.env，也没有把业务库迁入新项目。原始绝对链接不被重写；manifest 的 source 到 relative_path 提供恢复映射。

## 可复用清单（尚未迁移）

车辆字段及 engine_family/code 分离、Pydantic extra 校验、revision 冲突保护、脱敏与风险停止思路、API 回归场景可供后续重设计。diagnosis/research/catalog/Repository 均需按新分层重写，固定树只作为隔离回归参考，旧静态页面不迁移。新源码迁移数量为零。

## 交付前复核补记

测试运行期间53文件哈希完全一致；交付前再次扫描发现旧计划文档并行变化，非本任务写入。变更：docs/参考/00-阶段总表与使用方法.md；新增：docs/参考/P2/01-第二阶段实施说明.md, docs/参考/P2/02-第二阶段验收清单.md, docs/参考/P3/01-第三阶段实施说明.md, docs/参考/P3/02-第三阶段验收清单.md, docs/参考/P4/01-第四阶段实施说明.md, docs/参考/P4/02-第四阶段验收清单.md, docs/参考/P5/01-第五阶段实施说明.md, docs/参考/P5/02-第五阶段验收清单.md, docs/参考/P6/01-第六阶段实施说明.md, docs/参考/P6/02-第六阶段验收清单.md。已重读更新后的阶段总表，WP-00边界及状态规则没有变化，不自动执行新增计划。业务源码/原脚本/原测试/依赖模板未变化。详见 evidence/legacy-final-inventory.json。

备份脚本实测补充：含补充资产的合成往返、拒绝已有备份/恢复目标、拒绝篡改备份均通过；当前真实恢复8文件及脚本SHA256再次匹配。记录见 evidence/wp00-script-checks.json。
