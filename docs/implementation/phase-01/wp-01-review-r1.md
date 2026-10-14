# WP-01 独立审核 r1

审核时间：2026-09-18T02:42:26.380182+08:00。范围：当前 WP-01 交付与 Docker 只读诊断。

**总评：BLOCKED；同时存在必须整改的代码/脚本问题。不建议接受整个 WP-01。** 数据库隔离存在可复现的参数绕过；原 HTTP 冒烟脚本两次提前失败。真实 PG/vector 与图恢复仍缺失，不能给无条件 REVIEW_PASS。本报告不修改 STATUS、不替用户接受、不推进 WP-02。

## 1. 基准与读取范围

- 新项目 `E:\Work\xiutu-v5`，Git 根一致，分支 main；`rev-parse --verify HEAD` 退出128，确无首次提交。不能以此跳过审核。
- 32 个暂存文件；5 个已有文件有 WP-01 未暂存修改（.gitignore、CHANGELOG、README、STATUS、tests/README）；其他交付为未跟踪文件。完整列表及 cached/unstaged diff 见 `evidence/wp-01-review-r1/status.txt`、cached.txt、unstaged.txt。未执行 add/commit/reset/push，safe.directory 仅用于单次命令。
- 原 delivery-hashes.json 的156项与当前完全一致；另对该清单本身取哈希，共固定157文件。开始/结束文件 SHA256 见 baseline-before.json、baseline-after.json；**157项均未变化**。
- Git index SHA256：`c451d6e78b8f29fc818002923a19fb1a888139ced20679ad545f75e9692a9ec6`。
- WP-00 原审核 SHA256：`842f085cbffd50dfb92177a7042597b52ff0b751203a341edc0e43227a694b9b`。两者与 acceptance-baseline.json、final-protection.json 一致，结束再核对未变。
- acceptance-baseline 的32项中上述5文件因已授权 WP-01 有预期变化；这是接受后的实施变更，不是接受时基准失配。没有改原审核/接受记录。见 acceptance-comparison.json。
- 已检查项目、E:\Work、E:\ 及项目下适用 AGENTS.md，未发现。完整读取 STATUS、wp-01-result、dependency-matrix、wp-00-acceptance、P1实施说明/清单；读取总指南 WP-01、全局边界、恢复/MCP/模型、运行/配置/交付契约；审查 backend、迁移、所有 WP-01脚本/测试、前端壳、锁文件和原始证据。

本次仅新增本报告、对应审核证据及唯一隔离验证目录；没有改实现、原 evidence、旧项目或原服务。

## 2. 独立执行与证据

为了避免覆盖原 .venv、node_modules、dist 或历史 basetemp，复制已审源码/锁到全新 `.test-runs/wp01-review-r1-7e067fc7d84e47c0b64ac024860fdf48/snapshot`，独立 venv 位于其同级 `venv`。snapshot-inputs.json 逐文件证明复制输入与原交付相同。没有复制旧项目环境、数据或密钥。pytest 关闭缓存，设置 PYTHONDONTWRITEBYTECODE，清除数据库/模型配置，使用从未存在的新 basetemp。

全部实际命令、cwd、时间和退出码见 commands.json、supplement-commands.json、additional-commands.json、toolchain-checks.json；均位于 `evidence/wp-01-review-r1/`。以下为本轮结果，不引用执行者22 passed作为审核结果。

