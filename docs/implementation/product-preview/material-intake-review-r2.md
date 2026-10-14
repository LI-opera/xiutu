# INTAKE-001 定点复核 r2

结论：**INTAKE-001 RESOLVED；结合material-intake-review-r1未变部分，本轮资料接入改进达到限定范围REVIEW_PASS**。建议用户限定接受上传提示、明确资料性质及非虚构待核实解析入口；本报告不是用户接受或部署授权。

本任务参与过本轮实施、整改及r1审核；此次是同任务切换审核角色，不声称不同任务独立审核。没有修改实现、STATUS、接受记录、历史报告/证据或Git index。

## 基准与复用范围

开始核对整改delivery-hashes.json、seal.json共3398个去重保护文件（含两份清单自身），全部匹配；结束逐项复核无变化。index开始/结束均为`c451d6e78b8f29fc818002923a19fb1a888139ced20679ad545f75e9692a9ec6`。Git main无HEAD按实际记录于final-protection.json；未add/commit/reset/push。适用祖先/项目未发现AGENTS.md。

生产差异仅为三份声明文件：frontend/src/material-intake.ts、frontend/src/main.tsx、frontend/scripts/material-intake.test.mjs；对照整改implementation.diff和整改前副本，无额外后端或资格变化。

复用整改dist/index-Cm304vYO.js，其源码、依赖锁、构建命令/成功日志及产物SHA均在匹配封存内；本轮未重新构建或类型检查，不将历史构建宣称本轮执行。没有覆盖frontend/dist。r1的27项接口、PDF、非默认大小门禁、服务端审核/owner检查和补充1项继续引用，属于整改前证据；三份前端修改没有改变这些后端路径，不重复全量。

## 源码与实际页面接线

- material-intake.ts:22—29：UploadDraft包含真实File对象、nature及fields；selectUploadFile每次创建新空声明，包括同名文件，不做文件名相等推断。selectedUploadMetadata验证对象同一性后才调用原元数据构造。
- main.tsx:40—43、188：文件onChange实际调用setUploadDraft(selectUploadFile(...))；性质/字段更新仅作用于该草稿，未调用changeContext。不是只有测试辅助类而页面绕开它。
- main.tsx:110—115：普通提交使用绑定的File/草稿，专用样例仍走example明确元数据分支；成功后才changeContext。run.catch及finally不清空草稿，不在每次提交前无条件清空。
- 上传禁用条件仍包含!nature。已有代次/迟到保护未变。源码正则测试只作为接线检查，以下真实页面过程才是行为证据。

## 本轮执行

cwd均E:/Work/xiutu-v5，完整命令、时间及exit code见evidence/material-intake-review-r2/commands.json。

| 命令/检查 | 本轮结果 |
| --- | --- |
| node --test frontend/scripts/preview-context.test.mjs frontend/scripts/material-intake.test.mjs | **22通过，0失败/跳过/取消，exit0**，本轮只执行一次；state-tests.log |
| prepare_database.py --name xiutu_test_preview_3b82915c7c06；alembic upgrade head | 各exit0，仅准备本轮新隔离库，非迁移全套回归 |
| instance_runner.py start / stop | 独立localhost:3800，独立storage/凭据，API/worker；结束仅停止本轮登记且创建时间匹配的进程，库保留 |
| CUA连续浏览器路径 | 换文件/声明入库/失败保留通过；首次取证异常及一次有界补充检查分列如下 |

localhost与用户127.0.0.1按主机隔离cookie。复用既有xiutu-v5-postgres-1，标签及端口见service.json；未启动/重建/停止数据库。未运行27项接口、PDF/大小全链、364项、前端重建、第二环境或模型评测；无付费调用。

## 五项判定与本轮亲测

1. **新文件必须重新声明：PASS。** 用a/same.md填写来源R2-A-source、车型R2-A-model、2020—2022、R2-A-family/R2-A-code；换b/same.md（同名不同内容）。性质为空、来源为空、未声明时上传禁用；再选nonfiction后5个适配输入全空。原资料/会话URL、候选编辑及原文一致。
2. **synthetic换文件：PASS。** 选择synthetic，再选invalid.md；nature为空且上传禁用，没有隐式继承合成性质。
3. **B新声明实际保存：PASS。** 最后选择B，重新填写来源“SYNTHETIC R2-B declaration, no real source claim”和R2-B-model，通过页面实际POST上传。版本`a2aa16d0-9567-41a9-b3b0-c39a5c15ed53`真实GET显示仅上述B声明，年份/发动机均null，synthetic=false、source/license unknown。没有A或失败重试草稿字段；上传成功后旧候选清空。见browser-checks.json及B-metadata.png，不是模拟入库。
4. **同文件失败保留：PASS，有取证限定。** 在invalid.md填写nonfiction草稿，真实后端INVALID_MARKDOWN_ENCODING后，草稿前后相同、原URL/候选/原文及候选通过结果保持。本轮没有通过清空旧页面隐藏错误。首次取证异常与补充过程见下一节。
5. **不影响原上下文及专用入口：PASS。** 普通草稿为空时，“导入授权虚构样例”真实解析/审核/索引/检索并形成候选通过；这仅建立保护基线，不重做检索质量评测。随后文件选择/编辑不动该基线，成功上传B才切换。专用样例不读取普通草稿声明。

全部行为在新库、人工测试文件及当前封存构建验证；未操作用户实际PDF或5180数据。

## 首次异常、补充验证及证据版本

首次失败保留取证断言失败：预期车型R2-retry-model，读到R2-retry-modelw，同时没有捕获alert；其他原上下文仍一致。原对象以assertionFailed=true保留在browser-checks.json。**没有证据确认额外字符/未捕获错误的原因，也不将其直接解释为环境问题或产品已修复。**该次不能作为失败保留通过证据。

仅针对这一不完整取证补一次有界检查：明确填写R2-verified-retry并在提交前读回车型/来源，点击同一invalid文件上传，等待明确alert（上界10秒），再比较提交前后值。捕获INVALID_MARKDOWN_ENCODING，字段完全一致、原上下文和accepted保持。没有改实现、放宽断言或重启实例，没有循环重跑到通过；22项状态测试也没有再跑。该充分的前后观测与无重置的代码路径支持关闭本问题，首次异常继续保留供追溯。

历史r1为18项状态、27项接口、补充1项与浏览器反例；整改自测为22项及页面证据；本轮为新执行22项及上述连续页面过程。各轮不累加为不同功能覆盖数，不宣称最终版本全仓重跑。

## 限定接受建议及停止

本轮没有新增必须整改项。结合r1，可限定接受“服务端实际上传上限提示、普通上传明确声明、非虚构待核实解析/原文/切块及合成审核隔离”，INTAKE-001关闭。

大文件、220MB整本、分片、OCR、正式资料审核/检索、真实维修效果均未完成；真实资料NOT_MET及原截止未满足、历史SSE/Compose/启动根因未确认、Linux BGE限制等继续保留。此次修复不纠正历史误填元数据。没有接受完整前端包或推进WP11。

**5180仍为原已接受版本，本次资料接入改进和修复尚未部署。**用户服务/构建/数据库/资料/会话未修改。只新增本报告与复核证据、必要隔离运行工件；验证实例及临时浏览器标签已关闭。等待用户决定接受与部署。
