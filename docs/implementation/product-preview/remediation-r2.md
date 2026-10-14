# PREVIEW-003 剩余轮询分支整改 r2

状态：IMPLEMENTED_NOT_ACCEPTED，执行者自测完成，等待仅此分支的定点复核。不是审核关闭或用户接受。

## 范围与基准

本轮只修复 review-r2 指出的同 doc/vid 更换会话后旧轮询错误回写。写入前按 r2 清单及封存核对，未发现未解释差异；3229 项保护基准见 evidence/remediation-r2/baseline.json。结束核对只有下列三个既有文件变化，3226 项未变，Git index SHA256 保持 c451d6e78b8f29fc818002923a19fb1a888139ced20679ad545f75e9692a9ec6。主分支仍无 HEAD，命令原文另存。

- frontend/src/main.tsx：refresh 的成功/错误统一经过代次及生命周期守卫。自动轮询传入 effect 存活判断；新建预览会话现有即时 refresh 调用也进入同一路径。
- frontend/src/preview-context.ts：新增 guardedRefresh，每次调用捕获代次，错误仅在当前代次且存活时交付；成功回调使用同一个 current 判断。
- frontend/scripts/preview-context.test.mjs：保留原四例，增加六例测试生产刷新策略。

未改 effect 依赖集合，不通过反复重建 effect 清空编辑规避问题。未改后端、版本映射、WP-10算法、STATUS、原问题清单或接受记录。PREVIEW-004保持既有关闭结论。

## 根因及修复边界

原 refresh 成功有代次保护，但外层 catch 只判断 effect ended；同资料版本的新会话不会销毁该 effect。现在每次请求开始捕获代次，版本及任务成功写入同时检查 current，异常也使用同一判断。显式刷新没有 effect 的情况下仍检查组件存活及代次。当前真实错误保留 HTTP code/message 展示；不会全吞错误。

“新建预览会话”按钮沿用原产品语义：先清除旧会话上下文，下次检索才创建新的数据库会话；本次没有为验证改变此行为。按钮即时刷新已经实际执行，不能把清空会话ID描述为当场创建新数据库行。

## 本轮命令和结果

cwd 均为 E:/Work/xiutu-v5；开始/结束时间及退出码见 commands.json。以下均在最终三文件版本执行一次：

| 命令 | 结果 |
| --- | --- |
| node --test frontend/scripts/preview-context.test.mjs | exit 0；10通过，0失败/跳过/取消 |
| npm.cmd --prefix frontend run typecheck | exit 0 |
| npm.cmd --prefix frontend run build -- --outDir E:/Work/xiutu-v5/docs/implementation/product-preview/evidence/remediation-r2/dist | exit 0；独立输出，没有写frontend/dist |
| python -B scripts/probes/prepare_database.py --name xiutu_test_preview_240dc0e9cf95 | exit 0；全新隔离库 |
| python -B -m alembic upgrade head | exit 0；仅准备本轮隔离库，非迁移专项回归 |

构建/检查日志分别保存在 state-tests.log、typecheck.log、build.log；无本轮测试失败。一次查找不存在的 backend/app/api/preview.py 后通过 rg 定位已有 product_preview.py，仅为只读定位错误，不是测试失败。

## 实际页面验证

独立实例 http://localhost:9061，独立库/存储/访问令牌、独立 dist；与用户127.0.0.1主机cookie隔离。使用两份新合成Markdown和真实解析任务，不加载向量模型、不索引或付费调用。页面操作使用真实 React 构建与API；review_app.py仅在真实已授权版本读取返回后用 asyncio.Event 控制响应释放，120秒为夹具失败上界，不用于抢时机或延长产品超时。没有触发夹具超时。

control.py arm <id> <error|stale|success> 等待“held”后操作页面，再 control.py release；各命令 exit 0。timing.jsonl 记录真实200读取后的 held/released/returned。browser-checks.json 保存本轮页面DOM断言，截图 current-error.png、normal-poll.png。

| 页面路径 | 实际结果 |
| --- | --- |
| A已有会话，挂起旧轮询；同doc/vid点击新建预览会话，再释放503 | 未显示 old-session-error；即时刷新恢复真实当前版本。没有依赖effect销毁 |
| 当前上下文挂起轮询再释放503 | 页面明确显示 FIXTURE_POLL_ERROR · current-error，证明真实错误未吞掉 |
| 挂起A成功，选择B再回A，再释放带可辨识旧状态的成功响应 | 当前显示A正确版本、解析完成，未恢复注入的旧失败状态；生产守卫六例同时覆盖ABA及生命周期 |
| 当前候选JSON人工编辑，正常轮询经屏障释放 | 编辑标记保持，解析状态真实刷新 |

四个屏障实例各运行一次，无长时间sleep/人工抢窗口。浏览器观察与生产函数确定性断言分别保留，不把页面采样声称为每一帧监测。未重新运行接口22项、PDF链路、全仓、第二环境、BGE或E10。

## 隔离与剩余项

仅停止本轮9061实例已登记且创建时间匹配的API/worker进程，保留隔离库与存储供追溯。用户5180未重启、其frontend/dist哈希未变，结束health=200；**5180仍为旧版，本修复尚未部署到用户实例**。

旧报告、原反例、失败证据、STATUS、接受记录、迁移及原虚构资料保持不变。未读取私有.env、真实模型费用账本或调用付费模型；未提交推送，未进入WP-11。

PREVIEW-001大文件/提示、PREVIEW-002真实资料入口继续为原改进/需求；真实资料NOT_MET和既有限制保留。本任务参与整改，本文仅为自测交付，不声称独立审核。待用户安排此分支定点复核。
