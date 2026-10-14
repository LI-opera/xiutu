# DKVB-001部署 r1

时间：2026-09-19T16:25:32.834689+08:00。结果：**已部署到现有5196并完成必要冒烟**。限定接受见[接受记录](dkvb-topic-acceptance.md)，接受与部署分别记录。本轮没有实现、审核或接受新功能。

## 核对与切换

r2对应4926项保护记录匹配（含r2报告/证据），原资料包及前端封存匹配；main无HEAD沿用实际状态，不修改Git index。无未解释代码差异。原5196 API PID12172的创建时间及uvicorn入口核实；5433数据库连接正常、Docker项目归属xiutu-v5，queued/running任务为0后才切换。

先建立私有回退目录：`E:\Work\xiutu-v5\.local-data\dkvb-topic\rollback-dkvb001-20260919-162049`。含现用前端dist、后端副本及runtime-private.json（含凭据，不得公开/封存到证据包）。后端副本以当前匹配代码加原r1封存dkvb_preview.py恢复旧映射实现；没有改写工作区代码。前端没有改动，不构建、不切换。

仅按PID和创建时间停止原API，启动已审核当前后端，更新runtime.json中的API进程登记，保留其余身份配置；新API PID33888。未运行原脚本的全实例stop/start（会连带worker），未init/import/迁移、创建库或重建索引。新API有界健康检查通过。

首次只读快照脚本误用chunk_embeddings.id排序，SQL失败发生在接受/备份/停止服务前；仅修正部署证据脚本为整行稳定排序。失败说明保存在preflight-initial-failure.txt，不属于业务代码修复。

## 冒烟与保留

独立httpx客户端使用原身份登录，自己的Cookie jar不触及用户浏览器；结束注销该客户端。实际请求包括health、登录、原case读取、topic读取、静态资源读取、两次BGE检索、chunk定位、PDF及页图读取。未新增资料、会话或索引。

- 原5份资料可读，使用既有会话 `084417a3-e8e5-4e4c-ad06-57bd339eae01`，未创建替代会话。
- 标题通过真实检索命中，pages=[]、simulation_specs=[]。
- 正常FS-02命中对应S02物理第6页，PDF SHA256匹配，PNG完整页图1061×1500。
- 实际HTTP静态资源hash与审核构建一致：index-Cm_Gkvfa.js / index-BQxo7_Cx.css。
- database=`xiutu_test_preview_dkvb_a0f2f43b4a`，storage=`E:\Work\xiutu-v5\.local-data\dkvb-topic\storage`，dist=`E:\Work\xiutu-v5\.local-data\dkvb-topic\dist-sealed`保持不变。registry、storage文件hash、访问身份配置hash不变。
- documents/document_versions/chunks/index_versions/chunk_embeddings/cases/jobs/runs八表行数及完整行摘要前后相同。登录/检索等产生正常请求及内存认证会话，不声称整库及全部运行状态零变化。
- 5180 PID8820及创建时间未变；未修改其构建、配置、资料或登录。

命令cwd=E:/Work/xiutu-v5：`python -B evidence目录/prepare.py`退出0；`python -B evidence目录/deploy.py`退出0（内部健康与smoke通过）。详细时间、原/新进程、hash和结果见preflight.json、deployment.json、final-protection.json、deploy.log。未追加全仓测试或审核轮次。

## Worker运行现状

runtime登记的worker PID33836已不存在；最新既有worker日志时间为15:58:51，早于本次16:20后的部署。最终核对发现，不能写成worker仍健康运行；本轮未对worker发停止/启动指令，未更改其登记。现有索引检索/原页接口已验证可用，无活跃任务。本次仅API修复不需要worker；未来新增解析/索引前需要另行核查并恢复worker。未借此扩展修复，也不把历史数据库中断根因称为已解决。

## 运行与回退

体验：[http://localhost:5196/#dkvb](http://localhost:5196/#dkvb)。API重启使旧内存认证会话失效，用户请刷新并用原access.txt令牌重新登录；令牌没有轮换，不在报告显示。数据库中的原会话仍保留；页面既有限制为刷新后不自动恢复会话，可按原流程新建专题检索会话。

现有实例查询/停止仍可使用scripts/dkvb_topic.py status/stop。注意start是全实例启动且有存活进程保护，不应在当前API运行时直接执行，也不要再次init/import。

若需回退本次API：在项目根执行 `.venv\Scripts\python.exe -B docs/implementation/product-preview/evidence/dkvb-topic-deployment-r1/deploy.py --rollback`。它先确认原身份及无queued/running任务，按当前登记API PID/创建时间停止API，再从私有备份backend的PYTHONPATH启动旧实现并检查health；不改工作区源码，不动worker、DB/storage或现用前端。不得把runtime-private.json直接覆盖回运行配置（其中PID已过时）。

自动回退路径已在部署脚本中准备，本次未触发；不能声称回退流程已实演。旧后端仍有DKVB-001，回退只用于恢复原可用服务。前端未切换，无前端回退需求；备份dist保留，后端回退不覆盖前端。回退模式在将来用通用start启动时不会自动沿用，需按实际运行说明判断。

## 停止与限制

5196 API保留运行，等待用户体验。真实资料NOT_MET、PDF needs_ocr、同任务限制、Linux BGE未验证和历史未确认根因保留。未修改业务源码、旧迁移、旧项目、原资料包、历史证据或接受记录；Git index未变，无付费/账本读取/提交推送。WP-11—17未开始。
