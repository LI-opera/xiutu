# WP-01 独立复核 r2

**结论：REVIEW_PASS（限定 WP-01 核心技术范围）。建议用户在明确保留 E10 与资料缺项的前提下接受本包；本报告不是用户接受，也不是第一阶段无条件完成。**

审核日期：2026-09-18，Asia/Shanghai。ISSUE-001—005 均 RESOLVED，ENV-001 当前已解除。未发现必须现场整改的新问题。未修改实现、STATUS、接受记录或历史证据；未进入 WP-02。

## 1. 审核依据与固定基准

检查 E:\、E:\Work、项目根及项目内适用 AGENTS.md，未发现。阅读 STATUS、原 result、r1 review、remediation-r1、WP-00 acceptance、dependency-matrix、旧项目 P1 实施说明/验收清单，以及总指南 WP-01、全局边界、数据库、恢复、MCP/模型、脚本配置与交付契约。检查实际源码、测试、迁移、锁、脚本、前端及原始输出。

- 项目/Git 根：`E:\Work\xiutu-v5`；旧项目：`E:\Work\v4-double`。
- 分支 main；HEAD 检查退出128，确无首次提交。32个暂存文件，5个已有文件有未暂存修改，其余 WP-01 交付未跟踪。完整输入见 `evidence/wp-01-review-r2/status.txt`、cached.txt、unstaged.txt。
- 开始时间及逐文件 SHA256：`baseline-before.json`。整改 delivery-hashes.json 与当前无差异；额外固定清单自身，共281项。结束 `protection-after.json`：281项全部未变。新增内容仅本报告、r2证据及被忽略的唯一审核目录。
- Git index SHA256：`c451d6e78b8f29fc818002923a19fb1a888139ced20679ad545f75e9692a9ec6`，开始/结束一致。
- WP-00 原审核 SHA256：`842f085cbffd50dfb92177a7042597b52ff0b751203a341edc0e43227a694b9b`。
- WP-00 接受 SHA256：`c5af6d91211f295252633a4c5c64229f2368010255b1809ae06c6dc7b3c524db`。与整改 protection-final.json 声明一致，历史文件都包含在281项中，未覆盖原基准。
- Git 仅命令级 safe.directory；无 add/commit/reset/push。working/cached diff --check 均退出0。

本报告下文证据文件，除注明历史来源外，均相对于 `evidence/wp-01-review-r2/`。

## 2. 独立环境与实际执行

复制41项源码/脚本/锁/配置到 `.test-runs/wp01-review-r2-a203e777d1ed43cca9ac4ca5b15b3601/snapshot`，逐文件复制哈希见 snapshot-inputs.json。全新 venv 位于其同级 `venv`，前端在副本内安装/构建。未复制原 venv/node_modules/数据。测试关闭字节码与 pytest cache，使用首次创建的 boundary-temp/full-temp。

完整命令、cwd、开始/结束时间、退出码和输出文件见 commands.json；审核辅助脚本 independent-run.py、continue-run.py、supplement.py 保留。数据库凭据只在审核进程内从新项目忽略文件静默加载，通过子进程环境传递；命令日志不含完整敏感连接串。未读取旧 .env。

| 本轮独立执行 | 退出码 | 结果/原始证据 |
| --- | --- | --- |
| uv sync --frozen --group dev；uv pip check --python 审核解释器 | 0 / 0 | frozen-sync.txt、pip-check.txt；全新环境，83包依赖一致 |
| pytest tests/contract/test_database_boundary.py | 0 | boundary.txt/xml：35 passed，0失败/错误/跳过 |
| 完整 pytest tests/contract tests/probes -q -s -p no:cacheprovider，唯一 basetemp | 0 | full-tests.txt/xml：**66 passed，0 failed/errors/skipped，1 warning，31.51秒** |
| prepare_database.py --name 本轮唯一库 | 0 | create-database.txt；没有复用执行者两个库 |
| python -B -m alembic upgrade head | 0 | migration.txt；仅环境迁移 |
| 真 Uvicorn + 修复后的 run_smoke | 0（正常返回） | http-empty.json：200/503；http-ready.json：200/200；http-db-failure.json：200/503 |
| python -B scripts/probes/http_smoke.py 全新日志路径 | 0 | http-entry.txt、http-entry-server.txt；实际主入口200/503 |
| npm.cmd --prefix frontend ci / run typecheck / run build | 0 / 0 / 0 | npm-ci.txt、typecheck.txt、build.txt；副本内实际执行Node门禁 |
| 模拟 Node18：实际检查入口 / npm run typecheck / bootstrap.ps1 | 1 / 1 / 1（预期） | node-entry.txt、node-lifecycle.txt、node-bootstrap.txt；明确24.14.0 required，未创建bootstrap目标环境 |
| uv export --frozen runtime/dev | 0 / 0 | runtime-export.txt、dev-export.txt、export-comparison.json；除导出命令注释头外与两份 requirements 一致 |
| 版本、锁和驱动参数补核对 | 0 | versions-corrected.txt、runtime-node.txt、runtime-npm.txt、additional-boundary.json |

