# 开发阶段证据（已移出仓库目录）

`docs/implementation/` 原来保存开发各阶段（phase-01～05、product-preview、product-recovery）的验收记录、执行日志、JUnit 和截图，共 171 个文件、约 2MB。它们记录的是当时的开发过程，不是当前功能的说明，2026-10 起从仓库目录移除，以保持结构整洁。

**内容没有丢失**，仍在 git 历史里。最后包含这些文件的提交是 `eec5550`（PR #10 合并后的 main）。需要查看时：

```powershell
# 只查看某个文件
git show eec5550:docs/implementation/STATUS.md

# 把整个目录取回到工作区（不会自动提交）
git checkout eec5550 -- docs/implementation
```

`docs/api/wp-*.md`、`docs/runbooks/*.md`、`tests/README.md` 等旧阶段文档里指向 `docs/implementation/...` 的链接，按上面的方法查看。

原来写入这个目录的几个旧预览工具（`scripts/dkvb_topic.py`、`scripts/probes/dkvb_verify.py`、`scripts/export_preview_types.py`）改为写到 `.local-data/evidence/product-preview/`（不进仓库）。
