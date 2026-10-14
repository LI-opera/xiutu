# 本地运行

## 环境

Python 3.12、Node 24.14.0、uv、Docker Desktop Linux Engine。开发后端单进程，认证会话在内存中；API 重启后会话需要恢复。

从根目录执行 `uv sync --frozen --group dev`，进入 frontend 执行 `npm ci`。复制 `.env.example` 为 `.env`，填写自己的 PostgreSQL 密码和 DATABASE_URL。示例没有可用 key。

Docker Compose 的 postgres 使用固定镜像、127.0.0.1:5433 与持久卷。启动前设置当前 shell 的 XIUTU_DB_PASSWORD。不要执行 down -v、prune 或删除其他项目卷。

## 初始化与开发启动

```powershell
uv run python scripts/setup_workspace.py
uv run python scripts/setup_workspace.py --apply
uv run python scripts/dev.py
```

setup 默认仅校验仓库内独立 v2 模板、资料覆盖和源文件哈希；--apply 才连接指定数据库，要求没有病例且 schema 为空或已经位于当前迁移 head。它不会重置旧库，不调用模型。

dev 从项目 .env 加载配置，要求 APP_ORIGIN 是本机 HTTP，端口空闲、数据库当前 schema 就绪，再启动 API、Vite 和默认资料 worker。Ctrl+C 只终止本次创建的子进程。默认网页 5215、API 8215；支持 --web-port/--api-port，APP_ORIGIN 由本次网页端口明确指定。

不要在同一端口已有服务时另开 dev。原机器 WP15 实例继续用 wp15_workbench.py，它依赖未上传的本机 runtime.json，并非新克隆的通用初始化入口。

## 可选真实 AI

在自己的 .env 填 DEEPSEEK_API_KEY 后，显式建立用量账本：

```powershell
uv run python scripts/setup_workspace.py --enable-ai-budget
```

这一步表示授权本机由用户按钮触发的真实调用；不会自行发出模型请求，也不会重置已有账本。账本逐次计量，不提供统一累计消费封顶。避免重复点发起按钮，结果不明时先查询状态。

综合分析与 AI 排序是两个功能：综合分析依赖 key 和资料；排序还要求本机排序授权配置，通用 dev 不自动开放排序授权。

## 保留数据

克隆不恢复原机器的数据库、病例与历史 AI。需要迁移真实使用数据时，应另走备份、恢复和来源核对流程；不把 SQL dump 放进 Git。

资料中心的 embedding 模型不上传仓库；没有本地模型时，不把资料检索和索引功能宣称为已就绪。模板主流程直接读区域绑定正文，允许在不运行向量索引时使用。
