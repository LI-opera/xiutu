# 模板积木库

`resources/templates/` 里是**发布用的完整模板**（修途运行时读取的就是它们）。本目录是它们的**来源**：按区域拆开的积木，以及把积木拼成完整模板的配方。

```
template-library/<库名>/
├─ catalog.json        共用部分：阶段、图片、来源、规则引擎版本
├─ modules/<区域>/<版本>.json  一个区域的一个版本：区域定义、分组、题目、只属于这个区域的计算/观察规则
└─ recipes/<模板>.json  一个模板：选哪些积木、按什么顺序、模板级文字、来源清单、要去掉的图片
```

## 编译与检查

```powershell
uv run python -B scripts/compile_templates.py --library resources/template-library/tayron-dkvb          # 检查
uv run python -B scripts/compile_templates.py --library resources/template-library/tayron-dkvb --write  # 生成新版本
```

- 检查：把每个配方拼成完整模板，和 `output` 指向的已发布文件逐字节比较，结果为 `identical` 才算通过；
- `--write` 只生成**还不存在**的文件。已发布的版本不会被覆盖，要改模板就新建一个配方、换新版本号；
- 编译不写数据库。生成后仍按原流程登记 `relations.json`、预检、发布。

## 编译时会拦下的错误

- 配方要的积木版本和库里的不一致；
- 积木声明的前置积木（`requires_modules`）没被选上，例如 `turbo` 的 TUR-09 要用 `pressure` 的压力题；
- 题目引用了模板里不存在的题（前提、分组、规则里的题号）；
- 引用了目录里没有的图片或来源；`excluded_asset_ids` 里的图片没有被任何积木用到；
- 两个积木写了同一个观察流程，或题号、分组号、区域号重复；
- 积木里的 `{"$recipe": "<名称>"}` 在配方的 `values` 里找不到值。

## 拼装规则

- 区域、题目、分组、规则按配方里积木的顺序依次拼接；
- 图片清单 = 积木实际引用的图片（去掉 `excluded_asset_ids` 后），按目录顺序；
- 来源清单 = 配方 `source_ids` 选中的来源，按目录顺序；
- 输出为 2 空格缩进、CRLF 换行，与现有发布文件一致。

## 修改一个区域的步骤

1. 复制 `modules/<区域>/<旧版本>.json` 为新版本，改内容和 `module_version`；旧版本文件保留不动；
2. 为每个用到这个区域的模板新建配方（换新的 `version` 和 `output`），把该积木改成新版本；
3. `--write` 生成新模板文件，在 `relations.json` 里登记新版本；
4. 配记录角色：`scripts/build_analysis_context.py`。没改的题自动沿用上一版；改过的题要人工写一个审核文件，用 `--review` 传入；
5. 预检、试用、发布。

## tayron-dkvb

- v2：由 `tayron-dkvb-p0299-v2` 拆出 5 个积木（boost-air、pressure、actuator、turbo、powertrain）。两个配方拼出的结果与已发布的 P0299 v2、P0236 v2 **逐字节相同**。两者的差别全部在配方里：题目适用说明文字、来源清单，以及 P0236 去掉了 P0299 专用的诊断路由图 D03。
- v3：boost-air 积木第 2 版。本车增压软管接头是"插到止动位置 + 标记对齐 + 螺旋卡箍"，不是快插接头，AIR-07～10 按此重写，相应调整追查规则，删去只适用于快插接头的冲突规则。P0299、P0236 同时升到 v3，其他 4 个积木不变。
- v4：boost-air 积木第 3 版，由资料整理平台从审核过的《增压空气通路检查与维修指南》（资料包第 6 版）起草题目，程序核对出处与数值，人工审核后转换（xiutu-clean：`draft_module.py` → `check_module.py` → `module_from_review.py`）。AIR-01～16 编号保留，选项改用指南结果表的说法；滤芯、导流软管、软管表面改为多选；检漏 AIR-14～16 的执行条件指向前一题的具体选项；新增 AIR-17 进气侧导流软管座合与卡箍。每题记下出自指南哪一节（`reference_section`）。P0299、P0236 同时升到 v4，其他 4 个积木不变。
- v5：pressure 积木第 2 版，同样由资料整理平台从审核过的《增压压力测量检查与维修指南》（资料包第 5 版）起草（提示词 draft-module-v3）。PRS-01～12 编号保留，读数字段、同批采集和两条计算规则原样沿用；G31 插头改为多选；三帧读数只要求先确认工况可比较（PRS-07）；新增 PRS-13 G31 插头 T4ct 针脚与线色核对（电路图 70/10）；动态工况卡片补路试安全提示。P0299、P0236 同时升到 v5，其他积木不变。
