# 资料与提案预览：PREVIEW-003剩余轮询分支复核 r3

结论：**REVIEW_PASS（限定本地合成资料预览切片技术范围）**。PREVIEW-003剩余轮询错误分支关闭；PREVIEW-004沿用review-r2已关闭结论。建议用户按既有切片范围接受，技术复核不代表用户已经接受或修复已部署。

本任务参与了实施、整改及前次复核；本轮切换为审核角色并重新运行验证，不声称不同任务独立审核。

## 基准与保护

读取review-r2、remediation-r2、其封存/时序/测试记录及三个修改文件；上级和本项目相关路径未发现适用AGENTS.md。核对remediation-r2的delivery-hashes.json、seal.json及seal文件自身，共3255项当前匹配；开始/结束均无差异。详见 evidence/review-r3/baseline.json、final-protection.json。三文件是main.tsx、preview-context.ts、preview-context.test.mjs；本轮未改动它们。

Git main仍无HEAD；git-head.txt保留实际退出码，未因无HEAD跳过文件基准。Git index始终为c451d6e78b8f29fc818002923a19fb1a888139ced20679ad545f75e9692a9ec6。STATUS、接受记录、原问题清单、旧报告/证据、迁移和frontend/dist均未变。未修改旧项目。

## 代码核对

- frontend/src/preview-context.ts:10—19：guardedRefresh在每次调用开始capture代次；current同时判断alive与isCurrent；catch仅在current时调用错误处理。
- frontend/src/main.tsx:38—40、75—89：refresh把组件存活和调用方生命周期组合传入guardedRefresh；版本读取后、任务Promise.all后均检查current，成功不会跨代次发布。错误保留code/message，不是统一吞掉。
- main.tsx:95—96：自动轮询每次都调用refresh(doc,vid,()=>!ended)，清理时ended=true；依赖仍是session/doc/vid，未以重建effect规避问题。
- main.tsx:162、170：手动刷新及新建会话即时刷新均调用同一个refresh。新建会话先changeContext递增代次，再发即时请求；没有未保护的外层catch。按钮只重置会话范围，下次检索才建立新数据库会话，保持现有语义。
- 版本映射/后端未变化；不重开PREVIEW-004或WP-10判断算法。

## 本轮实测与原始证据

全新实例 http://localhost:5748，库xiutu_test_preview_b07152470b9e，独立存储、凭据及构建目录。localhost与用户127.0.0.1的cookie主机隔离；未操作用户5180标签或服务。

所有命令cwd为E:/Work/xiutu-v5，commands.json记录起止时间和退出码：

| 命令 | 本轮结果 |
| --- | --- |
| node --test frontend/scripts/preview-context.test.mjs | exit 0；10通过，0失败/跳过/取消 |
| npm.cmd --prefix frontend run build -- --outDir E:/Work/xiutu-v5/docs/implementation/product-preview/evidence/review-r3/dist | exit 0；包含tsc --noEmit；Node门禁通过 |
| python -B scripts/probes/prepare_database.py --name xiutu_test_preview_b07152470b9e | exit 0；新审核库 |
| python -B -m alembic upgrade head | exit 0；仅初始化审核库，不是重复迁移验收 |
| python -B .../evidence/review-r3/control.py arm <场景ID> <模式>；随后release | 各exit 0；每个场景一次 |
| python -B .../evidence/review-r3/instance_runner.py stop | exit 0；仅停止本轮登记且创建时间匹配的API/worker |

构建唯一提示：outDir在frontend项目根外，不会清空；这是刻意的构建隔离，没有使用emptyOutDir或覆盖用户dist。state-tests.log、build.log为本轮原始输出。

## 实际页面接线验证

审核夹具复用整改事件屏障代码，但实例、库、资料、访问凭据、时序及输出全新。真实服务先完成鉴权和版本读取200，再将该次响应暂停；通过显式release控制错误/成功释放，不依赖长sleep或人工抢时机。120秒仅为夹具失控上界，本轮没有触发。控制端点只在审核包装应用中，未进入业务实现。

| 场景 | 本轮观察和结论 |
| --- | --- |
| 同doc/vid挂起旧轮询→重置会话→释放错误 | 11:44:56 held真实200；页面重置后11:45:19释放503。旧r3-old-session未显示；即时刷新显示当前正确版本。PASS |
| 当前上下文轮询错误 | 11:45:41 held，11:45:44释放503；页面明确显示FIXTURE_POLL_ERROR · r3-current-error。PASS |
| A→B→A，再释放旧A成功 | 11:46:08 held，页面ABA完成后11:46:25释放带audit_stale标记的旧失败状态200。当前A仍显示正确版本及解析完成，没有恢复旧状态。PASS |
| 同上下文正常轮询 | 候选JSON写入“同上下文保留编辑”，11:46:48 held、11:46:51释放真实200后仍保留。PASS |

证据：timing.jsonl是服务端屏障时序；browser-checks.json是本轮浏览器动作后的DOM及断言；current-error.png、normal-poll.png为实际截图。状态测试还确定性覆盖生命周期清理与ABA成功回调；代码检查确认生产页面确实接入该策略，未仅靠辅助类测试判PASS。页面快照不是逐帧监测，不夸大为任意调度/浏览器实现的穷尽验证。

本轮没有失败，也没有改断言后重跑。使用两份明确合成Markdown只准备轮询上下文；不执行索引、模型、PDF、接口22项或历史全仓。

## 证据版本与总体范围

- r2对PREVIEW-004的4项source_mapping测试、旧v1命中原文定位及失败清理实测继续引用，相关实现及证据哈希未变，本轮没有重跑它们。
- remediation-r2的10项测试/浏览器记录是执行者自测历史。
- 本轮r3重新运行10项状态测试和四条页面屏障路径，不能与自测重复累加为功能覆盖数。
- 结合r1/r2未变部分，PREVIEW-003和PREVIEW-004均无剩余必须整改问题，切片达到限定REVIEW_PASS；不是重新审核WP-00—10或正式WP-14。

## 保留项与停止

PREVIEW-001大文件/提示与PREVIEW-002真实资料接入仍是原改进/需求，不扩大上传上限或放宽formal/synthetic门禁。真实资料NOT_MET、原截止要求未满足、E10既有限定结论、Linux BGE未验证、历史SSE/Compose/启动原因未确认及同任务流程限制继续保留。

**5180仍为旧版，修复未部署。** 结束只读health=200，用户frontend/dist哈希不变；审核5748已停止，隔离库/存储保留。未更改STATUS或接受记录，不付费、不读取真实模型账本、不提交推送，不进入WP-11。等待用户决定接受与是否部署。