| 独立检查 | 退出码 | 本次结果及证据 |
| --- | --- | --- |
| UV_PROJECT_ENVIRONMENT=<审核venv> uv sync --frozen --group dev | 0 | frozen-sync.txt，全新隔离安装 |
| uv pip check --python <审核python> | 0 | pip-check.txt |
| python -B -m pytest tests/contract tests/probes/test_mcp_roundtrip.py tests/probes/test_pgvector_probe.py::test_database_down_health -p no:cacheprovider -q -s --basetemp <新目录> --junitxml=<新证据> | 0 | **22 passed，0 failed/errors/skipped，1 warning，11.78s**；independent-tests.txt、tests.xml |
| 原 scripts/probes/http_smoke.py（首次） | 1 | http-smoke.txt / http-server.txt；ConnectTimeout 未被重试 |
| 同一原脚本（新的日志路径再次运行） | 1 | http-smoke-retry.txt / http-server-retry.txt；服务器日志已显示启动，但首次连接超时使脚本提前退出 |
| 审核专用 http-independent.py（不改原脚本） | 0 | http-independent.txt；真实 Uvicorn PID33688，live200、ready503；只结束本次子进程 |
| npm.cmd --prefix frontend ci | 0 | npm-ci.txt；在审核副本安装 |
| npm.cmd --prefix frontend run typecheck / run build | 0 / 0 | typecheck.txt / build.txt |
| uv export --frozen --no-dev --no-emit-project --output-file <审核requirements> | 0 | export-runtime.txt |
| uv export --frozen --group dev --no-emit-project --output-file <审核requirements-dev> | 0 | export-dev.txt |
| requirements 导出比较 | 通过 | exports-comparison.json：剔除命令路径不同的注释头后，两份实际依赖内容均一致，非手写替代锁 |
| 纯参数隔离复现 isolation-review-v2.py | 0 | isolation-verified.txt；拦截 connect/create_engine 后续连接，**0次数据库网络连接** |
| Git working/cached diff --check | 0 / 0 | toolchain-checks.json |
| Docker version / context ls / desktop status / compose version | 1 / 0 / 1 / 0 | docker-current.json，详见环境部分 |

版本实测：Python3.12.10、uv0.11.28、Node24.14.0、npm11.9.0；核心包版本与原矩阵一致，见 versions.txt。Starlette 的 AnyIO BlockingPortal 别名弃用警告保留，未屏蔽。

真实 MCP 使用独立子进程与 SDK Streamable HTTP transport，初始化、发现、实际 echo 调用及 schema/结构化输出均通过，协议2025-11-25；停止该子进程后重新初始化有界失败。异常断言必须包含 ConnectError/ConnectTimeout，且小于8秒，不是任意异常都通过。它证明新连接的断连反例，不声称验证生产会话重连或在途调用恢复。

模型测试读取实际适配器并使用 MockTransport 和禁止 socket 的断言；工具响应 ID、ToolMessage ID、结构化解析及模拟超时有效，均为离线合成内容。未执行 tests/live 或任何真实模型请求，E10仍未验证。

审核辅助复现自身曾有两次失败：首次从旧 cwd 运行被 DATA_PATH 防护拒绝，第二次连接参数中 AdaptersMap 无法 JSON 序列化；随后在正确新项目 cwd、以类型名序列化非标量参数完成复现。旧项目未写入。这些是审核脚本问题，不计为产品缺陷；首轮错误已在审核过程记录；后续序列化失败输出及脚本版本保留。

## 3. E01—E16

| 项 | 结论 | 独立依据与限制 |
| --- | --- | --- |
| E01 | FAIL | Python/前端依赖锁安装与导出通过；总指南要求的 Node 运行时版本锁未落实，只有文档记录，见 ISSUE-004 |
| E02 | PASS | 全新独立 venv，导入/离线测试与独立 HTTP 检查通过；不是使用旧22通过统计；原冒烟工具缺陷另列 |
| E03 | PASS | API 实际 live200、无DB及不可达DB ready503；代码检查扩展与迁移；**真DB ready200未验证**。配套冒烟脚本不可靠，ISSUE-003仍必须整改 |
| E04 | PASS | health 无模型调用链，配置/验证状态分开；带离线占位key的禁止网络测试通过 |
| E05 | NOT_VERIFIED | 当前无数据库引擎；未运行真实扩展/向量查询，未取得镜像digest与PG版本 |
| E06 | FAIL | URL隔离存在实际参数绕过（ISSUE-001/002）；schema创建/清理运行部分仍 NOT_VERIFIED，不以解析复现替代真DB |
| E07 | NOT_VERIFIED | 静态设计是 subprocess A/B、正常退出后同workflow恢复、count=1和错误ID反例；真实DB运行仍未执行 |
| E08 | PASS | 本轮真实SDK服务器/transport往返和有界断连错误通过；断言并非忽略所有异常 |
| E09 | PASS | 实际适配器离线schema、工具ID和结果对应、结构错误与超时验证通过；不扩展为provider真实契约 |
| E10 | NOT_VERIFIED | 无付费授权，没有真实请求 |
| E11 | PASS | 审核副本 npm ci、类型检查、构建实际退出0；页面仅基础壳 |
| E12 | PASS | 包版本/锁/当前安装相符，DB与模型live缺项明确；Node运行时未锁是E01缺陷，不宣称全栈兼容通过 |
| E13 | PASS | probe_echo、测试向量、最小图均为探针，无正式业务注册 |
| E14 | PASS | 32暂存文件与157待审文件独立扫描、静态检查及忽略规则核验，无密钥模式或私人库/图片/备份正文；真实.env不读取；此扫描不保证覆盖所有未知秘密格式 |
| E15 | PASS | 可复核53/63逐文件清单与SHA256；当前63项无变化，旧8014 PID5328未变；未打开旧业务库，不把活跃库自然变化判成实施修改 |
| E16 | PASS | WP-02—17未开始，无正式业务表/诊断/报告/完整UI；资料门槛仍NOT_MET |

