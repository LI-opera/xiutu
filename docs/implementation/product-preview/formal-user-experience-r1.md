# WP-15 正式平台隔离体验实例记录 r1

- 时间：2026-09-21 22:18（Asia/Shanghai）
- 状态：已启动，保留供用户体验
- 范围：使用已限定接受的 WP-15 实现准备本地、持久、合成资料体验环境；未修改业务实现、测试、`STATUS.md` 或接受记录，未进入 WP-16。

## 地址与运行身份

- 正式前端基址：`http://localhost:5215/`
- 正式工作台：`http://localhost:5215/workbench`
- 资料中心：`http://localhost:5215/documents`
- 历史病例：`http://localhost:5215/history`
- API：`http://127.0.0.1:8215/`
- 只读 MCP health：`http://127.0.0.1:8315/health`
- 隔离数据库：`xiutu_test_formal_user_e4faa7fa2769`
- 独立 storage：`E:\Work\xiutu-v5\.local-data\formal-user-experience-r1\pytest-temp-27eee310\test_one_bounded_synthetic_tur0\storage`
- 访问令牌文件：`E:\Work\xiutu-v5\.local-data\formal-user-experience-r1\access.txt`

访问令牌只保存在被 Git 忽略的私有目录。本记录、日志和命令输出均未复制令牌、Cookie、数据库连接串或模型密钥。

## 准备结果

1. 新建持久隔离 `xiutu_test_*` 数据库，完成 Alembic `head` 迁移和 LangGraph checkpoint 初始化。
2. 导入 `tests/fixtures/diagnosis-slice/bench.md` 的可追溯副本。资料保持 `synthetic=true`、`formal_usable=false`；先经现有解析、演示审核和资格门禁，再使用本地 BGE-M3 建立 1024 维索引。没有修改旧 E5 索引。
3. 启动 API、正式 Vite 前端、worker 和独立只读 MCP。MCP 使用专用只读数据库角色，并绑定本轮空白起步病例；多病例体验 worker 显式使用现有可信本地工具模式，避免把静态 MCP case binding 错用于其他病例。远端 MCP 失败不会被伪装为本地成功。
4. 从现有私有 `.env` 只读取受控 DeepSeek 模型配置；没有输出、复制或封存密钥。本轮没有发起 DeepSeek 请求。

## 已准备病例

所有病例均显著标记为合成体验，不代表真实资料资格、真实车型结论或维修效果。

- 从头操作病例：`a3da81a8-ec26-425d-bfba-a635b2657a10`。revision 0；可由用户自行启动诊断。病例说明同时提示实际触发模型可能产生少量费用。
- 恢复病例：`cd31e861-d2a6-46ee-ba07-1d4c7984198a`。已有两个区域、一项已保存观察和一项等待输入的 Q02 检查；当前 revision 3，可刷新读回相同步骤、观察和来源。
- 报告/stale 病例：`704144f2-7513-4bdb-b2ec-c124b599c1c5`。已有免费生成的进度报告；追加不可变事实更正后旧报告显示 `stale`，相应后续诊断任务已取消，避免在准备阶段触发模型。

## 免费冒烟

私有脚本 `E:\Work\xiutu-v5\.local-data\formal-user-experience-r1\smoke.py` 使用真实 API、隔离 cookie 会话和当前数据库完成：

- 登录通过；
- `/documents`、`/workbench`、`/history` 和恢复病例 URL 均返回 200；
- 资料列表包含 1 份合成资料，历史页可读取 4 个病例（含初始化阶段保留的来源核对病例）；
- 恢复病例可读取当前检查、2 个区域、1 项已保存观察及授权 evidence；
- 连续两次读取保持同一 current step；
- 报告病例可读取 `stale` 进度报告；
- 只读 MCP health 就绪；
- 本轮付费模型调用数为 0。

浏览器已保留在正式工作台登录页。自动化没有把访问令牌写入可见证据；用户可从私有令牌文件复制后登录。

## 推荐体验顺序

1. 打开 `http://localhost:5215/workbench`，从私有 `access.txt` 复制令牌登录。
2. 进入“资料中心”，确认资料显示 `synthetic`、`formal_usable=false`，查看解析状态、切块和不可变原文。
3. 进入“历史病例”，主动搜索“合成体验”。先打开恢复病例，查看区域、Q02 当前检查、引用和已有 P01 观察；刷新页面确认状态恢复。
4. 打开报告/stale 病例，查看进度报告及其 `stale` 状态。`unknown`/`stale` 均不是确诊、排除或最终报告就绪。
5. 如需从头体验，打开从头操作病例并自行启动诊断。启动或提交观察后的续轮可能实际调用 DeepSeek，沿用持续计量 v2；预留和 usage 估算不是平台账单。

不要把准备阶段的免费确定性候选解释成模型自主选择。当前资料只适合合成技术体验。

## 停止与恢复

停止本轮四个登记进程并保留数据库、storage 和病例：

```powershell
E:\Work\xiutu-v5\.venv\Scripts\python.exe -B E:\Work\xiutu-v5\.local-data\formal-user-experience-r1\experience.py stop
```

重新启动时先启动 API，再启动其余服务：

```powershell
E:\Work\xiutu-v5\.venv\Scripts\python.exe -B E:\Work\xiutu-v5\.local-data\formal-user-experience-r1\experience.py start-api
E:\Work\xiutu-v5\.venv\Scripts\python.exe -B E:\Work\xiutu-v5\.local-data\formal-user-experience-r1\experience.py start-rest
```

脚本只终止 `runtime.private.json` 中 PID 与创建时间均匹配的本轮进程，不清理数据库或 storage。

## 保留限制

- 真实资料仍为 `NOT_MET`；本实例没有正式可用维修资料。
- 真实模型第二项当前检查、真实最终报告语义、真实维修效果和生产恢复仍未验证。
- `unknown` 仅表示保守待补，不是确诊、排除或换件依据。
- 本轮未执行完整 DeepSeek 体验路径；实际操作留给用户。
- 只读 MCP 是独立运行且受固定 binding 保护的服务；当前多病例 worker 使用既有可信本地工具模式。该实例不证明动态每病例 MCP 凭据编排。
- 本次是本地体验实例，不是生产部署；没有修改或操作 5180/5196。
