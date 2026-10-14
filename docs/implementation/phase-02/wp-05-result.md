# WP-05 执行结果

状态：IMPLEMENTED_NOT_ACCEPTED。执行者实现与自测，等待一次集中审核及用户决定；不是审核通过或用户接受。未进入WP-06。

## 现在可以做什么

本地MD/PDF解析切块后，符合服务器审核/来源/许可资格的资料能由持久worker生成真实E5向量、建立版本化索引，以TF-IDF+精确cosine+RRF检索chunk并回到不可变原文。重建失败、取消、失租约、旧worker迟到不切换active；旧合法索引继续可查询。审核撤销后不进入新搜索快照。

可执行 `uv run --frozen python -B scripts/demo_retrieval.py --output .test-runs/wp05-demo-unique.json`，前提为README的新测试库/当前迁移及固定模型准备。上传→解析/SSE→合成审核→索引/SSE→检索→原文定位已真实运行。演示只接受测试库，明确synthetic服务器profile；不是正式资料专业审核。公开请求不能切换profile或指定其他owner。

正式资料尚不足：synthetic、pending/rejected/revoked、needs_ocr、来源/许可未核实不进入formal候选；缺精确车型/发动机信息为unknown，仅通用参考；明确冲突排除。approved不是直接ready，也不等于维修效果。本包没有OCR、Agent、正式前端或case_evidence；后者留给WP-06，未开始。

## 基准与实际范围

开始核对WP-04 r2基准1281项，STATUS按用户接受后的已知哈希替换比较，全部匹配；WP-04接受记录SHA256 `42eff7847f16d865e896a57f27e1c4cf15d5bc2d9994568f7096015fc8636cd9`，未改。捕获当前Git交付清单1265文件于baseline.json。main无HEAD，记录Git根/分支/状态，不依赖git diff判断新增文件。

Git index始终 `c451d6e78b8f29fc818002923a19fb1a888139ced20679ad545f75e9692a9ec6`。旧项目63项哈希、0001—0004、共享db_target、全部已有接受/报告/证据不变；结束核对见protection-final.json及delivery-hashes.json。模型、凭据、测试存储均在忽略或系统临时目录；没有提交、推送或调整暂存区。

主要新增：

- `migrations/versions/0005_indexes.py`：index_versions、chunk_embeddings(vector384)、review_snapshot、active_index_id与版本复合FK；building部分唯一索引。旧迁移不改。
- `infrastructure/embedding_gateway.py`、`index_state.py`、`services/index_service.py`、`index_builder.py`：真实模型、资格检查、分批暂存和原子激活。
- `retrieval/eligibility.py`、`sparse.py`、`service.py`、`domain/retrieval.py`、`api/evidence.py`：适配、TF-IDF、PG精确cosine、融合与API。
- `tests/unit/test_retrieval.py`、`tests/integration/test_indexes.py`、`evals/retrieval-synthetic-v1.json`、`scripts/demo_retrieval.py`、`scripts/fetch_embedding.py`。

必要衔接修改：worker/job_store、run_service取消与index retry边界、document_service/响应模型/审核响应、ORM/health revision、应用路由/OpenAPI、0005迁移回归、原资料测试索引字段断言；原文解析器/存储/NUL/数据库隔离门禁不改。原demo_documents只修正“索引未实现”旧输出文字。

依赖修改由uv add解析uv.lock，requirements.txt从锁导出；README、CHANGELOG、API说明、依赖矩阵、STATUS、契约与ADR同步。完整文件列表/新旧哈希见交付清单和保护记录。

## 模型与资源

固定`intfloat/multilingual-e5-small@614241f622f53c4eeff9890bdc4f31cfecc418b3`，官方MIT，FP32 ONNX、CPUExecutionProvider、384维，配置e5-small-onnx-v1。权重470268510字节；权重/tokenizer哈希固定且加载前验证。query:/passage:前缀、mean pooling、L2；长输入按480内容token窗覆盖、加权合并，不静默丢弃末尾。详见[ADR0002](../../adr/0002-local-embedding.md)及model-manifest.json。

实装onnxruntime1.30.0、tokenizers0.23.2、numpy2.5.3；Python3.12.10。AMD7500F/约32GB内存/RTX4060 8GB，选择CPU避免新增CUDA组合。BGE-M3只作候选资料比较，未下载/性能实测，未宣称本机不能运行它。

model-probe-v2.json：加载1.628秒；3文档18.75ms、3查询11.90ms；工作集802103296字节、峰值1181065216字节。原内存0值采样失败保留。中文→英文电瓶样例未排第一，未隐藏。sample-real-vector.json是本轮PG中已提交的完整384维合成向量及模型/文本哈希，不是随机替身。

未使用付费embedding/DeepSeek或外部推理服务；仅下载公开权重及依赖。没有上传私人资料。Embedding失败503不会自动降级成baseline；baseline只供内部显式评测。

## D210—D212 自测证据

