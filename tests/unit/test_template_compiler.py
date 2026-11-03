import json
import shutil
from pathlib import Path

import pytest

from scripts.compile_templates import CompileError, compile_recipe, content_hash, run

ROOT = Path(__file__).resolve().parents[2]
LIBRARY = ROOT / "resources/template-library/tayron-dkvb"


def test_modules_reassemble_the_published_templates_exactly():
    results = run(LIBRARY)
    assert {item["recipe"] for item in results} == {f"tayron-dkvb-{code}-v{version}.json"
                                                    for code in ("p0299", "p0236") for version in (2, 3, 4, 5, 6)}
    for item in results:
        published = json.loads((ROOT / item["output"]).read_text(encoding="utf-8"))
        assert item["status"] == "identical"
        assert item["content_hash"] == content_hash(published)


def copy_library(tmp_path, edit):
    library = tmp_path / "library"
    shutil.copytree(LIBRARY, library)
    recipe_path = library / "recipes/tayron-dkvb-p0236-v2.json"
    recipe = json.loads(recipe_path.read_text(encoding="utf-8"))
    recipe["output"] = str(tmp_path / "out.json")
    edit(recipe)
    recipe_path.write_text(json.dumps(recipe, ensure_ascii=False), encoding="utf-8")
    for other in (library / "recipes").glob("*.json"):
        if other != recipe_path:
            other.unlink()
    return library, recipe_path


@pytest.mark.parametrize(("edit", "message"), [
    (lambda r: r.update(modules=[{"id": "turbo", "version": "1"}]), "needs modules"),
    (lambda r: r["modules"][0].update(version="9"), "no module boost-air v9"),
    (lambda r: r["excluded_asset_ids"].append("M11"), "not used by any module"),
    (lambda r: r["values"].clear(), "no value for 'question_applicability'"),
    (lambda r: r["source_ids"].append("NO-SUCH-SOURCE"), "not in the catalog"),
])
def test_invalid_recipes_are_rejected(tmp_path, edit, message):
    library, recipe_path = copy_library(tmp_path, edit)
    with pytest.raises(CompileError, match=message):
        compile_recipe(library, recipe_path)