Starlette/AnyIO BlockingPortal 的1条弃用警告原样保留；没有屏蔽警告或跳过强制探针。这里的66是本轮独立实测，非执行者历史统计。原 r1 HTTP 失败、整改早期失败证据均未修改。

审核辅助执行有两处非产品修复记录：第三次连续请求8020在启动子进程前被 WinError10048 拒绝；没有确认占用根因，不声称一定是TIME_WAIT，随后补充HTTP使用新端口14126，实际原脚本主入口稍后在8020正常通过。另一次版本查询误查项目未声明的 langchain 分发包而退出1，改查已声明 langchain-core后成功；未增装包。首次日志/脚本保留，audit-notes.json记录原因。http-db-failure.json的辅助命令元数据误保留8020，实际端口14126以服务器日志和该补记为准。此类审核记录差异没有修改被审实现。

## 3. ISSUE逐项复核

| ISSUE | 结论 | 文件/行号与独立依据 |
| --- | --- | --- |
| 001 | RESOLVED | `backend/app/infrastructure/db_target.py:48`、`migrations/env.py:10`：校验在create_engine前；query仅允许单个connect_timeout，1—5秒；驱动参数重新构建，不转交原DSN。原dbname/host/port覆盖在本轮boundary测试中拒绝，engine未调用；真实迁移成功。 |
| 002 | RESOLVED | `db_target.py:17`、`backend/app/infrastructure/db.py:11`、`tests/conftest.py:21`、`scripts/probes/graph_worker.py:30`、`prepare_database.py:16`：共用校验，固定数值host/hostaddr、5433、dbname、用户、密码、passfile=os.devnull。原hostaddr绕过、service、多主机、缺参数、PG变量、越界库名端口和未知query拒绝。additional-boundary.json补测真实连接池及fixture入口，两个原绕过及未知参数均在驱动调用前拒绝，调用数0。 |
| 003 | RESOLVED | `scripts/probes/http_smoke.py:16`、`:29`、`:43`、`:63`：只重试ConnectError/ConnectTimeout；总deadline和子进程poll存在；finally只结束自身Popen。独立完整测试包含2秒延迟就绪、永不监听限时失败、提前退出7、端口占用不调用Popen且原监听仍可连接；实际main入口也通过。 |
| 004 | RESOLVED | `.node-version:1`、`frontend/scripts/check-node.mjs:4`、`frontend/package.json:10`、`scripts/bootstrap.ps1:10`：声明与engines/文档均24.14.0。正确版本实际ci/typecheck/build；隔离子进程preload只模拟process.versions.node=18，实际检查脚本、npm pretypecheck与bootstrap均明确失败，未触及全局运行时。不是仅调用比较函数。 |
| 005 | RESOLVED | `docs/implementation/STATUS.md:28`：已明确53初始/63扩展并链接证据。protection-after.json重新计算差集恰为P2—P6十份文档；共同文件仅阶段总表有已记录历史差异；当前63项均匹配保护哈希，无旧业务源码变化。 |

共享门禁也实际用于向量/重复建库入口；扫描所有connect/ConnectionPool/create_engine调用未发现原始DSN旁路。SQLAlchemy最终参数测试将URL解析参数与connect_args合并，确认最终host/hostaddr均127.0.0.1、port5433、明确库名。迁移允许xiutu_dev或xiutu_test_*，测试只允许后者，建库的管理连接仅xiutu_dev。

拒绝所有非空PG*是README和兼容矩阵明确声明的WP-01本地限制，包括可能不改变目标的PG选项也会拒绝。当前属于保守的已知范围约束，不判为本包功能缺陷；不是宣称生产任意PostgreSQL配置已支持。反例禁用连接以证明门禁，不用于替代后面的真实数据库能力验证。

Node反例shim位于本轮隔离目录，只作用于测试子进程。npm实际输出pretypecheck，随后版本检查错误；bootstrap在uv安装前退出。未安装或切换全局Node。

## 4. ENV-001及真实数据库/协议验证

**ENV-001：RESOLVED（当前引擎可用）。** docker version/info/context均成功：Server29.4.0，Desktop4.69.0，desktop-linux。docker-owned.txt显示现有容器标签project=xiutu-v5/service=postgres、healthy、绑定127.0.0.1:5433→5432；配置文件归属本项目。没有依据历史引擎故障重复修复，没有执行compose up/recreate/down、删卷或改全局配置。

镜像 `pgvector/pgvector:0.8.2-pg16-bookworm`，实际digest与compose一致：`sha256:00ba258a66dac104fd5171074a0084462a64a1369d8513f3d0a634e2f24d15bc`。见docker-image.txt、docker-owned.txt；数据库实际连接进一步确认该端口服务可用。

本轮唯一库：`xiutu_test_r2_d45ee786b69d4891b5b6a405f4ab`，保留供复核，未删除任何数据库。

