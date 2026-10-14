# WP-00 执行结果

工作包：WP-00。状态：**IMPLEMENTED_NOT_ACCEPTED**。日期：2026-09-18，Asia/Shanghai。独立审核和用户接受均尚未发生；本文件不是 review。

## 执行基准和范围

完整读取用户指定5份文档（以 docs/参考 内的总指南为准）及适用 AGENTS 检查。阶段总表明确纠正总指南“所有包 NOT_STARTED”的歧义：本包待验收，WP-01—17 未开始。旧目录 E:\Work\v4-double 无 Git；新目录创建前不存在，独立 main 分支，HEAD 尚无提交。交付文件暂存，审核用 git diff --cached；没有推送远程。

变更：README.md、CHANGELOG.md、.gitignore、tests/README.md、scripts/wp00_baseline.py、scripts/wp00_backup.py、docs/adr/0001-scope.md、docs/implementation/STATUS.md、phase-01 下 baseline.md、source-manifest.csv、data-readiness.md、本结果及 evidence。仅 WP-00 辅助脚本和记录；无业务接口/状态契约实现，无应用代码迁移，无新 .venv/.env/依赖安装，无 WP-01 探针。

## 实际执行与结果

1. 旧测试使用旧解释器、独立新目录，67 passed / 1 warning，失败/错误/跳过均0，退出0。第一次隔离器误阻断 socketpair 导致50 setup errors；保留 attempt-01 证据，修正新脚本后重跑成功。旧源码与文档53文件哈希前后一致。
2. SQLite backup API 创建一致备份，独立目录恢复，integrity_check=ok；5张表 schema/行数一致；数据库、两份语料、三份虚构样例和两张外部图共8文件全部哈希一致。未直接复制运行中的源数据库。
3. 资料清单7行：实际语料2 Markdown、旧根3虚构样例、外部引用2 PNG。全部授权未知，真实车辆范围未确认，不支持正式维修效果声明。
4. 新仓库/忽略规则建立；密钥、业务库、环境、资料、备份与临时目录不进暂存区。SHA256 清单和备份 manifest 只包含元数据，不包含密钥值或业务记录正文。

### 已运行命令（在 PowerShell）

```powershell
$py = 'E:\Work\v4-double\.venv\Scripts\python.exe'
& $py -B E:\Work\xiutu-v5\scripts\wp00_baseline.py --old E:\Work\v4-double --run E:\Work\xiutu-v5\.test-runs\wp00-20260918-02 --evidence E:\Work\xiutu-v5\docs\implementation\phase-01\evidence
& $py -B E:\Work\xiutu-v5\scripts\wp00_backup.py backup --database E:\Work\v4-double\data\diagnostic.db --documents E:\Work\v4-double\data\repair_docs --attachments E:\Work\v4-double\data\attachments --extra-file "E:\Work\v4-double\虚构维修手册式横向诊断树.md" --extra-file "E:\Work\v4-double\虚构分区式维修树交互原型.md" --extra-file "E:\Work\v4-double\冷却系统完整清晰维修树（虚构交互样例）.md" --extra-file "C:\Users\Administrator\AppData\Roaming\Typora\typora-user-images\image-20260903222136740.png" --extra-file "C:\Users\Administrator\AppData\Roaming\Typora\typora-user-images\image-20260903222223621.png" --output E:\Work\xiutu-backups\phase-01-20260918-0115
& $py -B E:\Work\xiutu-v5\scripts\wp00_backup.py restore --backup E:\Work\xiutu-backups\phase-01-20260918-0115 --output E:\Work\xiutu-backups\restore-20260918-0115
```

以上路径已经存在，脚本会拒绝覆盖；复核重跑时必须换新的 run/output 目录，并为 baseline 的 evidence 使用新目录（先创建），不要覆盖本次证据。pytest 实际参数和时间见 legacy-test-summary.json；脚本调用原 tests，关闭 cache，写 JUnit。独立恢复没有启动旧业务服务，因此验证的是备份可读、完整性/schema/行数/哈希，不冒充新产品恢复验收。

备份路径：E:\Work\xiutu-backups\phase-01-20260918-0115。
恢复路径：E:\Work\xiutu-backups\restore-20260918-0115。
测试目录：E:\Work\xiutu-v5\.test-runs\wp00-20260918-01 和 -02，均保留。

## 仍缺什么和影响

