# 测试说明

| 目录 | 内容 | 需要什么 |
| --- | --- | --- |
| `unit/` | 模板计划与投影、答案校验、规则计算、AI 输入组织、检索与资料入库、维修复检、模型网关（离线 MockTransport） | 无数据库、无网络 |
| `contract/` | 启动、健康检查、依赖导入、数据库目标边界 | 无数据库 |
| `integration/` | 真实 PostgreSQL 上的病例 HTTP、模板全流程、资料上传入库、迁移（含 0026 只在允许时删旧数据） | `TEST_DATABASE_URL`，库名须为 `xiutu_test_*` |
| `probes/` | pgvector 等环境探针 | 视文件而定 |

常用命令：

```powershell
uv run python -m pytest tests/unit tests/contract -p no:cacheprovider -q --basetemp .test-runs\pt
uv run python -m scripts.run_reference_ingest_db_tests
```

- 数据库测试只连 `127.0.0.1:5433` 上的 `xiutu_test_*` 库，没有 `TEST_DATABASE_URL` 时直接失败，不回退开发库。
- 不默认调用付费模型；AI 评测见 `evals/area-advice/README.md`，先确认费用再跑。
- 旧流程（早期诊断、旧资料中心、MCP、B01/B02）的测试已随代码删除，见 `docs/archive/retired-features.md`。
- 测试通过证明相应实现范围，不证明真实车辆维修效果。
