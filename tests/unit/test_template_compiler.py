import json
import shutil
from pathlib import Path

import pytest

from scripts.compile_templates import CompileError, compile_recipe, content_hash, run

ROOT = Path(__file__).resolve().parents[2]
LIBRARY = ROOT / "resources/template-library/tayron-dkvb"


def test_modules_reassemble_the_published_templates_exactly():
    results = run(LIBRARY)
    assert {item["recipe"] for item in results} == {"tayron-dkvb-p0299-v2.json", "tayron-dkvb-p0236-v2.json"}
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
    (library / "recipes/tayron-dkvb-p0299-v2.json").unlink()
    return library, recipe_path


@pytest.mark.parametrize(("edit", "message"), [
    (lambda r: r.update(modules=[{"id": "turbo", "version": "1"}]), "needs modules"),
    (lambda r: r["modules"][0].update(version="9"), "wants boost-air v9"),
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
    module_path = library / "modules/pressure.json"
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
