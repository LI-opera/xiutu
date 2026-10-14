# 本地资料与提案预览：体验步骤

这是顺序前置的产品验证切片，不是正式WP14或诊断台。持续使用虚构资料，仅作技术体验。

## 打开与登录

2026-09-19已按用户授权更新到r3审核修复构建，部署冒烟通过，见[deployment-r1.md](deployment-r1.md)。本轮已经启动：<http://127.0.0.1:5180>。用私有文件 `E:\Work\xiutu-v5\.local-data\product-preview\access.txt` 中的令牌登录；不要把令牌粘到报告、URL或聊天中。页面不保存令牌；同源HttpOnly登录cookie按原契约管理，重启API后重新登录。

## 一条体验流程

1. 选择已导入的“冷却系统 · 用户虚构原文”，或点击“导入授权虚构样例”。后者从已授权原样副本上传，源文件不变。也能选择本地Markdown/PDF，全部进入该隔离synthetic库。
2. 等待真实解析任务显示完成。新上传文件勾选“仅确认本地合成演示源”，再点击审核并索引；这是演示源确认，不是维修专业审核或规则审批。已审核样例无需再提交。
3. 输入 `P01 电动水泵 位置`，点击检索。首次创建服务端冻结范围的会话；本轮位置表排第3，按内容找表头“部件 / 虚构位置”。排名不作为固定契约。
4. 选择该表格命中。点“有据区域”，等候选JSON出现后点“校验候选”：应为accepted=true、disposition=candidate、published=false。这里是区域候选，不是正式诊断结论。
5. 分别点“原文句式限制”“引用不支持主张”“缺少正式规格”，查看实际JSON后再校验。预期包含LOCATION_UNCERTAIN、CLAIM_UNCERTAIN、SPEC_REQUIRED等；其他必要字段缺项会一并显示，不制造单一错误假象。
6. 从具体问题点“查看本候选依据”，打开不可变版本原文与高亮；可展开locator。多个依据全部列出，链接不是系统声称该引用支持该错误字段。
7. 刷新页面后资料/版本/会话ID由URL恢复，解析/索引从服务器重读。候选编辑与校验结果不持久化，需重新选择命中并校验。API重启会使原登录失效，但DB和原文保留。

选择资料用于查看其版本；检索覆盖会话冻结的全部合格资料，不是浏览器任意指定的版本allowlist。新上传/审核资料不会自动扩充旧会话，点击“新建预览会话”后再检索。

## 启动与停止

在PowerShell中执行（不加载私有.env）：

```powershell
Set-Location E:\Work\xiutu-v5
.\.venv\Scripts\python.exe -B scripts/product_preview.py status
.\.venv\Scripts\python.exe -B scripts/product_preview.py start
# 使用完成后，仅停止该脚本核对PID及创建时间的API/worker及其子进程：
.\.venv\Scripts\python.exe -B scripts/product_preview.py stop
```

本轮已完成init，不要删除runtime.json重新初始化。首次无状态的部署需已有xiutu-v5专用Postgres容器与本地E5、现有venv/锁定Node依赖：先 `npm --prefix frontend run build`，再 `python scripts/product_preview.py init` / `start`。init创建全新xiutu_test_preview_*库和UUID存储目录；既有状态拒绝覆盖。脚本不启动Docker、不改既有角色密码、不清数据或卷；端口占用拒绝接管。复用受保护的`.local-data/wp01-postgres.json`仅供本地连接，不读取旧.env或模型费用账本。start有30秒上界；排查仅看本轮`.local-data/product-preview/`私有日志，分享前先脱敏。

## 范围与复现检查

- `python -B scripts/export_preview_types.py`：从实际preview OpenAPI生成TypeScript schema。
- `python -B scripts/verify_product_preview.py`：新库/新目录运行本切片18项接口测试；不会重跑历史全仓。测试位于tests/product_preview，专用库前缀约束不加入旧包的通用库入口。
- `npm --prefix frontend run typecheck` / `npm --prefix frontend run build`：Node门禁、类型与构建。
- PDF沿用已有解析/原文件接口；正常合成文本PDF有r1审核证据，本次部署仅做原Markdown资料冒烟，未重复PDF/OCR回归。扫描页仍needs_ocr。
- 本切片没有安装可信结论规则，没有AI生成按钮或模型调用；可编辑JSON不是可信规则入口。待补不是维修故障判定。


## 本次更新与回退（deployment-r1）

切片限定ACCEPTED；PREVIEW-003依据r3关闭、004依据r2关闭，001/002仍待处理。当前主脚本index-C4HAaDd2.js与r3审核产物逐字节一致。

旧版位于 `.local-data/product-preview/deployment-r1/previous-live-dist`，另有old-dist备份，新构建在new-dist。runtime-before.json仅为私有比对副本，包含秘密，不分享或覆盖当前runtime。

如需回退前端（短暂停止5180）：

```powershell
Set-Location E:\Work\xiutu-v5
.\.venv\Scripts\python.exe -B docs/implementation/product-preview/evidence/deployment-r1/deploy.py rollback
```

仅调用既有stop/start，保留当前库/存储/访问配置；新构建保留为retired-new-dist-*，旧构建复制回frontend/dist。不执行init，不恢复旧PID，不删除库卷。仅回退前端，后端保持已审核代码。本轮成功后没有主动演练回退。

API重启后请刷新原标签，必要时用原access.txt重新登录；本次同主机冒烟登录可能更新Cookie。原URL的doc/version/case保留，候选编辑不跨刷新保存。


## 资料性质与上传提示：实施期历史说明（现已部署，见下节）

见material-intake-contract.md、material-intake-result.md。本次新构建仅在独立8198实例验证，已停止；5180仍为上一轮已接受的版本，尚无本次新表单。不要直接在5180重建dist或重启来体验，需先检查及另行部署授权。

新表单从服务端读取大小上限。普通文件需明确选合成或非虚构待核实；未知来源/许可保持unknown，非虚构车型等可留空。专用授权虚构样例入口保留。非虚构文件只能解析、查看元数据/原文/切块，不能通过合成审核或进入合成检索。误填性质不自动改历史，需重新正确声明；非虚构声明不是内容真实性/许可证明。

现有5180启动脚本从工作区加载后端代码，未来重启应按新交付审核/部署流程处理；本轮没有执行该实例重启。新版本没有新增运行依赖、迁移或收费调用。


## 当前版本：资料接入改进已接受并部署

以material-intake-acceptance.md及material-intake-deployment-r1.md为当前记录。5180现在使用index-Cm304vYO.js及匹配的预览后端。上方8198/未部署描述是实施期历史，不代表当前状态。

刷新http://127.0.0.1:5180，必要时使用原私有access.txt登录。普通上传每选一个文件均需重新声明性质；填写来源/适配可明确未知。非虚构仅待核实解析/原文/切块，不得合成审批/正式检索。专用虚构样例入口保持。页面以服务端实际上限为准，不支持超限整本、拆书、分片或OCR。

本次回退请使用material-intake-deployment-r1.md的deploy.py rollback，而非上方旧部署的仅前端回退命令。新回退同时使用previous-dist及已核对的旧backend快照，保持当前runtime身份和数据，需操作授权。回退后普通start会加载工作区新代码，不要混用。此次只准备预案，没有演练回退。