| 验收点 | 本轮事实与边界 |
| --- | --- |
| D210 | 真实ONNX文档/查询向量、固定模型与文件哈希、维度/数量/有限值/非零验证；错误维度由PG拒绝；缺本地模型实际ASGI503且无baseline伪成功。model-probe-v2、sample-real-vector、targeted/full/final-targeted |
| D211 | 同一冻结24段/12查询合成集比较，SHA256 `29ab9e0e06c63d77340fc5880a4a7e18ca5808961db2b0b7c59bfd3d08c1d1b1`，eval-freeze在首次评测前写入；debug/heldout分列，未调标签或删失败。仅合成技术评测，真实维修召回NOT_VERIFIED |
| D212 | 真实PG和不同worker进程；新索引8/20条时中断，旧active仍检索，恢复后完整20条且一套；before_finish中断/租约/取消/撤销、真实version锁跨租约回滚、并发reindex实测两连接锁等待一202一409；旧索引不被覆盖，错维度不能混入。partial-batch/activation-lock-window/index-recovery/concurrent-reindex*.json |

所有模型推理在数据库事务外，worker独立心跳。批次写入和最终激活使用原租约物理连接；最终发布取得version锁后再验证，并复用所有SQL后的clock_timestamp+原deadline快照检查，job/run/ready/active/event在同一事务；失败整体回滚。staging批次可保留但building/failed不可查询。查询在推理后重新核对当前owner资格及active快照，变化返回409，不拿历史ready替代当前审核。

## 冻结评测结果

| 模式 | n | Recall@5 | Hit@5 | MRR@10 | p50/p95 ms | 未完整召回 |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| TF-IDF baseline | 12 | 0.847222 | 0.916667 | 0.861111 | 24.737 / 26.684 | q07,q11,q12 |
| hybrid | 12 | 0.930556 | 1.000000 | 0.881944 | 31.970 / 34.234 | q11,q12 |

Recall为相关片段比例的查询宏平均，Hit为至少一条；初始Recall@5≥0.85目标保留。hybrid在这个小样本合成集上改善0.08333并超过目标，**不代表真实维修召回达标**。标签由实施者编写，无人类专家真值；没有足够真实语料。延迟为该次热模型小样本服务调用，非生产负载/冷启动指标。全部排名和失败查询见evaluation-results.json，固定基准DB和ID保留可核对。

## 实际执行与统计

工作目录统一`E:\Work\xiutu-v5`。隔离库`xiutu_test_wp05_d412b38a192b486cb65e`，迁移回归另自动创建唯一测试库；仅复用确认归属的xiutu-v5-postgres-1/127.0.0.1:5433，PG16.14/vector0.8.2，镜像digest见environment-results.json。未重建/删除容器卷、不停止未知服务。凭据由新项目受保护文件静默读取，不进入命令文本。

| 运行 | passed | failed/error/skipped | 警告 | 证据 |
| --- | ---: | --- | --- | --- |
| 首轮定点 | 15 | 0/0/0 | 0 | targeted-first.* |
| 补充窗口 | 4 | 0/0/0（7 deselected） | 1 已知Starlette/AnyIO弃用 | targeted-windows.* |
| 批次取消边界 | 1 | 0/0/0 | 0 | targeted-cancel.* |
| **标准完整入口，一次** | **192** | **0/0/0** | **1 已知弃用** | full.*，335.67秒 |
| 完整后最小收尾定点 | 4 | 0/0/0 | 0 | final-targeted.* |

完整后自检仅补全版本查询的failed/last_index_status/index_error及ORM新表默认值一致性，新增2个用例；**不将192写成最后这次改动后重新全量通过**。完整入口对应full-code-hashes.json；最后4项验证上述两点、旧active/维度门禁及正常资料HTTP。未变检索算法的评测证据仍适用。没有重跑前端、第二环境或循环全量直到通过。

完整入口覆盖WP04三窗口及SQL失败回滚、WP03互斥/取消/预算/断锁、WP02认证幂等、迁移/health、PG/vector、checkpoint跨进程、MCP真实往返断连。SSE心跳过期用例本轮17.11秒通过；**本轮未复现，首次根因未确认**，没有修改该测试或扩大超时。

逐条原始命令、cwd、开始/结束时间、退出码在各label.json，原输出label.txt、JUnit及SHA在test-summary.json；172份本轮自建子进程日志另存child-logs，原路径/哈希在child-log-manifest.json。

