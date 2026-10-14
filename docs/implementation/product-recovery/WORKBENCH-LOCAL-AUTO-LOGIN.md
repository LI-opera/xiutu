# 本机开发工作台自动登录 · 2026-09-25

状态：`IMPLEMENTED_NOT_ACCEPTED`。只改变当前 5215 本地开发实例的会话建立方式；没有更改病例所有者、数据库或 AI 付费授权。

## 实施

- 原因：旧 `AuthStore` 会话仅在 API 进程内，重启后原 cookie 无效；Chrome 与内置浏览器又各自持有独立 cookie，因此反复显示令牌页。
- `LOCAL_DEV_AUTO_IDENTITY` 默认关闭；仅允许非生产且 `APP_ORIGIN` 为回环 HTTP。当前 `scripts/wp15_workbench.py start` 显式开启，继续使用既有 runtime `actor` 对应旧病例；受限真实模型窗口仍只允许回环自动身份，付费请求另由病例、revision、幂等键与单次授权共同限定，不因免登录而放宽。
- `GET /api/v2/auth/session` 对无效/缺失 cookie，仅在显式模式开启且请求的**实际客户端和本地套接字地址**都是回环 IP 时创建独立 HttpOnly/SameSite 会话。Host、`X-Forwarded-For` 不构成判断依据。已有效会话直接复用。写入仍需原有 cookie、Origin 与 CSRF；病例归属、其他权限、报告门禁不变。
- 前端收到旧会话的 401 后重新查询 `/auth/session`；普通模式仍回到原令牌页。当前实例关闭模式可使用 `start --manual-login`，不修改项目 `.env`。

## 定点验证

- 当前进程监听：Web `[::1]:5215`，API `127.0.0.1:8215`，未见 0.0.0.0 或公网监听。服务为本脚本登记的 API/Web/worker，重启未触及 Docker、数据库和卷。
- Python `tests/unit/test_auth.py`：7 passed。覆盖无令牌回环会话、重启后同一 actor 与新 CSRF、错误 CSRF 被拒、远端实际 peer 即使伪造 Host/转发头仍 401、模式关闭仍 401、生产或非回环来源禁止开启。
- 前端类型检查通过；新增会话恢复定点 1 passed。完整 `routes.test.tsx` 中旧工作台 mock 缺少 `readyView.areas`，其既有“restores the case named by the workbench route”用例失败；与本次会话用例分开记录，未改造无关 fixture。
- 新开 Chrome 标签与 Codex 内置浏览器标签，均未输入令牌就进入 [独立 C19 DEMO 病例](http://localhost:5215/workbench/663edce0-9a9a-4105-88a5-4dc01d697980)。刷新、退出后恢复、停止并重启本项目 API/Web/worker 后两端再刷新，均直接显示原病例及 revision 62，无令牌页。内置浏览器以该 DEMO 的正式问题接口记录 X-05“尚未执行”，revision 61→62；前置条件未被绕过，旧替身建议仍标过期。未修改用户当前 C17 体验病例。
- 根地址先前仍显示旧资料预览；已将 `http://localhost:5215/` 接入正式 `/workbench`，保留旧 `/preview` 及 `/#diagnosis`、`/#dkvb`。Chrome 和内置浏览器各自新开根地址，均直接显示“车辆接诊与诊断工作台”，无令牌输入。
- 临时以 `start --manual-login` 启动同一实例：无 cookie 的 `/auth/session` 为 401；随后已恢复默认自动登录，两个浏览器再次无需令牌加载。没有关闭整个 Chrome 进程（其中还有用户其他标签）；“关闭后重新打开”以新标签和独立内置浏览器会话验证，不声称实测 Chrome 进程退出再启动。

运行实例最后保持 `stub` / `paid=false`，真实模型调用数 **0**。自动登录不构成真实模型调用授权。
