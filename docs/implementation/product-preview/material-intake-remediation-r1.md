# INTAKE-001 定点整改 r1

状态：**IMPLEMENTED_NOT_ACCEPTED**。仅执行文件选择与声明绑定整改，等待定点复核；不是审核关闭、接受或部署。完成日期：2026-09-19。

## 根因与最小修改

旧main.tsx文件选择只setFile，性质/来源/适配为独立持久state，因此换文件（包括同名文件）会复用上一份声明。

仅修改三份前端文件：

- frontend/src/material-intake.ts：新增UploadDraft，将File对象、nature和全部fields放在同一草稿。selectUploadFile每次实际选择都创建空性质和新空fields，不按文件名/大小比较，不复用声明。selectedUploadMetadata在普通提交时验证File对象与草稿关联，再复用原intakeMetadata。
- frontend/src/main.tsx：文件onChange实际调用selectUploadFile；性质及字段编辑只更新该草稿。普通上传消费selectedUploadMetadata；专用授权样例仍走原明确元数据分支，不依赖普通草稿。
- frontend/scripts/material-intake.test.mjs：新增4项，覆盖同名不同文件、synthetic后重新声明、失败草稿/重试及生产页面选择/提交接线；保留原8项断言。原上下文10项一并运行。

选择文件/编辑草稿不调用changeContext，也不清除已加载资料/会话/候选/原文。提交和catch不重置草稿；同一选中文件失败后可以修正声明再试。仍只有实际上传成功后切换资料上下文。没有自动复用声明、后端资格变更、迁移或历史元数据修正。

implementation.diff为本轮前后真实差异；本轮baseline.json保存整改前文件与审核封存SHA256。原material-intake-review-r1及其失败反例、截图、断言均保持不变。

## 实际验证及命令

cwd：E:/Work/xiutu-v5；精确argv、开始/结束时间、退出码见evidence/material-intake-remediation-r1/commands.json。

| 执行 | 本轮结果 |
| --- | --- |
| node --test frontend/scripts/preview-context.test.mjs frontend/scripts/material-intake.test.mjs | **22通过，0失败/跳过/取消**，exit0；含新增4、原接入8及上下文10 |
| npm.cmd --prefix frontend run build -- --outDir E:/Work/xiutu-v5/docs/implementation/product-preview/evidence/material-intake-remediation-r1/dist | exit0，包含tsc --noEmit及Node门禁；JS index-Cm304vYO.js；未覆盖frontend/dist |
| prepare_database.py --name xiutu_test_preview_d13965e3ecd2；alembic upgrade head | 各exit0，仅准备本轮空库，未修改迁移或演练历史迁移往返 |
| instance_runner.py start / stop | 本轮独立API/worker启动；结束仅按登记PID及创建时间停止自己的进程，库/存储保留 |
| CUA浏览器连续路径 | 见下表及browser-checks.json、B-metadata.png |

没有重跑27项接口、364项全仓、PDF/大小边界全链、第二环境、BGE或E10。没有模型付费调用。本轮浏览器为本地E5复用已有功能建立需保护的有效资料上下文，不重做选型或质量评测。

## 实际页面与提交结果

独立http://localhost:9632，数据库xiutu_test_preview_d13965e3ecd2，独立storage、凭据及构建（路径指针见instance.json）。localhost与用户127.0.0.1隔离cookie。只用合成测试载荷。

1. 普通草稿为空时使用“导入授权虚构样例”，真实解析/演示审核/索引/检索可用，构造并校验合法候选；证明专用入口不依赖普通草稿，建立需保持的会话、命中和原文。
2. 选择fixtures/a/same.md，填写A全部声明（source/model/两个年份/family/code）；再选择fixtures/b/same.md，文件名相同而内容不同。nature为空、来源为空、重新选择nonfiction后5项适配输入均为空；未声明时上传禁用。原会话URL、候选编辑和原文逐字一致。
3. 选synthetic后改选invalid.md，nature重新为空、上传禁用。给同一invalid文件填写nonfiction、Retry-source、Retry-model后提交，后端实际INVALID_MARKDOWN_ENCODING。性质/来源/车型草稿仍在，所选文件仍为invalid.md，重试按钮可用；原URL、候选编辑、原文和候选通过结果保持。
4. 再选B，重新声明nonfiction、B-model和B专属来源，其他字段留空，实际上传。版本`3dee848c-b515-4aaa-8d44-3c05d7b43e6b`页面从真实GET返回的metadata为：synthetic=false、model=B-model、来源=SYNTHETIC B declaration; not a real manual，年份/发动机均null、source/license均unknown；没有A或Retry字段。成功后原候选/accepted清空。

browser-checks.json保存上述状态及实际提交后的版本读取结果；并未抓取或封存带Cookie/CSRF的完整请求头。元数据证明来自真实界面POST及数据库版本GET，不是模拟保存。B-metadata.png仅包含人工测试声明。

## 失败证据与版本

状态测试和构建首轮通过，无修正后循环重跑。浏览器一次取证试图读取input.files[0]，只读DOM接口未暴露files导致TypeError，发生在取证阶段；已记入browser-checks.json。随后读取页面实际文件名及原有字段，保留同一失败上传状态，未重跑该上传、未改产品代码或弱化断言。真实无效编码失败是预期反例，原错误和保持结果均记录。

历史审核的18项、27项及补充1项仍属于整改前版本；本轮仅22项状态及页面路径，不宣称整改后完整回归。

## 保护与停止点

结束比对只有上述三份前端实现/测试发生授权修改；历史报告、审核证据、接受记录、STATUS、后端、迁移和用户frontend/dist均未变。Git index保持`c451d6e78b8f29fc818002923a19fb1a888139ced20679ad545f75e9692a9ec6`。final-protection.json记录完整核对。

本轮实例已停止，**5180仍为原已接受版本，本次修复未部署**。没有停止/重启用户服务，没有改用户数据库/资料/会话；没有提交推送、读写费用账本或进入WP11。

PREVIEW-001大文件、PREVIEW-002正式资料审核平台/真实检索等未实施需求继续保留；真实资料NOT_MET与既有未确认根因不变。修复不自动纠正此前误填的历史版本元数据。完成后停止，交用户安排仅INTAKE-001定点复核。
