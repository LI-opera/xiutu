# 文档导航

当前入口是根目录 README。本目录按架构、运行、学习、路线和历史分开。

| 目录 | 用途 |
| --- | --- |
| architecture/ | 当前模块与完整数据流；目录内其他设计文档需结合当前源码阅读 |
| guides/ | 新机器运行、验证及脚本入口 |
| learning/ | 沿四条实际业务链阅读源码 |
| roadmap/ | 当前能力与缺口，不代表已经安排全部实现 |
| api/ | 接口契约与生成的 OpenAPI，部分 WP 文档是阶段记录 |
| adr/ | 架构决策 |
| runbooks/ | 专项维护说明，执行前核对适用对象 |
| archive/ | 旧首页说明、开发证据与已移除功能的说明（[retired-features.md](archive/retired-features.md)） |

建议顺序：

1. [项目结构](architecture/project-structure.md)
2. [完整数据流](architecture/data-flow.md)
3. [创建病例](learning/01-intake-and-template.md)
4. [检查与更正](learning/02-observations-and-projection.md)
5. [AI 分析](learning/03-analysis-and-references.md)
6. [处理复检与历史](learning/04-repair-retest-and-history.md)
7. [当前能力与缺口](roadmap/current-capabilities.md)

2026-10 清理第二步删除了旧资料中心、早期诊断流程、MCP 和旧模板，见 [archive/retired-features.md](archive/retired-features.md)。GitHub 仓库不含原病例库、本机模型与凭证。