E03的PASS仅针对health接口路径，不能覆盖其配套冒烟工具失败，也不消除总评的整改要求。E06的FAIL针对已证实的隔离代码缺陷；真实schema和数据库运行检查另外保持NOT_VERIFIED。

## 4. 代码与交付问题

### ISSUE-001 — 必须整改 / 高：迁移校验与实际连接参数不一致（E06）

- 文件：`migrations/env.py:10`、`:11`、`:17`。
- 触发：`postgresql://review@localhost:5433/xiutu_dev?dbname=review_unrelated&host=192.0.2.10&port=5544`。无真实密码；192.0.2.10为文档保留地址。
- 复现：isolation-review-v2.py调用原 migrations/env.py，将 create_engine 入口截获，仅用实际 SQLAlchemy dialect 生成参数。门禁校验 URL authority/path 为localhost:5433/xiutu_dev而通过；最终参数却是 host=192.0.2.10、port=5544、dbname=review_unrelated，见 isolation-verified.txt。
- 影响：在真实可连接环境中，升级迁移可在非授权数据库执行DDL。当前未发连接，更没有证明已经发生数据修改。
- 修复要求：统一校验驱动最终使用的参数，拒绝可覆盖目标的 query/service/多主机/环境选项，或采用明确白名单后重建连接参数；不要只校验 make_url 的主字段。
- 复核：纯参数反例必须在创建引擎/连接前拒绝；合法隔离URI仍允许。再对真正独立测试库运行迁移正例，确保与探针目标一致。

### ISSUE-002 — 必须整改 / 高：hostaddr 绕过仅检查 host 的隔离门禁（E06）

