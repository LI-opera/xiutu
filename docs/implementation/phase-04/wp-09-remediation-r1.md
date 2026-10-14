# WP-09 r1 定点整改记录

状态：IMPLEMENTED_NOT_ACCEPTED，等待仅针对本次差异的定点复核。本文是执行者自测记录，不是审核关闭、REVIEW_PASS或用户接受。仅处理审核r1 ISSUE-001/002，不进入WP10。

## 基准及改动范围

本轮读取STATUS、契约、r1报告、原反例及封存；适用目录未找到AGENTS.md。main无HEAD。开始核对3709项交付/审核保护文件全部匹配，包含原报告、原反例、失败日志及seal；Git index匹配。未读取或修改真实费用账本和私有.env，也未加载模型或连接数据库。

仅修改已有文件：
- backend/app/infrastructure/model_gateway.py：有界载体脱敏、预留后deadline。
- docs/implementation/phase-04/wp-09-contract.md：支持载体和终态规则。

新增正式回归tests/unit/test_wp09_remediation.py；另新增本报告及evidence/wp-09-remediation-r1独立证据。model_budget.py未修改。实现差异model_gateway.diff已通过反向重建与审核原SHA核对。STATUS、接受记录、旧迁移及历史证据未改；其过时说明按用户范围保留，不顺带更新。

## ISSUE-001：出站脱敏

原request仅处理字符串content，遗漏混合块和历史tool_calls.arguments。现outbound_messages复制输入，先检查SDK转换前的文本块（避免SDK合并文本时丢弃未知字段），再处理允许出站的正文及函数参数JSON文本叶子。角色/函数名/call ID不作盲目替换；保留数字、布尔、null、嵌套结构与普通字符串含义，敏感文本替换为既有PHONE/EMAIL/VIN标记。相关ToolMessage正文同样处理；原消息及业务记录不变。

仅支持文本块，图片/音频/未知块或附加字段明确MODEL_MESSAGE_UNSUPPORTED，在预算预留与transport之前拒绝。敏感JSON键拒绝而不重命名，非法/非有限JSON拒绝；不靠禁用正常字符串工具参数规避问题。原图文审核实例保持原字节重跑后因明确拒绝而在旧“必须返回成功”断言处失败，这不是继续泄漏，未改原断言宣称全部通过；正式新增测试明确断言无请求、无预算记录、输入未变。正常多文本块经SDK规范化为换行字符串并完整脱敏。

## ISSUE-002：锁等待后期限

reserve跨进程阻塞后，在SDK实际invoke前重验120秒turn期限。过期终止为MODEL_TURN_TIMEOUT，不进入发送/重试；预留记not_sent、dispatched=false、usage=null/unknown，金额仍保守保留，不退款或清零。终态写入失败也不会发送，可能保留reserved供核查。共享金额算法和SDK max_retries=0未改；本缺陷从未证明突破5元总额。

原独立进程锁反例本轮PID11352、实际等待约2.032秒，transport=0；正式回归最终PID34180、约2.032秒，终态not_sent、仅1条预留。普通请求可发；429正常仅两次且各预留，金额不足或turn过期不追加发送。已发送响应迟到仍记录received/usage但抛超时，不返回给后续业务；received不是结果获准使用。保留同步调用非硬实时限制，不声称网络在途可实时撤销。

## 本轮实际测试与失败记录

全部MockTransport、合成电话/邮箱和新临时账本，无真实费用账本读取、无外部请求。直接导入当前backend，原审核副本内容逐字节相同，仅位置变化使输出落入本轮目录。临时目录均全新，不复用历史basetemp。

| 记录 | 结果 | 解释 |
| --- | --- | --- |
| original | 2通过、1失败；exit1 | 历史工具参数和真实预算锁反例通过；图文实例明确拒绝触发旧成功假设，原失败完整保留 |
| targeted | 24通过、2失败；exit1 | 新测试预期SDK保留文本块，实际SDK合并字符串；另发现转换前未知块字段检查缺口，均保留日志 |
| correction | 26通过、0失败/错误/跳过；exit0 | 转换前检查修正，并以SDK实际换行字符串检查脱敏；复跑直接受影响网关集。无警告输出 |

26项由原17项离线契约及新增9项回归组成。覆盖结构JSON修复、空/截断、429/503/401、预算并发/重启/重复、原生多ID/skill收窄、错误参数，及本次新出站、输入不变、超时终态等。未声称全量或真实模型重跑；历史328项和审核22项仅引用原基准，不与本轮重复统计累加为功能覆盖数。

首次两失败分别为测试对SDK输出形状的预期错误，以及实现应在转换前检查的真实缺口。修正未放宽无敏感文本、身份不变、无请求/无预留等业务断言；未改变任何历史反例。未循环运行整包。

## 边界与停止

两项必要实现与定点自测已完成，是否关闭交后续审核者决定。E10保留r1按原证据限定通过，不扩大到其他DeepSeek型号；Linux BGE部署仍未验证并排除范围。既有脱敏正则不是完整PII识别平台；协议身份保留，受信入口仍应使用不含个人信息的标识。真实资料NOT_MET，最迟WP10/真实效果验收前；SSE首次超时、Compose历史启动底层原因未确认，以及既有非阻断待办保留。

结束核对3709项中仅两项声明的旧文件变化，新增正式测试单列；旧项目63项及Git index不变。无提交推送、无付费、无自发审核或接受，STATUS原IMPLEMENTED_NOT_ACCEPTED保持。未重跑328全量、BGE索引、前端、第二环境、Linux Compose。完成后停止。

## 实际命令与时间

### original

```text
E:\Work\xiutu-v5\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider docs/implementation/phase-04/evidence/wp-09-remediation-r1/test_original_audit.py::test_text_carriers_redacted docs/implementation/phase-04/evidence/wp-09-remediation-r1/test_original_audit.py::test_deadline_after_real_budget_lock -q -s --basetemp=.test-runs/wp09-remediation-original-29fa --junitxml=docs/implementation/phase-04/evidence/wp-09-remediation-r1/original.xml
```

cwd：`E:\Work\xiutu-v5`；2026-09-19T01:01:31.460083+08:00 → 2026-09-19T01:01:39.565273+08:00；exit=1。原始输出/JUnit：`original.txt`、`original.xml`。

### targeted

```text
E:\Work\xiutu-v5\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider tests/unit/test_wp09_contracts.py tests/unit/test_wp09_remediation.py -q -s --basetemp=.test-runs/wp09-remediation-targeted-826c --junitxml=docs/implementation/phase-04/evidence/wp-09-remediation-r1/targeted.xml
```

cwd：`E:\Work\xiutu-v5`；2026-09-19T01:01:51.495160+08:00 → 2026-09-19T01:02:00.874739+08:00；exit=1。原始输出/JUnit：`targeted.txt`、`targeted.xml`。

### correction

```text
E:\Work\xiutu-v5\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider tests/unit/test_wp09_contracts.py tests/unit/test_wp09_remediation.py -q -s --basetemp=.test-runs/wp09-remediation-correction-ae67 --junitxml=docs/implementation/phase-04/evidence/wp-09-remediation-r1/correction.xml
```

cwd：`E:\Work\xiutu-v5`；2026-09-19T01:02:43.282227+08:00 → 2026-09-19T01:02:51.977730+08:00；exit=0。原始输出/JUnit：`correction.txt`、`correction.xml`。

