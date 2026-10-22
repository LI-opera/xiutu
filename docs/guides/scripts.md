# 脚本入口

脚本保留当前路径以避免破坏 Python imports 和已有运行记录；按用途从下表选取，不按文件日期任意运行。

| 用途 | 入口 |
| --- | --- |
| 新机器校验/初始化 | setup_workspace.py |
| 通用前台开发运行 | dev.py |
| 仓库上传前检查 | check_repository.py |
| 原机器已登记实例 | wp15_workbench.py start/stop/status |
| 依赖环境 | bootstrap.ps1 |
| 模板与资料校验/登记 | seed_workbench_templates.py、seed_area_references.py |
| 本机升级数据库并导入、切块、计算资料向量 | install_area_references.py（先 `wp15_workbench stop`） |
| 原 WP15 受控发布 | publish_independent_templates.py，默认预检 |
| API 类型 | export_frontend_openapi.py |
| 专项测试与探针 | test.ps1、probes/、verify_* |
| 历史回放/核验 | c*_offline_replay.py、c*_audit.py 等，依赖相应历史环境 |

新克隆不直接运行旧一次性安装脚本。setup_workspace 使用仓库内资源，而不要求原机器 E 盘资料目录。