- 文件：`tests/conftest.py:17`、`scripts/probes/graph_worker.py:30`、`scripts/probes/prepare_database.py:17`。
- 触发：合法 localhost:5433/xiutu_test_* URI 附加 `hostaddr=192.0.2.10`；prepare_database 对应xiutu_dev。
- 复现：原fixture直接接受该URI；图worker和建库脚本均进入被审核器截获的 psycopg.connect，参数保留非loopback hostaddr；没有真正连接。
- 影响：测试schema、checkpoint或CREATE DATABASE可能发往范围外服务器。libpq同时有host和hostaddr时后者决定网络地址，参见 [PostgreSQL官方连接参数说明](https://www.postgresql.org/docs/17/libpq-connect.html)。
- 修复要求：共享有效目标验证器，拒绝/严格限制hostaddr，并处理PGHOSTADDR、service、多主机等有效目标来源；保证测试、图worker、建库和迁移规则一致。
- 复核：覆盖URI hostaddr、PGHOSTADDR、query覆盖、缺参数及合法loopback；反例不允许发生connect。真实隔离schema清理仍须DB恢复后另测。

### ISSUE-003 — 必须整改 / 中：HTTP 冒烟启动等待漏处理 ConnectTimeout（E03）

- 文件：`scripts/probes/http_smoke.py:33`、`:35`。
- 触发：新解释器启动服务器时，Windows首次loopback连接在服务绑定前超时。
- 实际：两次原脚本均退出1，httpx.ConnectTimeout穿过仅捕获ConnectError的重试分支；15秒总等待尚未结束就退出并结束本次服务器。第二次服务器日志已输出正常启动。独立等待端口后同一代码返回200/503，说明不是health业务响应失败。
- 影响：独立环境/冷启动验证产生假失败，发布给用户的验证工具不可靠。
- 修复要求：在总deadline内处理预期连接超时及拒绝连接，保持失败上界与子进程退出检查；不要吞掉非连接异常或将最终超时改成成功。
- 复核：延迟监听超过单次1秒但小于总deadline时应成功；始终不监听时应限时失败；端口已占用不得停止未知进程。保留本轮两次失败证据。

### ISSUE-004 — 必须整改 / 中：未落实 Node 运行时版本锁（E01）

- 文件：`frontend/package.json:1`、`scripts/bootstrap.ps1:13`；依据总指南WP-01步骤7（约619行）。
- 证据：package-lock锁包版本，但无.node-version/.nvmrc等运行时版本声明，也无Node版本检查；package.json无engines，bootstrap只同步Python。dependency-matrix记载24.14.0只是实测记录。
- 影响：另一台机器可使用不兼容Node运行同一包锁；不能将“记录版本”写成运行时已锁。
- 修复要求：选定并声明已验证Node版本，提供明确检查/使用方式；只需最小版本门禁，不要求本包安装新系统软件。
- 复核：指定版本可完成npm ci/typecheck/build，故意不支持的版本在前置检查给出明确错误；不自动改全局Node。

### ISSUE-005 — 建议 / 低：STATUS 仅写53文件，未指明后续63项保护清单（E15）

- 文件：`docs/implementation/STATUS.md:28`（“以53文件前后SHA-256为基线”段）。
- 核对：原53项来自evidence/legacy-hashes-before.json；63项来自evidence/review-r1/legacy-hashes-after.json。新增恰为P2—P6共10份阶段文档；阶段总表一份历史变更已在baseline.md记录。当前63项全与后者一致。见legacy-protection.json，含每项当前哈希。
- 影响：读STATUS无法判断当前保护范围，但不是发现了旧业务修改，也不推翻已接受WP-00。
- 建议：明确“初始53项；当前扩展63项”，链接两份清单；保留并行文档变化说明。复核计数/集合差与当前哈希。

## 5. 环境阻塞：与代码问题分开

### ENV-001 — 核心阻塞：Docker 当前无可连接引擎（E05/E06运行部分/E07）

本轮只执行version/context/status/compose version以及日志、进程、socket元数据读取。没有启动/停止Docker、修改设置、删除socket、重装、改变WSL/虚拟化或创建替代数据库。

当前：CLI29.4.0、Compose5.1.1，context=desktop-linux，命名管道dockerDesktopLinuxEngine不存在；desktop status退出1。没有5433监听。`docker-current.json`与历史`evidence/wp-01/docker-blocker.json`是不同时间的证据，不把历史故障直接当当前状态。

当前读取的后台日志最后写入02:34:01，包含02:33:54（UTC18:33:54）的相同错误：Inference manager创建/移除dockerInference本地socket时系统拒绝访问并报告路径语法错误。这是最近一次启动失败位置，**不是最终根因证明**；无法据此断定一定是权限、陈旧socket、Docker缺陷或WSL损坏。该日志事件不由本轮只读诊断主动启动Docker触发。进程与socket元数据分别保存在docker-processes.json、docker-socket-metadata.json，不据元数据猜测修复成功。

建议最小后续范围（需用户另行决定）：先由维护者检查Docker Desktop自身错误界面；授权后仅按正常退出/启动流程尝试恢复一次，并运行docker version验证Server与管道。若同样失败，再对dockerInference文件类型/拥有者/使用者及具体Docker版本已知问题做针对性诊断；没有确认归属和恢复方案前不要直接删socket，也不先重装或改虚拟化。本报告没有执行这些动作。

引擎可用后，必须先修复ISSUE-001/002，再用专用project/volume与新测试库验证镜像tag/digest、PG/扩展版本、迁移、ready200、向量排序、schema清理、跨进程恢复和错误ID，保存新证据。不得拿SQLite、内存saver或mock代替。

E10仍NOT_VERIFIED：后续真实探针先取得模型、调用范围和预算授权。资料来源/许可、精确车型/发动机、正式规格/线路/拆装/复核章节及两张缺图仍未解决，资料门槛NOT_MET；技术echo/合成内容不是维修依据。

## 6. 结论与停止点

**BLOCKED，且需整改ISSUE-001—004；ISSUE-005为文档澄清建议。暂不建议用户接受WP-01。** 已验证的锁定安装、离线契约、真实MCP、前端和健康接口可保留，不需要推翻WP-00接受。

最小下一步是用户另行授权修复本包隔离门禁、HTTP冒烟和Node前置约束，并单独决定Docker环境处理；随后复核受影响项和补齐真实DB/图证据。不开始WP-02。本轮审核结束，等待用户决定。
