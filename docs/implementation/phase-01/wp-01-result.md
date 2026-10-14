# WP-01 执行结果

- 工作包：仅 WP-01；记录时间 2026-09-18T02:25:47.814139+08:00。
- **包状态：BLOCKED**。已实现部分供独立审核；核心真实数据库/图恢复未通过，不能写成本包全部 IMPLEMENTED_NOT_ACCEPTED 或验收通过。
- 新项目 `E:\Work\xiutu-v5`；旧项目 `E:\Work\v4-double`。新仓库 main，无 HEAD；原暂存区不变，新增交付与修改未暂存；未提交、未推送。
- WP-00：2026-09-18 已按用户明确指令记录 ACCEPTED，依据原 `wp-00-review-r1.md`；见 `wp-00-acceptance.md`。接受前 32 文件、review 与 index SHA256 一致，证据 `evidence/wp-01/acceptance-baseline.json`。未改原 result/review 结论。

## 1. 读取依据与范围

已完整阅读旧项目 `docs/参考/修途项目详细实施方案-Codex执行指南.md`、`00-阶段总表与使用方法.md`、`P1/01-第一阶段实施说明.md`、`P1/02-第一阶段验收清单.md`，以及当前 STATUS、WP-00 result/review。新项目及其上级未发现适用 AGENTS.md。

在实施前已向用户列明范围、文件组、前置环境及顺序：锁定安装 → 离线/health → 真 PG/vector/跨进程 → 真 MCP → 前端 → 第二环境。实际因 Docker 启动失败，先完成独立项并保留核心阻塞。未实施生产诊断树、Agent、正式业务表、报告、完整工作台或 WP-02。

## 2. 实际交付

- `pyproject.toml`、`.python-version`、`uv.lock`、`requirements.txt`、`requirements-dev.txt`：Python3.12，项目 xiutu，包路径 backend/app；requirements 由锁导出。
- `backend/app/config.py`：模式、路径与 PostgreSQL URI 校验；SecretStr 隐藏配置，拒绝旧项目 DATA_PATH；不自动读取旧 .env。
- `backend/app/main.py`、`infrastructure/db.py`：create_app、live、ready；连接池生命周期；就绪检查 SELECT1、vector 扩展、0001_environment 迁移版本。无 DB 时 503；从不调用 LLM。
- `alembic.ini`、`migrations/env.py`、`versions/0001_environment.py`：独立环境迁移，仅 vector + alembic_version；限定 loopback:5433/xiutu_dev 或 xiutu_test_*。真实迁移未运行成功。WP-02 必须使用新 revision，不覆盖本文件。
- `deploy/compose.yaml`：独立 xiutu-v5 project、5433 本地端口、命名 volume、pg_isready；密码只由本地环境传入。镜像版本标签已指定，实际 digest/启动未验证。
- `scripts/bootstrap.ps1`、`test.ps1`：固定项目根、拒绝未知环境目录；测试使用唯一临时路径和显式测试库，无旧/开发库回退。
- `scripts/probes/`、`tests/contract`、`tests/probes`：技术 echo、合成向量、健康/配置/模型离线契约、跨进程 checkpoint 探针。`prepare_database.py` 只 CREATE 新测试库，冲突即失败。
- `tests/live/test_deepseek_probe.py`：显式未授权 skipped，不包含可执行付费探针。
- `frontend/`：React/TS/Vite 最小“基础环境验证”页面，无正式业务按钮；package-lock 锁定。
- README、CHANGELOG、STATUS、tests/README、`docs/architecture/dependency-matrix.md`、本结果及本次证据。

完整文件及 SHA256 见 `evidence/wp-01/delivery-hashes.json`。本文件是执行结果，不是独立 review，不生成本包 REVIEW_PASS/ACCEPTED。

## 3. 实际命令与结果

以下命令工作目录均为新项目。完整参数、时间、退出码在 `evidence/wp-01/verification-commands.json`、`verified-test-commands.json`；输出路径相对 `evidence/wp-01/`。执行中未复用历史统计。

