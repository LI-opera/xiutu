# Docker 运行

`deploy/docker/` 把整个修途放进 Docker：别人只装 Docker Desktop 就能运行，不需要 Python、Node 和 uv。改代码时仍用[本机运行](local-development.md)。

## 组成

| 容器 | 内容 |
| --- | --- |
| `postgres` | PostgreSQL 16 + pgvector（与本机运行同一个镜像） |
| `init` | 一次性任务，跑完就退出。执行 `scripts/container_init.py`：迁移数据库，补装缺少的模板和维修资料，并切块（挂载了模型时同时计算向量，第一次要几分钟）；重复执行不会改动已有数据 |
| `api` | FastAPI 后端，`init` 成功结束后启动 |
| `worker` | 与 api 同一个镜像，处理上传资料的切块和向量 |
| `web` | 构建好的前端页面 + nginx，`/api` 转给 api |

只有 `web` 对外开放端口，并且只监听本机 `127.0.0.1:8080`。数据库和后端不对外开放。

它与本机运行完全分开：项目名 `xiutu-docker`，数据卷 `xiutu-docker_pgdata`（数据库）和 `xiutu-docker_appdata`（用量账本、检索缓存）。两套可以同时运行，互不影响。

## 配置（`deploy/docker/.env`）

从 `deploy/docker/.env.example` 复制。

| 变量 | 说明 |
| --- | --- |
| `XIUTU_DB_PASSWORD` | 必填。只用字母和数字（它会放进数据库连接地址） |
| `XIUTU_ACCESS_TOKEN` | 必填，至少 32 个字符。登录页输入它；后端重启后需要重新输入 |
| `XIUTU_WEB_PORT` | 可选，网页端口，默认 8080。改了端口就用新端口打开，并且要用 `localhost`，不要用 `127.0.0.1` |
| `XIUTU_BGE_M3_DIR` | 可选，本机 BGE-M3 模型目录（含 `model.onnx` 或 `onnx/model.onnx`），只读挂载 |
| `DEEPSEEK_API_KEY` | 可选，真实 AI 分析；不用时整行保持注释，不要留空值 |

生成一个随机令牌（PowerShell）：

```powershell
-join ((48..57) + (65..90) + (97..122) | Get-Random -Count 40 | ForEach-Object { [char]$_ })
```

## 常用命令

都在仓库根目录执行。

```powershell
docker compose -f deploy/docker/compose.yaml up --build -d   # 构建并在后台启动
docker compose -f deploy/docker/compose.yaml ps              # 查看状态（api 显示 healthy 即就绪）
docker compose -f deploy/docker/compose.yaml logs init        # 查看初始化结果
docker compose -f deploy/docker/compose.yaml logs -f api     # 查看后端日志
docker compose -f deploy/docker/compose.yaml down            # 停止（数据保留）
```

清空 Docker 版的全部数据（不影响本机运行的数据库）：`docker compose -f deploy/docker/compose.yaml down -v`。

## 真实 AI

1. 在 `.env` 填写 `DEEPSEEK_API_KEY`，执行 `up -d` 让配置生效；
2. 显式建立用量账本（只需一次，不会调用模型）：

```powershell
docker compose -f deploy/docker/compose.yaml run --rm api python -B scripts/setup_workspace.py --enable-ai-budget
```

之后只有在页面上点击分析才会请求模型。AI 区域排序只在本机工作台授权，Docker 版显示为不可用。

## 向量模型

没有模型时：已带的 5 份资料在分析时整份发送给 AI；上传新资料会显示无法计算向量。

挂载模型后，下次启动时 `init` 会给已有资料补算向量（每份资料一次）。Hugging Face 缓存里的 `snapshots/<版本>` 目录如果是指向 `blobs/` 的快捷方式（符号链接），容器里会读不到，此时请把模型文件复制到一个普通目录再挂载。
