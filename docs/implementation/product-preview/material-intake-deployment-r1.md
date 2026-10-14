# 上传提示与资料待核实入口：5180部署 r1

结果：**DEPLOYED / 必要上线冒烟通过**。完成时间：2026-09-19T14:16:11.059783+08:00。限定接受先记录于material-intake-acceptance.md，部署结果单列；没有预先宣称成功。

## 基准与准备

r2交付/封存及源码构建匹配，无未解释差异。复用整改审核构建，不重新安装依赖或构建：JS index-Cm304vYO.js、CSS index-BQxo7_Cx.css，完整hash见evidence/material-intake-deployment-r1/build-backend-hashes.json。旧frontend/dist先备份，再将审核产物复制至私有new-dist，校验后切换。

后端入口当前SHA256 `fc124b23d892413c47a1d95b188790b4b883f301a321eac29595e7fd258474a2`，与r2基准相同。通过既有scripts/product_preview.py启动，PYTHONPATH指向审核的backend；重启后preview/config实际返回upload_max_bytes，旧版没有该字段，运行响应及构建检查共同确认加载此次服务。未改变后端代码。

旧后端入口从本包新增差异反向恢复到隔离副本，并逐字节匹配改进前封存SHA256 `60106c57b5317cc34e6d7585c68d8149fdb08ab2b44329d97d652ba5abce3037`；其余backend复制为私有快照，未覆盖工作区。备份专用样例及回退启动器，确保不是仅前端回退。

## 切换与数据身份

部署脚本核对原登记API PID/创建时间及5180监听者为该PID或子进程；确认原xiutu-v5-postgres-1运行，并且原库无queued/running任务，才继续。使用既有stop/start，仅短暂停止预览API/worker；没有停止数据库或未知服务。

命令cwd E:/Work/xiutu-v5：

`python -B docs/implementation/product-preview/evidence/material-intake-deployment-r1/deploy.py switch`

exit0。内部stop/start精确时间/退出码见commands.json，启动日志保留。未执行init、迁移、建库或清库。原库xiutu_test_preview_a276917a3275，原storage、actor、instance、port及访问配置保持，仅processes换新PID/创建时间。私有runtime备份未进入证据包。

重启前后所有public表行摘要/数量与storage文件hash完全一致；实际HTTP首页和assets逐个hash与审核产物相同。见data-before.json、storage-before.json、identity-before.json、switch-result.json。旧构建通过目录重命名保留，没有删除历史数据。

## 必要冒烟

- 原凭据登录200、ready200；原文档7ace8013-d4b0-4ea7-874d-260cb515555f、版本d7bb676a-c4e5-41bb-b17c-6e8672961ee0及原会话68260068-6cba-4c58-b760-a610bc9a12be可读；原文hash仍e4896ccde323186e8c2c01ca5187b3edfa25977b5a74cb6be45f1a682dedd888。
- 原会话真实合成检索5项命中，点击原定位片段并绑定有据区域，候选accepted=true，仅候选通过、published=false，不是诊断发布。
- 页面显示服务端实际26,214,400字节（25.00 MiB）上限及新性质入口。仅选择两个同名人工测试文件，填写第一份草稿后换第二份，性质/来源清空且上传禁用；**没有提交或导入这些文件**。
- 当前已有非虚构资料数量为0，因此该分支不另行制造资料；限制验证沿用r1证据，不冒称本次上线再次验证非虚构入库。
- 浏览器和HTTP证据分别见browser-smoke.json、http-smoke.json。冒烟后数据库变化仅 `{'idempotency_keys': {'before': 14, 'after': 15}}`，为候选依据正常幂等请求记录；其余表行摘要保持。没有改历史资料声明或原会话范围。

本轮没有重跑历史测试、PDF全链、模型评测或付费调用，没有读取费用账本。

## 回退（前端与后端一起，需另行操作授权）

私有目录：`E:/Work/xiutu-v5/.local-data/product-preview/material-intake-deployment-r1`。

- previous-dist：切换前已接受前端；retired-original-dist也保留原目录；new-dist为本次审核构建。
- backend-snapshot/backend：旧预览后端入口及对应其他模块；rollback_entry.py使用该backend和previous-dist，继续使用**当前runtime中的原数据库/storage/访问身份**。不恢复旧PID列表、不回滚数据库、不改工作区业务代码。

```powershell
Set-Location E:\Work\xiutu-v5
.\.venv\Scripts\python.exe -B docs/implementation/product-preview/evidence/material-intake-deployment-r1/deploy.py rollback
```

此脚本只停止当前登记的预览进程，保留当前dist为retired-dist-*，恢复previous-dist，并在独立PYTHONPATH中启动旧backend快照及worker；重新登记PID，30秒有界ready检查。**不是单纯前端回退**。旧服务不含本次非虚构门禁，回退等于撤回本次改进，不应继续以新入口能力说明它。普通scripts/product_preview.py start仍加载工作区新后端，回退后不要混用；恢复新版本须重新按部署流程操作。

本次切换及冒烟成功，未触发/演练回退；不将准备好的预案写成实际回退测试通过。如回退启动仍失败，保留日志并停止扩大操作，不重建数据库。

## 当前停止点

5180保留运行，用户刷新页面，必要时用原access.txt重新登录。此次重启使旧登录失效，冒烟也在同主机登录，用户可能需刷新/重新登录。测试标签已关闭。

仅新增接受/部署文档及证据，更新STATUS本项、runbook及授权frontend/dist；源码、历史报告/证据、旧项目、迁移和Git index未变。PREVIEW-001/002只完成指定子项，大文件/OCR/正式资料审核检索、真实资料NOT_MET及原截止未满足、同任务流程限制、首次取证异常与其他历史未确认根因保留。未提交推送，不进入WP11。

收尾保护检查首次因清单混用正/反斜杠而拒绝授权路径比对；实际均为同一frontend/dist路径。原报告列表保存protection-first-check.json，规范化路径后无未授权变化；不是服务失败或源码差异。回退入口只做语法验证，未启动回退。
