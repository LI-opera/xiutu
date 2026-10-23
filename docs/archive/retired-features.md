# 已移除的旧功能（2026-10 清理第二步）

PR #14 之后，仓库里新旧两套资料系统、三代病例流程并存。为了让代码和讲解只对应一套正在用的系统，下面这些在清理第二步中整体删除。**内容没有丢失**，都在 git 历史里：删除前的最后一个提交是 `3e7142f`（`feat/vehicle-routing` 分支，PR #14）。

| 移除的部分 | 当初做什么 | 现在由什么代替 |
| --- | --- | --- |
| 旧资料中心（`/documents/legacy` 页面、`/api/v2/documents`、`/api/v2/evidence`、`retrieval/` 里的 PDF/Markdown 解析和 token 分块、Worker 的 `ingest`/`index` 任务、documents/chunks/chunk_embeddings 等表） | 上传、人工审核、按约 600 token 分块、TF-IDF + 向量检索 | "维修资料"页：按车型上传 Markdown，按章节切块、向量化，分析时两步检索 |
| 区域资料绑定表 `area_reference_bindings` 和区域资料清单 `area_reference_manifest_*.json` | 人工指定每个模板区域读哪份资料 | 资料只记录适用车型；分析时按内容选资料。仓库自带资料列在 `resources/knowledge/tayron/manuals.json`，评测用的标准答案在 `evals/area_documents.json` |
| MCP 服务（`search_manuals` 等三个只读工具）及其 Docker 配置 | 通过 MCP 查询旧资料中心 | 暂无，以后在新资料表上重新做 |
| 早期诊断流程（`legacy_execution/` 的 LangGraph 执行器、诊断区域/步骤、证据、测量规格、工具调用、报告） | WP-09～WP-15 时期的分步诊断与报告 | 模板工作台：检查记录 → 规则摘要 → AI 综合分析 → 维修复检 |
| B01/B02 演示专题、模板 v1（计算规则写在代码里）、旧病例分析（C 系列）、旧原型页面 | 早期演示与第一版模板 | 模板 v2：计算与观察规则全部写在模板数据里 |
| 前端按题号写死的 A 类判断（RET-01、RET-04、IN-08 等） | 只服务于上面的旧题目 | 删除；B 类判断（AIR-14 等）仍在，见改进清单 |

数据库由迁移 `0026_retire_legacy` 处理：删除上述旧表、LangGraph 检查点 schema，以及不是"模板 v2 病例"的旧病例和它们的记录（运行前必须备份，并显式设置 `XIUTU_ALLOW_LEGACY_DELETE=1`）。这个迁移不能降级，恢复请用备份。

查看旧文件：

```powershell
git show 3e7142f:backend/app/mcp_server/main.py
git checkout 3e7142f -- backend/app/legacy_execution   # 取回到工作区，不会自动提交
```

清理之前写的长篇文档已移到 [before-cleanup/](before-cleanup/)，现在的结构以 [../architecture.md](../architecture.md) 和 README 为准。