| label | 命令（凭据由runner静默注入） | 退出码 |
| --- | --- | --- |
| create | `E:\Work\xiutu-v5\.venv\Scripts\python.exe -B scripts/probes/prepare_database.py --name xiutu_test_wp05_d412b38a192b486cb65e` | 0 |
| migrate | `E:\Work\xiutu-v5\.venv\Scripts\python.exe -B -m alembic upgrade head` | 0 |
| model-v2 | `E:\Work\xiutu-v5\.venv\Scripts\python.exe -B docs/implementation/phase-02/evidence/wp-05/probe_model_v2.py` | 0 |
| targeted-first | `E:\Work\xiutu-v5\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider tests/unit/test_retrieval.py tests/integration/test_indexes.py -q -s --basetemp E:\Work\xiutu-v5\.test-runs\wp05-4da5214d67da4fec8d464c802a79458b/targeted-first --junitxml=E:/Work/xiutu-v5/docs/implementation/phase-02/evidence/wp-05/targeted-first.xml` | 0 |
| targeted-windows | `E:\Work\xiutu-v5\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider tests/integration/test_indexes.py -k partial_batch or activation_lock or missing_model or queued_cancel -q -s --basetemp E:\Work\xiutu-v5\.test-runs\wp05-4da5214d67da4fec8d464c802a79458b/targeted-windows --junitxml=E:/Work/xiutu-v5/docs/implementation/phase-02/evidence/wp-05/targeted-windows.xml` | 0 |
| targeted-cancel | `E:\Work\xiutu-v5\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider tests/integration/test_indexes.py::test_cancel_between_inference_and_batch_finishes_cleanly -q -s --basetemp E:\Work\xiutu-v5\.test-runs\wp05-4da5214d67da4fec8d464c802a79458b/targeted-cancel --junitxml=E:/Work/xiutu-v5/docs/implementation/phase-02/evidence/wp-05/targeted-cancel.xml` | 0 |
| evaluation | `E:\Work\xiutu-v5\.venv\Scripts\python.exe -B scripts/demo_retrieval.py --evaluate --output E:/Work/xiutu-v5/docs/implementation/phase-02/evidence/wp-05/evaluation-results.json` | 0 |
| full | `pwsh -NoProfile -File scripts/test.ps1` | 0 |
| final-targeted | `E:\Work\xiutu-v5\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider tests/integration/test_indexes.py::test_failed_build_visible_and_explicit_rebuild tests/integration/test_indexes.py::test_index_orm_defaults_match_migration tests/integration/test_indexes.py::test_queued_cancel_and_dimension_guard tests/integration/test_document_ingest.py::test_real_http_versions_review_and_locators -q -s --basetemp E:\Work\xiutu-v5\.test-runs\wp05-4da5214d67da4fec8d464c802a79458b/final-targeted --junitxml=E:/Work/xiutu-v5/docs/implementation/phase-02/evidence/wp-05/final-targeted.xml` | 0 |
| dependency-check | `uv pip check` | 0 |
| frozen-sync | `uv sync --frozen` | 0 |
| model-cache | `E:\Work\xiutu-v5\.venv\Scripts\python.exe -B scripts/fetch_embedding.py` | 0 |
| openapi | `E:\Work\xiutu-v5\.venv\Scripts\python.exe -B docs/implementation/phase-02/evidence/wp-05/export_openapi.py` | 0 |
| lint | `uv run --frozen ruff check backend tests scripts migrations/versions/0005_indexes.py` | 1 |
| lint-scope | `uv run --frozen ruff check backend tests migrations/versions/0005_indexes.py scripts/demo_retrieval.py scripts/fetch_embedding.py scripts/demo_documents.py` | 0 |
| git-whitespace | `git --no-optional-locks -c safe.directory=E:/Work/xiutu-v5 diff --check` | 0 |
| seal-data | `E:\Work\xiutu-v5\.venv\Scripts\python.exe -B docs/implementation/phase-02/evidence/wp-05/seal_data.py` | 1 |
| seal-data-v2 | `E:\Work\xiutu-v5\.venv\Scripts\python.exe -B docs/implementation/phase-02/evidence/wp-05/seal_data_v2.py` | 0 |

requirements导出实际命令：`uv export --frozen --no-dev --no-emit-project --format requirements-txt --output-file requirements.txt`。模型下载命令与固定来源见download_model.py及model-manifest.json；当前可复现入口fetch_embedding已验证现有文件哈希。官方资料链接集中在ADR。

## 必须解决项、非阻断待办与保留限制

本次自测后没有已知必须整改的WP05实现问题，仍待审核者核对，不能由执行者写审核通过。真实维修语料/专家真值不足继续列为后续阶段门槛，不以合成指标替代。

保留失败记录：初次静态检查的新测试引号/F811问题已修复（任务工具记录与development-notes）；首次内存0采样无效保留；最终全目录lint返回1是**未修改**的scripts/wp00_baseline.py两处既有风格问题，本包范围lint为0；seal-data首次按numpy假设调用tolist而实际返回list，导出辅助脚本失败保留，v2正确导出后退出0。没有掩盖为一次全通过。

非阻断：索引构建/查询吞吐与内存配额、暂存向量/旧索引清理、监控、永久检索日志平台、大模型/GPU比较、跨语言真值；现有上传配额/复杂PDF隔离等待办保留。精确检索面向小语料，未做性能压测或ANN；当前只支持固定384维配置，换维度需新迁移。提交通信不明确和生产灾备不在本包保证内。

E10继续NOT_VERIFIED，模型/调用范围/预算另行授权、最迟WP09；真实资料NOT_MET，来源许可、精确车型/发动机及规格/线路/拆装/复核/缺图最迟WP10/真实效果验收前。未付费调用、未实现WP06、未修改历史接受记录。

执行结束时间：2026-09-18T15:32:07.887149+08:00
