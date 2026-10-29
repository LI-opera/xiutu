# 模板积木库

`resources/templates/` 里是**发布用的完整模板**（修途运行时读取的就是它们）。本目录是它们的**来源**：按区域拆开的积木，以及把积木拼成完整模板的配方。

```
template-library/<库名>/
├─ catalog.json        共用部分：阶段、图片、来源、规则引擎版本
├─ modules/<区域>.json  一个区域：区域定义、分组、题目、只属于这个区域的计算/观察规则
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

## tayron-dkvb

由 `tayron-dkvb-p0299-v2` 拆出 5 个积木（boost-air、pressure、actuator、turbo、powertrain）。两个配方拼出的结果与已发布的 P0299 v2、P0236 v2 **逐字节相同**（`tests/unit/test_template_compiler.py` 会持续检查）。两者的差别全部在配方里：题目适用说明文字、来源清单，以及 P0236 去掉了 P0299 专用的诊断路由图 D03。