| 命令/检查 | 退出码 | 实际结果/证据 |
| --- | --- | --- |
| uv lock | 0 | 解析 84 packages，生成 uv.lock |
| uv sync --frozen --group dev | 0 | 新 .venv；uv-sync.txt |
| uv export --frozen --no-dev --no-emit-project --output-file requirements.txt | 0 | uv-export-runtime.txt |
| uv export --frozen --group dev --no-emit-project --output-file requirements-dev.txt | 0 | uv-export-dev.txt |
| npm.cmd --prefix frontend install --package-lock-only | 0 | npm-lock.txt |
| npm.cmd --prefix frontend ci | 0 | npm-ci.txt，21 packages，npm 当次报告 0 vulnerabilities |
| npm.cmd --prefix frontend run typecheck / run build | 0 / 0 | frontend-typecheck.txt / frontend-build.txt，构建 27 modules |
| uv pip check --python .venv/Scripts/python.exe | 0 | dependency-check.txt |
| .venv/Scripts/python.exe scripts/probes/http_smoke.py <新日志路径> | 0 | http-smoke.txt；独立 Uvicorn PID33300，8020，live200/ready503；finally 仅结束本次子进程 |
| .venv/Scripts/python.exe -m pytest tests/contract tests/probes/test_mcp_roundtrip.py tests/probes/test_pgvector_probe.py::test_database_down_health -q -s --basetemp .test-runs/verified-primary | 0 | verified-primary.txt/xml：22 passed，0 failed/errors/skipped，1 warning，9.33s |
| 设置 UV_PROJECT_ENVIRONMENT=.test-runs/wp01-reproduction/venv 后 uv sync --frozen --group dev | 0 | second-sync.txt，原先不存在的第二环境，未复制旧环境 |
| uv pip check --python <第二环境 python> | 0 | second-check.txt；versions-primary.txt 与 versions-second.txt 同版本、不同 prefix |
| 第二环境 python 执行同一离线+MCP+不可用 DB 用例 | 0 | verified-second.txt/xml：22 passed，0 failed/errors/skipped，1 warning，9.42s |
| 第二环境 python scripts/probes/http_smoke.py <新日志路径> | 0 | second-http-smoke.txt，PID25968，live200/ready503 |
| 设置 TEST_DATABASE_URL 指向 loopback:5433/xiutu_test_wp01 后 python -m pytest tests/contract tests/probes -q -s | 1 | verified-full-blocked.txt/xml：22 passed，0 failed，3 errors，0 skipped，1 warning，16.37s；3 errors 均为真实 PostgreSQL 连接超时 |
| python -m pytest tests/live -q | 0 | live-not-authorized.txt：1 skipped，不是模型通过 |
| uv run --frozen ruff check <本包新增代码目录> | 0 | ruff-final.txt；未修改旧 WP-00 脚本 |
| git diff --check / git diff --cached --check | 0 / 0 | git-diff-check.txt / git-index-check.txt |
| docker version / docker desktop status | 1 / 1 | docker-blocker.json，Server 不可用 |

完整套件中 3 个错误：test_checkpoint_cross_process、test_real_vector_and_health、test_missing_migration_health。连接阶段失败，未执行向量断言、迁移成功路径或 checkpoint 写入/恢复，不得算作功能失败已被修复或功能通过。

MCP 使用新服务器进程和实际 HTTP SDK，协商协议 2025-11-25；probe_echo 的 inputSchema/outputSchema、输入及结构化输出都保存在最终测试日志。停掉本次服务器后，重新初始化产生 McpError/ConnectTimeout，主环境约 2.266 秒，断言上界 8 秒；没有以 REST TestClient 代替协议。

模型测试的 MockTransport 仅用于离线契约：实际加载 ChatDeepSeek、解析工具响应、携带对应 tool_call_id 回传工具结果，并验证无效结构和模拟超时。禁用真实 socket；所有消息都是合成测试输入，不是远程模型响应。没有读取/输出真实密钥，没有付费请求和 usage 成功记录。

## 4. 自测清单（不是独立审核）

| ID | 状态 | 证据及边界 |
| --- | --- | --- |
| E01 | PASS | uv.lock/package-lock + frozen/npm ci；requirements 由锁导出 |
| E02 | PASS | 新第二环境锁定安装、相同版本、22 passed、独立进程 health |
| E03 | PASS（清单要求的 live/故障分支） | 两环境真 HTTP live200、无 DB ready503；连接拒绝测试503；DB 真正就绪200仍随 E05 待验证 |
| E04 | PASS | health 无模型调用链；配置密钥仅报告 configured，verified 始终 false；离线网络断言 |
| E05 | NOT_VERIFIED | Docker 核心阻塞，真扩展版本/向量查询没有运行通过 |
| E06 | NOT_VERIFIED（部分已验证） | 4个非隔离 URL/缺 URL 拒绝用例通过；真实 probe schema 创建/清理受 DB 阻塞 |
| E07 | NOT_VERIFIED | 真实数据库连接失败，不能用 MemorySaver 或同进程测试替代 |
| E08 | PASS | 实际 MCP initialize/list/call，断连产生有界错误；仅技术工具 |
| E09 | PASS | 真实适配器离线 schema/解析/工具结果对应/超时；明确 MockTransport |
| E10 | NOT_VERIFIED | 未获付费授权，live 显式 skipped；最迟 WP-09 门槛前单独处理 |
| E11 | PASS | npm ci、typecheck、build 退出0 |
| E12 | PASS（记录一致性） | 兼容矩阵与锁/实装对应，数据库行明确 NOT_VERIFIED，不把 import 作为集成通过 |
| E13 | PASS | probes 与最小服务分开；无正式 MCP 工具、业务图/向量知识库 |
| E14 | PASS（本次检查范围） | 忽略规则及待交付文本扫描；secret-ignore-check.json；无私人库/图片/备份正文；模式扫描不保证发现所有未知格式秘密 |
| E15 | PASS（本次保护范围） | 63 个旧基准文件哈希未变；原8014 PID5328持续监听；没有打开或写旧业务库，不要求运行中库字节/行数不变 |
| E16 | PASS | 没有 WP-02 业务表、诊断实现、报告或完整工作台；WP-02—17 NOT_STARTED |

