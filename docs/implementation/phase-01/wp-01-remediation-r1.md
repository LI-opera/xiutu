# WP-01 r1 整改与真实数据库补测

记录时间：2026-09-18T03:17:19.878735+08:00。范围仅WP-01，针对wp-01-review-r1.md的ISSUE-001—005及ENV-001。

**状态：IMPLEMENTED_NOT_ACCEPTED，等待独立r2复核与用户接受。** 本轮核心整改和真实验证完成；不是独立审核通过结论。E10仍NOT_VERIFIED，资料门槛仍NOT_MET。未开始WP-02，未提交/推送或调整暂存区。

## 1. 读取、基准和授权范围

已检查项目及上级适用AGENTS.md，未发现；阅读STATUS、原WP-01 result/r1 review、WP-00接受记录、兼容矩阵、P1实施说明/验收清单及总指南WP-01和相关全局契约。开始实现前列明修改范围与先隔离反例、后真实数据库的顺序。

新项目 `E:\Work\xiutu-v5`；旧项目 `E:\Work\v4-double`。main无HEAD，HEAD核对退出128属于空仓库状态。32项原暂存保留；已有未暂存/未跟踪交付均记录于 `evidence/wp-01-remediation-r1/status.txt`、cached.txt、unstaged.txt。r1所核对157文件在整改开始前无差异；包含审核新增工件的203项开始哈希见baseline.json。

本轮所有新证据位于 `evidence/wp-01-remediation-r1/`（以下文件名均相对此目录），原result、review、接受记录、delivery-hashes和历史证据未覆盖。原Docker历史失败保留；本次以当前Server实测为准，没有再次修复Docker。

## 2. 逐ISSUE整改

| ISSUE | 修改文件 | 修复与结果 | 证据/复核入口 |
| --- | --- | --- | --- |
| 001 | backend/app/infrastructure/db_target.py；migrations/env.py | 共享validate_target；只接受显式loopback:5433、明确用户及允许的库名，query仅connect_timeout；重建SQLAlchemy URL和psycopg kwargs，拒绝覆盖host/port/dbname。原绕过在创建引擎前失败 | tests/contract/test_database_boundary.py；boundary.txt/xml；final-primary.txt |
| 002 | 同一db_target.py；db.py；tests/conftest.py；graph_worker.py；prepare_database.py；test_pgvector_probe.py | 禁止hostaddr/service/query扩展、多主机、缺参数、不合法库名/端口和所有非空PG*环境项；最终固定host+hostaddr=127.0.0.1、port5433、显式凭据和passfile=os.devnull。健康连接池、schema连接、图和建库全部复用同一策略 | 35个无连接回归通过；无connect/create_engine调用反例；真实DB范围和清理记录 |
| 003 | scripts/probes/http_smoke.py；tests/contract/test_http_startup.py | 总deadline内只重试ConnectError/ConnectTimeout；保留退出检测、最终失败及日志；占用端口在Popen前拒绝；只结束自身创建的子进程 | startup.txt/xml：延迟2秒后真实就绪、永不监听限时失败、提前退出、端口占用不启动且原socket仍可接入；主/第二环境HTTP实测 |
| 004 | .node-version；frontend/scripts/check-node.mjs、check-node.test.mjs；frontend/package.json、package-lock.json；scripts/bootstrap.ps1 | Node24.14.0统一声明；bootstrap及npm preinstall/pretypecheck/prebuild/predev实际检查当前process.versions.node，错误明确，不安装/切换全局运行时 | node-gate.txt、second-node-gate.txt各2通过；模拟18.0.0被拒绝；两套npm ci/typecheck/build通过 |
| 005 | docs/implementation/STATUS.md、README及当前矩阵/CHANGELOG | 区分初始53项与扩展63项，链接原清单；差集为P2—P6十份文档，阶段总表历史并行变化仍保留；本轮63项均未变 | protection-final.json，含完整当前63项哈希及集合差 |