- database-before.json：新库无用户表，只有plpgsql；真实HTTP live200/ready503。
- 环境迁移后：PostgreSQL16.14、vector0.8.2，alembic_revision=0001_environment；真实HTTP ready200。版本值由完整测试查询断言和重复库保护断言验证。
- 认证失败目标返回真HTTP503；无配置main入口也503；缺迁移及错误revision在真实独立schema中ready=False。**本轮没有停止数据库来重做“Server完全离线”反例**，该具体情形沿用整改启动数据库前证据及未变化的错误处理路径，不把当前认证失败写成引擎停机实验。
- 实际合成向量查询断言顺序[1,2,3]、首个距离0。不是embedding语义效果。
- 四个UUID probe schema创建/清理均记录，before/after其他schema目录一致；最终仅public.alembic_version，没有残留wp01_* schema。证据full-tests.txt、database-after.json。
- checkpoint进程A PID29856正常退出0，状态count=1、next=[pause]；随后进程B PID35864相同workflow `wp01-1bf9132565214525b91e366db6ccba45`，count仍1、approval=approved、next=[]；错误workflow退出4、unknown_workflow。测试明确等待A结束后启动B，不是同进程或MemorySaver。
- 重复CREATE DATABASE被拒绝，原迁移内容仍0001_environment；不覆盖或清空已有库。
- MCP独立服务器/SDK transport协商2025-11-25，initialize/list/call实际echo成功；停止自身服务器后新连接初始化失败，包含ConnectTimeout，2.265秒<8秒。schema/输入输出在full-tests.txt，服务器日志另存test-process-logs。结论不覆盖生产重连、在途请求恢复或正式维修工具。

## 5. E01—E16

| 项 | 结论 | 依据及适用边界 |
| --- | --- | --- |
| E01 | PASS | frozen新环境、pip check、requirements导出一致、Node实际门禁、npm ci |
| E02 | PASS | 哈希一致独立副本及全新venv完整测试、真实HTTP；不是复制既有环境 |
| E03 | PASS | 真HTTP live200、ready200及无配置/空库/认证失败503，缺/错迁移真实schema反例；引擎完全离线本轮未重做，范围如上 |
| E04 | PASS | health调用链无模型；禁止socket的健康测试、configured与verified分离通过 |
| E05 | PASS | 本轮真实PG16.14/vector0.8.2、环境迁移及向量排序，固定镜像digest |
| E06 | PASS | 35项边界+额外真实入口反例；唯一库、schema目录清理、重复库拒绝保留内容 |
| E07 | PASS | A/B独立PID、同workflow跨进程恢复、执行计数1及错误ID退出4 |
| E08 | PASS | 本轮真实MCP SDK transport与有界断连错误 |
| E09 | PASS | 实际ChatDeepSeek适配器离线schema/工具ID及ToolMessage对应、结构错误/模拟超时；禁止真实socket |
| E10 | NOT_VERIFIED | 未获付费授权，未执行真实模型请求；不能以离线契约或已配置key替代 |
| E11 | PASS | 独立前端ci/typecheck/build；最小基础环境页面，没有业务工作台 |
| E12 | PASS | 本轮版本与锁/矩阵一致；Node24.14.0/npm11.9.0，真实数据库版本与镜像确认 |
| E13 | PASS | echo、合成向量及最小图仍限定技术探针；未注册正式业务能力 |
| E14 | PASS（检查范围内） | 敏感配置脱敏、actual密码扫描0匹配、忽略规则、暂存与待交付扫描；不保证穷尽未知秘密格式 |
| E15 | PASS | 当前63项旧文件逐项哈希一致，53/63历史差集可核对；旧8014归属未改，未读取/写入旧业务库 |
| E16 | PASS | STATUS保持WP-01 IMPLEMENTED_NOT_ACCEPTED、WP-02—17 NOT_STARTED；无正式业务表/诊断/报告 |

E09、E13及原暂存文件的设计判断同时参考r1，但相应代码/原暂存基准未改变，且本轮重新执行离线/MCP测试。其余核心运行项使用本轮证据；没有将r1或整改的PASS直接转抄。`.gitattributes`仅原始evidence及顶层scripts/*.py的指定空白例外，未广泛关闭普通业务代码和文档检查。

## 6. 接受建议、保留项与停止点

无新增必须整改ISSUE；不修改原r1的历史BLOCKED结论。建议用户接受**WP-01已验证的核心技术交付，并显式保留以下缺项**：

1. E10真实DeepSeek契约仍NOT_VERIFIED，后续必须先授权模型、调用范围与预算，最迟WP-09收口。没有付费调用记录、usage或真实模型通过声明。
2. 真实资料门槛NOT_MET：来源/许可、精确车型/发动机适配、正式规格、电路/针脚、拆装/复核章节及缺图仍待确认。私人备份许可不等于公开分发许可，教学/合成资料不能作为正式维修依据；最迟WP-10/真实效果验收前补齐。
3. 本轮图/MCP/向量通过仅证明WP-01技术契约，不证明生产事务/fencing恢复、正式业务工具或维修效果。

报告、全部原始证据及唯一审核副本保留。只清理本轮probe schema与子进程，测试数据库保留；没有删除既有库或卷。STATUS、WP-00接受记录、原报告、历史evidence及Git index未变。审核结束，等待用户决定是否带列明缺项接受；不自动进入WP-02。
