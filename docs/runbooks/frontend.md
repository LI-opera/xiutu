# 正式前端本地运行（WP-14）

## 隔离验证实例

前置：现有 `xiutu-v5-postgres-1` 运行且只绑定 `127.0.0.1:5433`。脚本只创建一个新的 `xiutu_test_wp14_*` 数据库和专用 storage，不清理或替换已有数据库。

```powershell
cd E:\Work\xiutu-v5
.\.venv\Scripts\python.exe -B scripts\wp14_frontend.py init
.\.venv\Scripts\python.exe -B scripts\wp14_frontend.py start
```

打开 `http://localhost:5214/workbench`。访问令牌只在私有 `.local-data\wp14-frontend\access.txt`；不要复制进日志、截图或交付证据。

停止本轮 API、worker 和 Vite 进程，但保留隔离数据库与 storage：

```powershell
.\.venv\Scripts\python.exe -B scripts\wp14_frontend.py stop
```

该脚本不操作 5180/5196。`localhost` 用于把本轮浏览器 cookie 与两个 `127.0.0.1` 用户实例隔离。

## 生成与构建

```powershell
cd E:\Work\xiutu-v5\frontend
npm.cmd run api:generate
npm.cmd run api:check
npm.cmd run typecheck
npm.cmd run test:wp14
npm.cmd run build:wp14
```

`build:wp14` 输出到 `frontend\dist-wp14`，不会覆盖 `frontend\dist`。正式类型位于 `src\generated\api-schema.ts`；旧 `src\api-schema.ts` 只供已接受预览兼容入口使用。

## 功能边界

- `/documents`：上传、真实解析/审核/索引状态、原文、切块和合格资料试搜。
- `/workbench`：创建病例；带 case id 的路径刷新后读取同一快照。
- `/history`：用户主动搜索并选择病例。
- WP-15 已实现诊断启动、SSE、观察提交、区域切换和报告门禁交互；隔离启动、worker/MCP 配置与停止方法见 [frontend-diagnosis.md](frontend-diagnosis.md)。本页保留 WP-14 外壳与资料中心的运行基准。
