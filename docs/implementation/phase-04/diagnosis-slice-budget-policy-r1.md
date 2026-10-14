# 诊断闭环切片：共享账本计量策略变更

2026-09-20 用户明确取消原 DeepSeek 共享账本的累计人民币 5 元拒绝上限。本变更只改变累计拒绝策略，账本仍为原 `.local-data/wp09-budget.json`，未创建第二额度。原授权和历史 5 元值保留在账本 v2；新策略为 `metered_no_cumulative_cap`。原账本在跨进程锁内备份并原子迁移，18 条历史调用、各终态/usage 和累计保守预留 ¥2.329216 未变。原目录中的私有回退副本名为 `wp09-budget.json.v1-backup-agmnqjgo.json`，SHA-256 为 `8f0c9ae06706df5ce733ce693754a031ef3b5d82bda995793d6d3eb8ec81e1c9`。副本限制为本机管理员及 SYSTEM 访问；公开证据不包含账本或凭据。迁移后原账本 SHA-256 为 `34689b57dc351975e550f9b8dc5be7bd1cd6dcd3334cc8be39c97a4b38e70945`（真实验证前）。

修改 `model_budget.py`、`model_gateway.py`、`config.py` 及显式迁移脚本；同步 `.env.example`、模型运行说明、API 错误说明和定点测试。v1 账本在网关发送前明确拒绝，必须显式迁移；未知模型/价格、非法账本或参数、重复调用键、截止时间已过继续拒绝。每次请求仍按 payload 和输出上限计算保守预留，在原文件锁下先持久化；失败、超时和 usage unknown 不退款，usage 超过上界标记异常但不把累计强写成 5。现有诊断 turn 的四次模型请求、120 秒、工具/检索、一次修复和模型/API 白名单未放宽。请求不能指定账本策略。账本保守预留及 usage 估算不是平台账单；取消本地累计门禁不保证平台实际扣款上限。

免费验证：第一次定点收集因本轮引入的 `try` 语法错误 exit 2，原日志保留于 `.test-runs/diag-slice-metered-d1e6993f95114984b27146875675dff6/`，修正后预算/网关定点 42 passed（exit 0）；额外迁移失败及四请求限制 4 passed（exit 0）；最终坏账本反例 4 passed（exit 0）。独立跨进程预留、重启、重复键、usage unknown/越界、旧账本无损迁移、锁等待后过期不发送和诊断第五次不预留均在这些定点中覆盖。代码风格定点 `ruff check` exit 0。受影响来源扩展定点 7 passed（exit 0）；其缘由及实际业务结果另见 [真实验证记录](diagnosis-slice-live-r2.md)。未运行全仓完整入口。

回退必须先停止本轮付费调用，在受控维护窗口核对上述备份哈希，再恢复原文件及相应旧代码。不能直接把 v1 账本给当前 v2 网关使用。原 `git index` SHA-256 `C451D6E78B8F29FC818002923A19FB1A888139CED20679AD545F75E9692A9EC6` 未变；没有提交或推送。
