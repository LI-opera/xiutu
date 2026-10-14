# 资料与提案预览：5180部署 r1

结果：**DEPLOYED / 最小上线冒烟通过**。完成时间：2026-09-19T12:15:55.642685+08:00。

用户限定接受见acceptance.md；先记录接受，再部署验证，没有预先声称部署成功。不启动WP-11，不接受完整WP-14。

## 基准、构建与更新过程

r3交付及封存3279项开始匹配，Git index不变。未修改实现或安装依赖。

独立构建命令（cwd E:/Work/xiutu-v5）：
`npm.cmd --prefix frontend run build -- --outDir E:/Work/xiutu-v5/.local-data/product-preview/deployment-r1/new-dist`

exit0，含tsc及Node门禁；所有产物SHA256与r3/dist一致。主脚本index-C4HAaDd2.js，CSS index-BQxo7_Cx.css。完整记录见evidence/deployment-r1/build-command.json、build.log、new-build-hashes.json。

初始只读端口检查受沙箱限制，提权后成功；可选psutil未安装，改用Win32_Process，无依赖安装。首次只读DB快照超时，Docker引擎管道不存在、5433无监听，此时未停止5180、未切换，runtime及旧dist原样保持。pre-switch-blocker.json保留。用户表示会启动后，只读确认原xiutu-v5-postgres-1运行才继续，没有重建/修改数据库。此恢复不等于查明历史平台根因。

更新前PID7536为登记API16508的子进程，创建时间匹配；登记worker1780已退出，属于更新前状态。使用既有 `python -B scripts/product_preview.py stop`，exit0；保留旧dist后复制新构建；既有start，exit0。精确时间/命令见switch-commands.json。更新后API36660、worker35308均存活，ready200。真实HTTP根页面及全部静态资源hash匹配新构建。

文档收尾首次读取因Windows默认GBK失败，发生在写入前；改用PYTHONUTF8=1完成，未改产品代码，也非上线失败。

## 原数据与访问身份

原库xiutu_test_preview_a276917a3275、storage、actor、instance、port及原访问配置均保持；仅processes更新PID/创建时间。秘密只在私有内存比对，未封存令牌、Cookie、CSRF或连接串。未清空runtime、未init、未迁移、未新建替代库。

切换前后全部public表行摘要/数量及存储文件hash完全一致，见data-before.json、data-after-restart.json、storage-before.json、switch-result.json。上线冒烟后仅正常幂等记录12→13，其余行摘要不变；候选绑定复用了已有证据。不能将此写为冒烟后整库零变化，也没有删除历史资料。

## 最小上线冒烟

| 路径 | 本轮实际结果 |
| --- | --- |
| 原访问配置登录 | 200 |
| 原资料/版本/索引 | 原文档7ace8013-d4b0-4ea7-874d-260cb515555f、版本d7bb676a-c4e5-41bb-b17c-6e8672961ee0显示解析完成、已审核、索引就绪；formal_usable=false |
| 原会话检索 | 原case68260068-6cba-4c58-b760-a610bc9a12be，本地E5返回5项命中；未新建会话 |
| 来源映射和正文 | chunk24778e7d-8530-4964-b7bf-a935e1cec6b1映射至原document/version；内容200，hash=e4896ccde323186e8c2c01ca5187b3edfa25977b5a74cb6be45f1a682dedd888与版本一致 |
| 人工候选 | 当前位置表命中→有据区域→校验，accepted=true、disposition=candidate、published=false；不是诊断成立或AI生成 |

browser-smoke.json与http-smoke.json保存必要结果，无正文/秘密。没有重跑历史测试、轮询反例、PDF链路、BGE评测或E10，无付费调用。

## 回退及停止点

旧构建位于 `E:/Work/xiutu-v5/.local-data/product-preview/deployment-r1/previous-live-dist`，另有old-dist备份。runbook中命令只回退前端并调用既有stop/start，不改变数据身份、不恢复旧PID列表。失败自动回退路径已准备；本轮上线成功，未触发或主动演练回退。

**5180现在运行已审核修复版。** 用户请刷新已有标签，必要时用原access.txt重新登录；重启令旧会话cookie失效，本次冒烟登录也可能更新Cookie。只关闭本次检查标签，服务继续运行。

本次新增接受/部署记录及证据，更新STATUS切片记录、runbook和授权frontend/dist。历史报告/证据、issues.md、旧迁移、旧项目和Git index未修改。PREVIEW-001/002仍待处理，真实资料NOT_MET及原截止未满足、同任务限制、Linux BGE未验证及历史未确认根因保留。未提交推送，不进入WP-11。