数据库策略区别：test仅允许`xiutu_test_[a-z0-9_]`且后缀1—40字符；建库入口development仅xiutu_dev；环境迁移和health允许xiutu_dev或上述测试库。输入的DSN不会原样传驱动。schema名只接受受限wp01_*标识，不能通过options注入其他路径。DB目标白名单是WP-01本地隔离范围，不声称支持任意生产部署。

连接入口已检索复核：迁移create_engine、健康ConnectionPool、fixture、pgvector测试、图worker、建库脚本均使用validate_target与重建参数。测试fixture用RedactedURL避免pytest参数repr泄露凭据；本次原始输出在写证据时另作已知本地随机密码精确脱敏。

门禁测试在任何本轮真实建库/迁移/数据库探针前完成：35 passed，0失败/错误/跳过。包括r1两个具体URL、PGHOSTADDR/PGSERVICE/PGSERVICEFILE/PGSYSCONFDIR/PGHOST/PGPORT/PGDATABASE/PGUSER/PGOPTIONS/PGPASSFILE、多主机、缺host/port/user/db、越界库/端口、未知query和合法loopback；断言最终SQLAlchemy参数与psycopg参数一致。没有通过放宽门禁让真实测试通过。

## 3. ENV-001当前状态与资源归属

当前docker version与docker info返回Server29.4.0，Docker Desktop4.69.0，context desktop-linux；Compose5.1.1。用户已在r1后自行修复，本轮没有重装、改全局设置、删除socket/卷或调整WSL/虚拟化。当前证据为docker-version.txt、docker-info.txt、docker-context.txt，与历史docker-blocker.json分开。

首次启动前核对：本项目容器、卷、网络查询为空（project-containers.txt、project-volume.txt、project-network.txt），5433可独占绑定；其他项目资源仅查看，没有接管或停止。之后仅启动xiutu-v5/postgres。

- 专用容器：xiutu-v5-postgres-1；卷：xiutu-v5_wp01_pgdata；绑定127.0.0.1:5433。
- 镜像：pgvector/pgvector:0.8.2-pg16-bookworm。
- 实际并已固定digest：`sha256:00ba258a66dac104fd5171074a0084462a64a1369d8513f3d0a634e2f24d15bc`。
- PostgreSQL：`16.14 (Debian 16.14-1.pgdg12+1)`；vector扩展0.8.2；Python pgvector适配包0.5.0，二者不混淆。
- 资源标签、真实端口、镜像digest见image-and-resource.json；compose.yaml已固定tag@digest。只启动postgres，未建立WP-02业务表。
- 本次随机凭据仅在被忽略的`.local-data/wp01-postgres.json`保存，未读取旧.env、未输出密码或完整敏感连接串。容器和两个测试库保留供r2复核，不自动删除数据/卷。

## 4. 真实数据库与图恢复结果

第一新测试库：`xiutu_test_4ed3b06590c84427904aa08eebf722a2`。第二环境使用另一新测试库：`xiutu_test_adc3da06af214fe4b8b037979e02fb6f`。均以UUID命名，新建不覆盖。

迁移前实测：vector不存在、public无表、ready503；迁移后revision为0001_environment、vector0.8.2、ready200。迁移只建立环境扩展和alembic_version。证据database-before-migration.json、migration-test.txt、database-after-tests.json。

合成向量三行排序为[1,2,3]、最近距离0，测试通过；不代表embedding或维修语义效果。fixture在schema创建前后记录全体schema清单，finally只删除自身UUID schema并断言其他清单相同；两个库最终均无wp01_* schema，public仅alembic_version，见final-database-inventory.json。

图使用真实PostgresSaver，无MemorySaver：

| 环境 | workflow_id | A PID / 状态 | B PID / 状态 | 错误ID |
| --- | --- | --- | --- | --- |
| 主环境 | wp01-f0fb75f09183421ba9c6caf4126c0385 | 30180；count1、next=pause；正常退出0 | 36084；count1、approval=approved、next为空；退出0 | 退出4，unknown_workflow |
| 第二环境 | wp01-3837f1b743ac4d94b89e99b8b8cb406e | 25036；count1、next=pause；正常退出0 | 31240；count1、approval=approved、next为空；退出0 | 退出4，unknown_workflow |

