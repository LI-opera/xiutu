# WP-09 r2 定点复核

**结论：REVIEW_PASS（限定WP-09技术范围）。ISSUE-001、ISSUE-002均RESOLVED，可关闭。** 结合r1未变部分的通过证据，建议用户决定是否限定范围接受；本报告不是用户接受，不接受整个P4，不进入WP10。

**流程披露：本任务参与了实施、r1审核及整改，本次仍由同一任务复核，不属于不同任务独立审核。** 新隔离目录和本轮亲测不替代审核角色独立性。

## 1. 依据、差异与保护

已读STATUS、r1审核/整改报告、当前契约、model_gateway.py、正式整改测试、model_budget.py及对应diff、原反例、JUnit和封存记录。E:/、E:/Work及项目目录未找到适用AGENTS.md。main无HEAD，不以此跳过文件哈希；Git状态记录在baseline.json。

相对r1已有文件差异仅backend/app/infrastructure/model_gateway.py、docs/implementation/phase-04/wp-09-contract.md；新增tests/unit/test_wp09_remediation.py及整改报告/证据符合声明。预算算法、SDK零重试配置、其他工具/索引/迁移未改。核对整改delivery-hashes和seal，并合并原保护输入，共3731项全部匹配。本轮开始/结束无差异，Git index仍c451d6e78b8f29fc818002923a19fb1a888139ced20679ad545f75e9692a9ec6。旧项目63项哈希匹配；STATUS、历史接受/报告/原证据和旧迁移未改。

整改test_original_audit.py与r1原反例逐字节相同，未修改旧失败断言；历史XML结果保持。未读取私有.env、真实费用账本，未调用模型/启动DB或Compose。保护证据baseline.json、protection-final.json；本轮报告与测试输出另存evidence/wp-09-review-r2。

## 2. ISSUE-001 — RESOLVED

代码定位：model_gateway.py:38—92（_redact_json/outbound_messages），request:166在任何预算预留前调用。深复制后进行SDK转换前文本块检查，拒绝图片/音频/未知块及附加字段，防止SDK先丢字段；转换后的正文和JSON参数值统一脱敏。未对整包做盲目替换，调用ID/角色/工具名称保留。JSON重新序列化且allow_nan=false，正常字符串工具参数未被禁用；非敏感数字、布尔、null及嵌套结构保留。协议标识是可信调用身份，不保证通用PII识别。

本轮test_supported_carriers_and_immutability通过真实SDK→MockTransport观察普通正文、多个文本块、ToolMessage及嵌套arguments：合成电话/邮箱替换，正常中文保留，args可解析、类型与值相符，call ID和函数名匹配，原输入对象等价未变。既有多工具和结构输出测试验证角色/ToolMessage对应可继续消费。

三种不支持载体均明确MODEL_MESSAGE_UNSUPPORTED，transport=0、calls=0、无预留，原输入不变。合法纯文本和正常工具参数仍成功发送。

特别区分历史结果：整改original.xml是2通过、1失败；图文反例旧断言要求成功，安全拒绝导致该旧实例失败，不能改称三项全通过。本轮未无意义重复旧成功假设，而实际运行正式安全断言证明零请求/零预留。原失败日志与反例保持，原工具参数漏洞已由本轮合法嵌套参数成功脱敏验证覆盖。

## 3. ISSUE-002 — RESOLVED

代码定位：model_gateway.py:178—186，reserve完成之后、SDK invoke之前检查期限；过期路径finish(not_sent, dispatched=false, usage=None)后抛MODEL_TURN_TIMEOUT，不进入重试。终态持久化异常也会在invoke之前向外传播；金额保守保留，不清零、不退款。model_budget.py无改动。未证明或声称原缺陷突破5元上限。

本轮正式跨进程文件锁反例：独立PID7472实际持有隔离账本锁，网关等待约2.031秒，期间turn期限耗尽；transport=0、仅1条预留、not_sent/dispatched=false、usage unknown、保留金额。不是仅线程启动或替换reserve的并发证明。

补充两项仅注入终态save故障：①替换文件前抛OSError，原reserved留存；②真实save完成后抛OSError，not_sent留存。两者均0请求、1次预留/调用、金额未释放、无重试。终态失败时异常并未伪装成功。正常发送、429有限两次并计预算、金额不足/turn过期停止，以及已发送迟到结果拒绝均通过。

同步发送非硬实时抢占，最后检查到发送之间存在正常调度边界；不要求网络在途实时撤回。received仅表示已收到provider响应/记录usage，不表示结果获准后续使用。

## 4. 本轮亲测与历史证据

一次调用，26项受影响测试加2项终态写入失败补充，共**28通过，0失败/错误/跳过，exit0，pytest用时6.64秒，无警告输出**。每个选中实例仅运行一次；无现场修改实现或测试断言。使用新.test-runs/wp09-review-r2-06d7、MockTransport与合成字段/隔离账本，直接导入当前backend；不加载BGE、不连接数据库、不请求付费服务。

证据：targeted.json（展开命令、cwd、时间、退出码）、targeted.txt（PID/真实等待/两种故障状态）、targeted.xml；test_terminal_failure.py为本轮独立补充，未修改正式测试。

证据版本不得混同：

| 阶段 | 统计与基准 |
| --- | --- |
| 原执行完整回归 | 历史328通过；之后注释/空行AST核对见r1，不是当前版本重跑 |
| r1审核 | 历史22定点通过；补充发现脱敏/锁等待失败及一次夹具错误，原记录不改 |
| r1整改 | 原反例2通过/1安全拒绝引起的旧断言失败；首轮24通过/2失败；修正后26通过 |
| 本轮r2 | 当前26项亲测通过，另2项补充通过；合计28只是本轮实例数，不与历史重复统计相加为功能覆盖数 |

未重跑328项、前端、第二环境、模型评测、BGE索引或Linux Compose，无新增跨模块风险依据，不扩大审核。

## 5. 限定结论与保留项

本轮没有新的必须整改项。A402原两项阻断已消除；A401/A403、factory、Windows native BGE/E5兼容沿用r1已通过且未变的代码/证据，不声称本轮重新验证真实链路。E10保留r1原证据限定通过（实测deepseek-flash，不扩大到其他型号/全部strict或维修语义），未读取真实账本和账单，不产生新费用。

Linux BGE部署仍NOT_VERIFIED，明确排除建议接受范围。真实资料NOT_MET，最迟WP10/真实效果验收前补齐；SSE首次超时、Compose历史启动底层原因未确认，以及混合模型排序校准、性能/监控/清理等既有非阻断待办保留。脱敏为当前列明载体/正则范围，不代表全面隐私识别。生产恢复、正式Agent/图/UI、真实维修效果及后续包均不在通过范围。

建议接受范围：WP09模型网关与可信Skills、已验证配置factory、本地Windows BGE1024与旧E5384索引兼容，并保留上述边界及同任务流程限制。最终接受权属于用户；STATUS仍IMPLEMENTED_NOT_ACCEPTED，不改接受记录。无提交推送，完成本报告后停止。

## 实际命令

```text
E:\Work\xiutu-v5\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider tests/unit/test_wp09_contracts.py tests/unit/test_wp09_remediation.py docs/implementation/phase-04/evidence/wp-09-review-r2/test_terminal_failure.py -q -s --basetemp=.test-runs/wp09-review-r2-06d7 --junitxml=docs/implementation/phase-04/evidence/wp-09-review-r2/targeted.xml
```

cwd：`E:\Work\xiutu-v5`。起止：2026-09-19T01:08:30.474403+08:00 → 2026-09-19T01:08:39.033569+08:00。退出码：0。