## 5. 保留的失败与修正记录

1. offline-first：1 failed / 15 passed / 3 warnings。健康测试在创建 TestClient 事件循环前拦截所有 connect，误拦 Windows socketpair。改到进入 TestClient 后安装网络禁止断言，没有跳过用例或放宽健康断言。offline-second：16 passed / 1 warning。随后增补隔离 URL 与模型工具往返/超时测试。
2. 初次 ruff 有17项检查问题，保存 ruff-first.txt；本项目明确 lint 规则并修正导入、格式及异常类型，最终检查通过。
3. final-primary/final-second：各21 passed / 1 failed。收紧断连验证后仅接受 ConnectError，但 Windows 实际返回 ConnectTimeout；两个都是允许的断连/超时反例。修正为限定接受两种连接异常、仍要求错误发生且小于8秒。最终 verified-* 日志保存成功，失败日志未覆盖。
4. uv 硬链接跨盘回退复制警告保留；第二环境显式 UV_LINK_MODE=copy。Starlette/AnyIO 弃用警告仍存在，两个最终环境各1 warning，未屏蔽。

## 6. 核心阻塞与未完成项

**BLOCKER-WP01-001：Docker Desktop 引擎不可用。** 已尝试启动现有 Docker Desktop 和 `docker desktop start`，客户端29.4.0存在，desktop-linux 命名管道不存在。后台日志明确 `initializing Inference manager ... dockerInference ... The file cannot be accessed by the system`，保存脱敏原因于 docker-blocker.json。本次未改 Docker 全局设置、套接字文件、WSL/虚拟化设置，未安装额外数据库替代它。已结束本次一直等待的 Docker CLI start 子进程 PID30960，未停止旧服务。

需环境维护者处理引擎后，按 README 在专用 project/volume/测试库执行真实迁移、vector 查询、ready200、schema 清理和两个独立进程 checkpoint 恢复，保存新的证据，不覆盖本次失败。补录 PostgreSQL/extension 实际版本和 image digest。此核心阻塞不能通过 Mock 消除；本包不能宣布全部完成。

**E10 未授权：** 未调用付费模型。后续若需 live，先说明具体模型、调用次数/内容及预算，再取得用户确认。当前不是“密钥已配置就等于真实通过”。

**资料门槛仍 NOT_MET：** WP-00 的来源/许可/车型和发动机代码适配、正式规格/电路针脚/拆装/复核章节、两张相对缺图仍未解决。备份许可不是公开分发许可；合成教学内容不能作为正式维修证据。真实资料最迟在 WP-10/真实效果验收前补齐，本次没有把缺项标为已解决。

## 7. 用户亲自验证与停止点

1. 阅读 STATUS、wp-00-acceptance.md、本结果及 dependency-matrix.md；比对 verified-*.txt/xml 与锁文件。
2. 按 README 在新目录运行 bootstrap、`scripts/test.ps1 -OfflineOnly`、前端类型检查与构建；每次脚本建立新的 UUID 测试目录，不覆盖证据。
3. 启动新 Uvicorn 8020，访问 live200 与 ready503；配置好的真实隔离数据库具备扩展及迁移后才应得到 ready200。不能把503包装成“系统已完全就绪”。
4. Docker 修复后按 README 新建专用测试库运行完整测试；审核者需重新独立运行 E05/E06/E07 并检查跨进程 PID、workflow ID、状态和执行次数。本次尚无这些成功证据。

本包停止在 **BLOCKED / 等待独立审核与环境处理**。未创建 WP-01 REVIEW_PASS 或 ACCEPTED；不自动开始 WP-02，也不继续发起付费模型探针。