A完成后才以新的Python子进程B读取相同workflow；计数未重复增加。详细状态、ID、进程与schema清理均在final-primary.txt、second-full.txt。该证据不扩展为生产事务/fencing、崩溃恰好一次或正式业务图完成。

负例：缺迁移和错误迁移版本ready=False通过；服务启动前无5433监听时，真实连接故障ready503通过（startup.txt）。完整套件再次运行同一无效凭据目标时，服务已在线，验证的是数据库连接被拒后的503，不能把该后续结果称为当时没有Server。无DATABASE_URL的真实HTTP503也分别验证。

拒绝覆盖：正式test_prepare_database_refuses_existing使用xiutu_dev入口尝试CREATE已存在测试库，PostgreSQL返回DuplicateDatabase；既有alembic_version仍存在。额外原始异常见refuse-existing-db-actual.txt，预期退出1。没有执行DROP DATABASE。

## 5. 实际命令、退出码与统计

工作目录为新项目；第二前端在新临时副本中运行。environment-commands.json、real-commands.json、final-verification-commands.json记录实际参数、时间、退出码；辅助pytest时间可从对应JUnit读取，不把文件mtime当命令开始时间。所有测试使用本轮新目录，未复用历史basetemp或覆盖原evidence。

| 命令/步骤 | 退出码 | 实际结果 |
| --- | --- | --- |
| python -B -m pytest tests/contract/test_database_boundary.py -q -p no:cacheprovider --basetemp .test-runs/remediation-r1-boundary | 0 | 35 passed / 0 failed/errors/skipped；boundary.txt/xml |
| pytest tests/contract/test_http_startup.py tests/probes/test_pgvector_probe.py::test_database_down_health（启动DB前） | 0 | 5 passed / 0 failed/errors/skipped / 1 warning，7.78s；startup.txt/xml |
| docker version / docker info / context | 0 | 当前Server可用，未修复Docker |
| docker compose -p xiutu-v5 -f deploy/compose.yaml up -d --wait --wait-timeout 90 postgres | 0 | 新专用服务健康；compose-up.txt |
| python scripts/probes/prepare_database.py --name <新UUID库> | 0 | 两个环境各创建一个新库；create-test-db.txt、second-create-db.txt |
| python -m alembic upgrade head（目标测试库） | 0 | 两个环境均真实迁移；migration-test.txt、second-migration.txt |
| 首轮完整 tests/contract tests/probes | 0 | 65 passed / 0 failed/errors/skipped / 1 warning，22.31s；full-tests.txt/xml |
| 主环境最终完整 tests/contract tests/probes -q -s -p no:cacheprovider | 0 | **66 passed / 0 failed/errors/skipped / 1 warning，22.92s**；final-primary.txt/xml |
| 新UV_PROJECT_ENVIRONMENT下 uv sync --frozen --group dev | 0 | second-frozen.txt，全新第二环境 |
| uv pip check --python <第二环境> | 0 | second-pip-check.txt |
| 第二环境完整 tests/contract tests/probes | 0 | **66 passed / 0 failed/errors/skipped / 1 warning，30.26s**；second-full.txt/xml |
| 主/第二环境真实HTTP带已迁移DB | 0 / 0 | live200/ready200；http-ready200.txt、second-http-ready.txt |
| 主/第二环境原http_smoke入口（无DB配置） | 0 / 0 | live200/ready503；http-no-db.txt、second-http-no-db.txt |
| 正确开发入口创建重复库（补充原始负例） | 1（预期） | DuplicateDatabase，原库保留；refuse-existing-db-command.json |
| npm.cmd --prefix frontend install --package-lock-only | 0 | 更新engines/脚本对应锁元数据，依赖版本未漂移；npm-lock.txt |
| 主/全新前端副本 npm ci、run typecheck、run build | 均0 | npm-ci/typecheck/build.txt与second-*；每次实际触发Node前置检查 |
| 主/副本 npm run test:runtime | 0 / 0 | 各2 passed，0 failed/skipped；指定版本通过、模拟18.0.0拒绝 |
| uv run --frozen ruff check；uv lock --check | 0 / 0 | ruff-final.txt、lock-check.txt |
| git diff --check / git diff --cached --check | 0 / 0 | diff-check.txt、cached-check.txt |

