# WP-14 定点复核 r2

- 日期：2026-09-21（Asia/Shanghai）
- 范围：仅复核 `wp-14-review-r1.md` 的 ISSUE-001、ISSUE-002
- 结论：**REVIEW_PASS（限定正式前端范围）**
- 流程披露：本复核处于同一任务链，能够复用实施与整改上下文，不声称不同任务或组织上的独立审核。本轮没有修改业务实现、正式测试、STATUS、接受记录或历史报告。

## 1. 固定基准与保护结果

整改封存清单中的 9 个文件逐项重新计算 SHA-256，均与 `evidence/wp-14-remediation-r1/delivery-hashes.json` 一致，无未解释差异。关键当前哈希如下：

- `frontend/src/formal/pages/DocumentsPage.tsx`：`515a490f482e7a7533691a722881e7bb52a20d98b8672f773a6dc620331dcf88`
- `frontend/src/formal/pages/HistoryPage.tsx`：`7768dd545c382bc2c576b7ced7b2f609b759848326f98b038f395e0b9f00152a`
- `frontend/tests/pagination-context.test.tsx`：`7e40219df6d9410305d44945182f99c648ff1c57012418bd9a71d5a8bf8a4e4b`
- `docs/implementation/phase-05/wp-14-remediation-r1.md`：`c2a92c3c8e660aa3eee88702ab027a8b4d53afa0c3c99e190447ac776e703626`

Git 暂存内容按要求使用 `GIT_OPTIONAL_LOCKS=0 git ls-files --stage` 与 `GIT_OPTIONAL_LOCKS=0 git diff --cached --binary` 核对。为消除 PowerShell 首次和末次捕获的文本编码差异，两端都规范化为 UTF-8/LF 后计算内容哈希：

- `ls-files --stage` 前后均为 `e146135dd7084735f6b331b6ed1a3ac32938bf971f8705cf9e75e1dccb49a4ea`
- `diff --cached --binary` 前后均为 `dcbc0d1d7c2c1dd026a8106372d8beb6a9f5f38ac7dc10342ee3a4328389ad2b`

原始捕获字节哈希因 PowerShell 编码不同而不同，但逐行比较差异为 0；这不是 Git 暂存内容变化。没有执行 `git add/reset/checkout/commit/stash`。保护结果见 `evidence/wp-14-review-r2/protection-final.json`。

## 2. ISSUE-001：分页完整性

**结论：CLOSED。**

代码检查确认：

- 资料列表以 `useInfiniteQuery` 请求 `/documents?limit=50`，非空游标经 `encodeURIComponent` 后继续读取；跨页按 document id 保留第一次出现的位置稳定去重（`DocumentsPage.tsx:36-50`）。
- 切块查询键包含 document id 与 version id，使用 `/chunks?limit=100`；通过 `pageParam !== null` 保留数值游标 `0`，跨页按当前版本内稳定 ordinal 去重（`DocumentsPage.tsx:60-75`）。切换版本形成新的查询键，页面不拼接旧版本数据。
- 两类分页都检查所有已消费页的 `next_cursor`，非相邻游标循环也会停止；后续页错误保留已有数据，并只在用户点击重试后继续失败页（`DocumentsPage.tsx:184-187,211-213`）。
- 历史病例只在用户主动搜索后读取。查询键包含搜索文本和单调 generation；第一页无匹配且仍有下一页时自动继续，错误会停止自动翻页，只有游标耗尽且无错误时才显示“没有匹配病例”（`HistoryPage.tsx:15-45`）。跨页按 case id 稳定去重。

本轮直接证据：

- r1 原四个反例在当前源码上运行：**4 passed，exit 0**。第二页资料、第二页切块、历史后续页匹配与 A→B 迟到结果均通过。
- r2 审核夹具：**7 passed，exit 0**。其中分页部分覆盖：编码字符串游标；`cursor=0`；三页 `two → three → two` 非相邻循环；资料与切块跨页去重和顺序；切块第二页失败后保留第一页并从 `cursor=0` 重试；历史第二页失败时停止自动请求、保留未耗尽状态，点击重试后才恢复。
- 正式 WP-14 测试：**5 files / 24 passed，exit 0**。
- 隔离浏览器：当前源码、隔离数据库 `xiutu_test_wp14_01ad5ee5d8d0`、独立 Chrome 会话、web `localhost:5234`、API `127.0.0.1:8234`。加载更多后可见 **51** 份资料；选中首份资料后加载更多可见 **101** 个切块；历史第一页无匹配、第二页找到“后续目标车型”，未提前出现“没有匹配病例”。控制台 error/warning 为 0。浏览器与审核进程随后停止。

