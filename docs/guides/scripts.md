# 脚本入口

按用途从下表选取。

| 用途 | 入口 |
| --- | --- |
| 新机器校验/初始化 | setup_workspace.py |
| 通用前台开发运行 | dev.py |
| 仓库上传前检查 | check_repository.py |
| 本机后台运行工作台（API、前端、Worker，需本机 runtime.json） | workbench.py start/stop/status |
| 依赖环境 | bootstrap.ps1 |
| 模板与资料校验/登记 | seed_workbench_templates.py、seed_area_references.py（资料列表 `resources/knowledge/tayron/manuals.json`） |
| 本机升级数据库并导入、切块、计算资料向量 | install_area_references.py（先 `workbench stop`） |
| 发布新模板版本 | publish_independent_templates.py，默认预检 |
| API 类型 | export_frontend_openapi.py |
| 专项测试与探针 | test.ps1、probes/、run_reference_ingest_db_tests.py |
| 评测与核对 | section_retrieval_eval.py、run_area_advice_eval.py（花钱，先确认）、compare_reading_sources.py |

setup_workspace 使用仓库内资源，不要求原机器 E 盘资料目录。