def test_missing_question_reference_is_rejected(tmp_path):
    library, recipe_path = copy_library(tmp_path, lambda r: None)
    module_path = library / "modules/pressure/1.json"
    module = json.loads(module_path.read_text(encoding="utf-8"))
    module["questions"][0]["prerequisites"]["refs"] = ["TUR-01"]
    module_path.write_text(json.dumps(module, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(CompileError, match="TUR-01"):
        compile_recipe(library, recipe_path)


def test_write_creates_new_outputs_but_never_overwrites(tmp_path):
    library, _ = copy_library(tmp_path, lambda r: None)
    output = tmp_path / "out.json"
    assert run(library)[0]["status"] == "missing"
    assert run(library, write=True)[0]["status"] == "created"
    assert output.read_bytes() == (ROOT / "resources/templates/tayron-v2/tayron-dkvb-p0236-v2.json").read_bytes()
    output.write_text("{}", encoding="utf-8")
    assert run(library, write=True)[0]["status"] == "different"
    assert output.read_text(encoding="utf-8") == "{}"


def test_v3_changes_only_the_boost_air_connector_questions():
    folder = ROOT / "resources/templates/tayron-v2"
    for code in ("p0299", "p0236"):
        old = json.loads((folder / f"tayron-dkvb-{code}-v2.json").read_text(encoding="utf-8"))
        new = json.loads((folder / f"tayron-dkvb-{code}-v3.json").read_text(encoding="utf-8"))
        changed = {q["id"] for q, before in zip(new["questions"], old["questions"]) if q != before}
        assert [q["id"] for q in new["questions"]] == [q["id"] for q in old["questions"]]
        assert changed == {"AIR-07", "AIR-08", "AIR-09", "AIR-10"}
        assert {c["id"] for c, before in zip(new["cards"], old["cards"]) if c != before} == {"air-connector"}
        for key in ("stages", "assets", "sources", "areas", "calculation_rules", "observation_workflow"):
            assert new[key] == old[key]
        assert new["observation_rules"]["conflict_rules"] == []
        assert new["observation_rules"]["focus_rules"][0]["all"] == [
            {"question_id": "AIR-07", "option_ids": ["not_inserted"]}]


def test_v4_changes_only_the_boost_air_area():
    """boost-air v3 was drafted from the reviewed guide: AIR-01..16 keep their ids, AIR-17 is new,
    and the other areas are untouched."""
    folder = ROOT / "resources/templates/tayron-v2"
    for code in ("p0299", "p0236"):
        old = json.loads((folder / f"tayron-dkvb-{code}-v3.json").read_text(encoding="utf-8"))
        new = json.loads((folder / f"tayron-dkvb-{code}-v4.json").read_text(encoding="utf-8"))
        old_q = {q["id"]: q for q in old["questions"]}
        new_q = {q["id"]: q for q in new["questions"]}
        assert set(new_q) - set(old_q) == {"AIR-17"} and set(old_q) <= set(new_q)
        assert {i for i in old_q if old_q[i] != new_q[i]} == {f"AIR-{n:02d}" for n in range(1, 17)}
        assert [a for a in new["areas"] if a["id"] != "boost-air"] == [a for a in old["areas"] if a["id"] != "boost-air"]
        assert all(q["reference_section"] for q in new["questions"] if q["area_id"] == "boost-air")


def test_v5_changes_only_the_pressure_area():
    """pressure v2 was drafted from the reviewed guide: PRS-01..12 keep their ids, PRS-13 is new,
    the calculation rules still find their questions, fields and options."""
    folder = ROOT / "resources/templates/tayron-v2"
    for code in ("p0299", "p0236"):
        old = json.loads((folder / f"tayron-dkvb-{code}-v4.json").read_text(encoding="utf-8"))
        new = json.loads((folder / f"tayron-dkvb-{code}-v5.json").read_text(encoding="utf-8"))
        old_q = {q["id"]: q for q in old["questions"]}
        new_q = {q["id"]: q for q in new["questions"]}
        assert set(new_q) - set(old_q) == {"PRS-13"} and set(old_q) <= set(new_q)
        assert {i for i in old_q if old_q[i] != new_q[i]} == {f"PRS-{n:02d}" for n in range(1, 13)}
        assert new["calculation_rules"] == old["calculation_rules"]
        for rule in (r for r in new["calculation_rules"]["rules"] if r.get("target_question_id", "").startswith("PRS-")):
            outputs = rule["outputs"].values()
            names = {v for v in outputs if isinstance(v, str)} | {x for v in outputs if isinstance(v, dict) for x in v.values()}
            assert names <= {o["id"] for o in new_q[rule["target_question_id"]]["options"]}
            for item in rule["inputs"]:
                fields = {f["id"] for f in new_q[item["question_id"]]["fields"]}
                assert {item[k] for k in ("field", "target_field", "actual_field") if k in item} <= fields


def test_v6_changes_only_the_actuator_area():
    """actuator v2 was drafted from the reviewed guide: ACT-01..07 rewritten, ACT-08..10 (basic
    setting) kept unchanged, ACT-11..16 new."""
    folder = ROOT / "resources/templates/tayron-v2"
    for code in ("p0299", "p0236"):
        old = json.loads((folder / f"tayron-dkvb-{code}-v5.json").read_text(encoding="utf-8"))
        new = json.loads((folder / f"tayron-dkvb-{code}-v6.json").read_text(encoding="utf-8"))
        old_q = {q["id"]: q for q in old["questions"]}
        new_q = {q["id"]: q for q in new["questions"]}
        assert set(new_q) - set(old_q) == {f"ACT-{n}" for n in range(11, 17)} and set(old_q) <= set(new_q)
        assert {i for i in old_q if old_q[i] != new_q[i]} == {f"ACT-{n:02d}" for n in range(1, 8)}
        assert "不是输出测试" in new_q["ACT-03"]["instructions"]