以上覆盖了 ISSUE-001 要求的数字/字符串/编码游标、重复游标、稳定去重、失败停止与正确页重试、搜索代次和版本隔离，未发现无界 `useEffect/fetchNextPage` 循环。

## 3. ISSUE-002：检索上下文隔离

**结论：CLOSED。**

生产页面在每次检索时冻结 document id、version id、问题文本、请求 generation、AbortController 和请求体；成功、错误及 settled 回调统一核对组件生命周期、当前 generation、当前资料/版本和当前问题（`DocumentsPage.tsx:105-152`）。选择资料、编辑问题及上传成功调用同一失效路径；新请求先中止旧请求并增加 generation；卸载时标记生命周期结束、增加 generation 并中止请求（`DocumentsPage.tsx:89-94,157-179,214-215`）。因此即使中止未及时生效，旧回调也不能发布。

本轮证据覆盖：

- r1 原 A→B 迟到成功反例通过。
- 正式测试覆盖 A→B 迟到成功、A→B 迟到错误、A→B→A、当前上下文正常错误及最新结果正常发布。
- r2 受控屏障补证同一资料/同一问题的重叠请求：较新的成功保留，较早请求随后成功或失败均不能覆盖或清空新结果。
- r2 受控屏障补证问题编辑、成功上传和组件卸载均使旧请求失效；旧成功或旧错误均未进入当前页面。
- 当前有效请求的结构化错误仍显示，问题输入保持不变；防迟到逻辑没有吞掉当前错误或禁用正常检索。

本地隔离资料没有合格检索索引，未通过篡改资格或制造静态成功来做浏览器检索；竞态由直接挂载生产 `DocumentsPage` 的审核夹具控制响应顺序。这与真实浏览器分页抽查分开记录。

## 4. 命令与证据

| 命令 | 结果 |
|---|---|
| `vitest run --config evidence/wp-14-review-r1/vitest.audit.config.ts --reporter=verbose` | exit 0；4 passed |
| `vitest run --config evidence/wp-14-review-r2/vitest.audit.config.ts --reporter=verbose` | exit 0；7 passed |
| `npm.cmd run test:wp14 -- --reporter=verbose` | exit 0；5 files / 24 passed |
| `node --test scripts/check-node.test.mjs scripts/material-intake.test.mjs scripts/preview-context.test.mjs` | exit 0；24 passed |
| `npm.cmd run typecheck` | exit 0 |
| `npm.cmd run api:check` | exit 0；OpenAPI 与生成类型 current |
| `npm.cmd run build:wp14 -- --outDir E:\Work\xiutu-v5\.local-data\wp14-review-r2-build` | exit 0；102 modules；独立输出 |
| 隔离实例 `start/status/stop` | 均 exit 0；结束时 owned processes 为空 |

构建仅出现已知的依赖包 `use client` directive 提示，以及输出目录位于 frontend 根外、不会自动清空的提示；不影响构建结果。详细日志、审核夹具与浏览器摘要位于 `docs/implementation/phase-05/evidence/wp-14-review-r2/`。

## 5. 证据边界

- r1 已验证的路由、OpenAPI 类型、统一客户端、资料资格边界、工作台、响应式页面和预览兼容结论保持不变，本轮没有重新审核这些范围。
- 整改报告中的 24 项正式测试、24 项兼容测试及浏览器证据是执行者证据；本报告没有把它们冒充为 r2 亲测。
- r2 亲测是原反例 4 项、新增直接边界 7 项、当前正式 24 项、兼容 24 项、typecheck、api:check、独立 build 和三条隔离浏览器分页路径。
- 未运行后端标准完整入口、模型评测、付费调用、第二环境或 WP-15。未操作、重启或更新 5180/5196。

## 6. 最终结论

ISSUE-001、ISSUE-002 均已关闭，没有发现本轮范围内的必须整改项。

**结合r1与本轮定点复核，WP-14限定正式前端范围REVIEW_PASS。**

该结论不记录用户接受，不改变 WP-14 的 `IMPLEMENTED_NOT_ACCEPTED` 状态，也不推进 WP-15。