第二环境路径：`E:\Work\xiutu-v5\.test-runs\remediation-reproduction-fb15dad1da6a43b4887a1edbd3c2a433\venv`；安装相同uv.lock，没有复制旧.venv或旧数据。primary-versions.txt与second-versions.txt记录不同sys.prefix和相同核心版本。前端另复制源码/锁/.node-version到新临时目录安装构建，未复用主node_modules。

MCP在两环境完整套件继续实际初始化/list/call/断连；DeepSeek仅离线MockTransport与schema/ID/超时契约。没有执行任何付费模型请求；E10不计入上述核心通过统计。

## 6. 本轮发现、限制和保留记录

- 第一次补充“拒绝重复库”调用沿用了测试库DATABASE_URL，先被development范围门禁拒绝（refuse-existing-db.txt，退出1）。这是正确的入口拒绝，但不能充当DuplicateDatabase证据；随后增加正式回归并用正确开发入口取得真实DuplicateDatabase，原失败未覆盖。因此65项增加到最终66项，没有删除/跳过失败来凑通过。
- 首次真实PG/vector/图恢复未暴露额外业务实现需求；只增加错误迁移版本、schema清理核对及实际重复库拒绝测试，均属WP-01。
- 两环境均保留1条Starlette/AnyIO BlockingPortal弃用警告，未屏蔽第三方警告；不影响本轮断言通过。
- Node不支持版本为隔离参数模拟，用户全局Node未切换。HTTP负例测试的假进程/延迟服务仅验证探针等待行为；真实数据库、向量、跨进程和MCP没有用Mock代替。
- 初始53项与当前63项差集是10份阶段文档；历史阶段总表变化已记录，当前旧业务源码、测试、配置模板等63项哈希完全一致，见protection-final.json。没有读取/修改旧业务数据库，不要求活跃旧库字节恒定。

## 7. 当前检查状态与保护

执行者自测：E01/E02/E03/E04/E05/E06/E07/E08/E09/E11/E12/E13/E14/E15/E16的本包要求已完成对应验证，供r2独立复核；不自行作审核PASS结论。ENV-001当前Server可用且真实验证完成。E10=NOT_VERIFIED；资料门槛=NOT_MET。

Git index仍为`c451d6e78b8f29fc818002923a19fb1a888139ced20679ad545f75e9692a9ec6`。WP-00原审核SHA256仍为`842f085cbffd50dfb92177a7042597b52ff0b751203a341edc0e43227a694b9b`；接受记录及共157项历史报告/证据均未变。旧8014保持原进程，8020探针子进程已清理，5433仅本项目专用服务保留。保护详情和端口记录见protection-final.json、ports-final.json。

实际新生成数据库密码的精确匹配检查和通用秘密模式扫描均无交付命中；.local-data、.env、.venv、.test-runs、node_modules、dist均被忽略，见secret-scan.json。不会将私人凭据写入文档或Git。

## 8. 用户复核方法与停止点

README提供本机凭据的静默加载、新UUID测试库创建、环境迁移、完整test.ps1、前端命令与health访问步骤。复核者先读本记录与代码差异，再自行检查当前Docker/资源归属，在新的测试库和临时目录重跑；不要覆盖本轮证据。交付文件SHA256见delivery-hashes.json。

本轮只更新当前README、CHANGELOG、矩阵及STATUS，保留原result和r1审核作为历史。没有新增正式业务表、Agent、报告或工作台；没有改WP-00接受范围，也没有写WP-01 ACCEPTED/REVIEW_PASS。

**停止：交用户安排独立r2复核。** E10真实模型预算/授权与来源、许可、精确车型适配、正式规格/电路/拆装/复核章节和缺图事项仍未满足；私人备份授权不等于公开许可，合成内容不能作正式维修依据。不自动进入WP-02。