- 原始PDF及版次/许可、精确车型/年款/发动机代码、对应 DTC/位置/测量条件/线路针脚/数值标准/拆装修复/完工复核章节：均未确认或缺失。详见 data-readiness 的逐项影响表。真实资料充分性 NOT_MET。
- SRC-001 两张相对PNG仍缺失。SRC-002 两张外部Typora图已在用户明确回复“允许复制并验证”后补入私人备份并恢复校验。此前自动审批拒绝曾阻止复制；现已按新增授权完成，无待批准复制项。图片保存在 supplemental，未改写原稿中的旧绝对路径，恢复映射见 manifest；不声称原稿链接已自动修复。图片视觉内容/权属仍未审核，备份授权不等于公开分发许可。
- 无人工资料/权属审核者确认，无真实检索标注集或效果指标。本包只完成清点，不虚构接受结果。
- DeepSeek configured=true 仅表示配置存在；真实 DeepSeek 调用 NOT_VERIFIED；MCP NOT_VERIFIED。未付费探测，也未提前做 WP-01 离线/在线探针。
- 旧目录无 Git，不能回溯历史 diff；本次前后哈希证明覆盖文件未改变。旧服务活跃（PID5328，父PID13004为旧.venv解释器），未停止；系统查询首次沙箱权限不足，提升为只读后确认。没有变更旧端口/配置。

## 审核者可操作入口

按 P1/02 清单 B01—B11 独立审核，不照抄本结果作为 PASS：

- B01/B02/B03：baseline.md、preflight.json、legacy-service.json、legacy-hashes-before/after.json、legacy-test-summary.json、legacy-pytest.txt、legacy-junit.xml；另保留 attempt-01。
- B04/B05：scripts/wp00_backup.py、evidence/backup-manifest.json、restore-verification.json；访问上方实际备份/恢复路径，重新做独立恢复。
- B06/B08：source-manifest.csv、data-readiness.md、ADR-0001，按文件/章节抽查；unknown 和合成标识不得改为已授权/精确适配。
- B07/B09/B10/B11：git status --short --branch、git diff --cached --stat、git diff --cached、.gitignore、STATUS、README；核对只有当前包文件。

本包停止，等独立审核与用户接受。不创建审核通过记录，不写阶段 ACCEPTED，不开始 WP-01。下一包拟验证依赖与基础技术，但当前未授权执行。

初次仅配置数据的备份/恢复仍保留于 `E:\Work\xiutu-backups\phase-01-20260918-0107` / `restore-20260918-0107`；其证据存 evidence/backup-initial。当前有效脚本版本1.1与最新8文件备份对应；旧快照版本1.0单独保留历史记录。

## 交付前复核补记

测试运行期间53文件哈希完全一致；交付前再次扫描发现旧计划文档并行变化，非本任务写入。变更：docs/参考/00-阶段总表与使用方法.md；新增：docs/参考/P2/01-第二阶段实施说明.md, docs/参考/P2/02-第二阶段验收清单.md, docs/参考/P3/01-第三阶段实施说明.md, docs/参考/P3/02-第三阶段验收清单.md, docs/参考/P4/01-第四阶段实施说明.md, docs/参考/P4/02-第四阶段验收清单.md, docs/参考/P5/01-第五阶段实施说明.md, docs/参考/P5/02-第五阶段验收清单.md, docs/参考/P6/01-第六阶段实施说明.md, docs/参考/P6/02-第六阶段验收清单.md。已重读更新后的阶段总表，WP-00边界及状态规则没有变化，不自动执行新增计划。业务源码/原脚本/原测试/依赖模板未变化。详见 evidence/legacy-final-inventory.json。

备份脚本实测补充：含补充资产的合成往返、拒绝已有备份/恢复目标、拒绝篡改备份均通过；当前真实恢复8文件及脚本SHA256再次匹配。记录见 evidence/wp00-script-checks.json。

Git核对：忽略规则实测排除 .env/.env.local、环境、node_modules、业务库、备份、日志、私有资料、测试临时目录和PDF；.env.example 允许。实际密钥值仅在内存中用于扫描交付文档/脚本，未发现泄露，未输出值。首次 diff --check 提示原始失败日志的空白及已执行脚本的末尾空行；通过 .gitattributes 保留原始证据/脚本字节，不清洗测试输出、不改变已备份脚本哈希。仅对这些工件放宽空白检查，普通文档继续检查。交付新增 .gitattributes 用于此用途。
