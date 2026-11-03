"""Assemble complete template files from area modules (resources/template-library/<library>/).

A library holds catalog.json (stages, shared assets and sources, rule engine versions),
modules/<area>.json (one area with its cards, questions and the rules that belong to it)
and recipes/<template>.json (which modules, in which order, plus template-level text).

Default is --check: compile every recipe and compare with its published output file.
--write only creates output files that do not exist yet; a published version is never
overwritten, a change needs a new recipe with a new version.
Compiling does not touch the database; publishing stays publish_independent_templates.py.
"""
import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_SCHEMA = "template-module/1"
RECIPE_SCHEMA = "template-recipe/1"
CATALOG_SCHEMA = "template-catalog/1"
FROM_RECIPE = "$recipe"


class CompileError(ValueError):
    pass


def content_hash(content):
    """Same formula as app.services.workbench_templates.content_hash."""
    return hashlib.sha256(json.dumps(content, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def render(content):
    return (json.dumps(content, ensure_ascii=False, indent=2) + "\n").replace("\n", "\r\n").encode("utf-8")


def load(path, schema):
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != schema:
        raise CompileError(f"{path.name}: schema_version must be {schema}")
    return data


def fill(value, recipe, where):
    """Replace {"$recipe": "<key>"} placeholders with template-level text from the recipe."""
    if isinstance(value, dict):
        if set(value) == {FROM_RECIPE}:
            key = value[FROM_RECIPE]
            if key not in recipe.get("values", {}):
                raise CompileError(f"{where}: recipe has no value for {key!r}")
            return copy.deepcopy(recipe["values"][key])
        return {k: fill(v, recipe, where) for k, v in value.items()}
    if isinstance(value, list):
        return [fill(v, recipe, where) for v in value]
    return value


QUESTION_REF_KEYS = {"question_id", "target_question_id", "question_ids", "questionIds", "refs"}


def question_refs(value):
    """Question ids a module points at: prerequisites, card membership, rule inputs and triggers."""
    if isinstance(value, dict):
        for key, item in value.items():
            if key in QUESTION_REF_KEYS:
                yield from ([item] if isinstance(item, str) else item)
            else:
                yield from question_refs(item)
    elif isinstance(value, list):
        for item in value:
            yield from question_refs(item)


def compile_recipe(library, recipe_path):
    catalog = load(library / "catalog.json", CATALOG_SCHEMA)
    recipe = load(recipe_path, RECIPE_SCHEMA)
    asset_ids = [asset["id"] for asset in catalog["assets"]]
    source_ids = [source["id"] for source in catalog["sources"]]
    excluded = recipe.get("excluded_asset_ids", [])
    for asset_id in excluded:
        if asset_id not in asset_ids:
            raise CompileError(f"{recipe_path.name}: excluded asset {asset_id} is not in the catalog")
    for source_id in recipe["source_ids"]:
        if source_id not in source_ids:
            raise CompileError(f"{recipe_path.name}: source {source_id} is not in the catalog")

    modules, chosen = [], [entry["id"] for entry in recipe["modules"]]
    if len(set(chosen)) != len(chosen):
        raise CompileError(f"{recipe_path.name}: a module is listed twice")
    for entry in recipe["modules"]:
        module = load(library / "modules" / f"{entry['id']}.json", MODULE_SCHEMA)
        if module["module_id"] != entry["id"] or module["module_version"] != entry["version"]:
            raise CompileError(f"{recipe_path.name}: wants {entry['id']} v{entry['version']}, "
                               f"library has {module['module_id']} v{module['module_version']}")
        missing = [need for need in module.get("requires_modules", []) if need not in chosen]
        if missing:
            raise CompileError(f"module {entry['id']} needs modules {missing}")
        modules.append(fill(module, recipe, f"module {entry['id']}"))

    areas, questions, cards, calculation, focus, conflict, workflow = [], [], [], [], [], [], {}
    used_assets, dropped = set(), set()

    def keep_assets(item):
        for asset_id in item["assetIds"]:
            if asset_id not in asset_ids:
                raise CompileError(f"{item['id']}: asset {asset_id} is not in the catalog")
        dropped.update(a for a in item["assetIds"] if a in excluded)
        item["assetIds"] = [a for a in item["assetIds"] if a not in excluded]
        used_assets.update(item["assetIds"])
        return item

    for module in modules:
        area = module["area"]
        own_cards = [keep_assets(card) for card in module["cards"]]
        own_questions = [keep_assets(question) for question in module["questions"]]
        if any(card["areaId"] != area["id"] for card in own_cards) or \
                any(question["area_id"] != area["id"] for question in own_questions):
            raise CompileError(f"module {module['module_id']}: card or question belongs to another area")
        areas.append(area)
        cards += own_cards
        questions += own_questions
        calculation += module.get("calculation_rules", [])
        focus += module.get("focus_rules", [])
        conflict += module.get("conflict_rules", [])
        for key, value in module.get("observation_workflow", {}).items():
            if key in workflow:
                raise CompileError(f"observation_workflow.{key} is set by more than one module")
            workflow[key] = value
    unused = set(excluded) - dropped
    if unused:
        raise CompileError(f"{recipe_path.name}: excluded assets {sorted(unused)} are not used by any module")
    ids = [item["id"] for item in areas + cards + questions]
    if len(set(ids)) != len(ids):
        raise CompileError(f"{recipe_path.name}: duplicate area, card or question id")

    question_ids = {question["id"] for question in questions}
    dangling = sorted({ref for module in modules for ref in question_refs(module) if ref not in question_ids})
    if dangling:
        raise CompileError(f"{recipe_path.name}: references questions not in the template: {dangling}")

    template = recipe["template"]
    content = {"schema_version": template["schema_version"],
               "stages": catalog["stages"],
               "assets": [asset for asset in catalog["assets"] if asset["id"] in used_assets],
               "sources": [source for source in catalog["sources"] if source["id"] in recipe["source_ids"]],
               "topic_id": template["topic_id"], "version": template["version"],
               "authority": template["authority"], "source_boundary": template["source_boundary"],
               "areas": areas, "questions": questions, "cards": cards}
    if calculation:
        content["calculation_rules"] = {"version": catalog["calculation_rules_version"], "rules": calculation}
    if focus or conflict:
        content["observation_rules"] = {"version": catalog["observation_rules_version"],
                                        "focus_rules": focus, "conflict_rules": conflict}
    if workflow:
        content["observation_workflow"] = workflow
    return recipe, content


def run(library, *, write=False):
    results = []
    for recipe_path in sorted((library / "recipes").glob("*.json")):
        recipe, content = compile_recipe(library, recipe_path)
        output = ROOT / recipe["output"]
        expected = render(content)
        if not output.exists():
            status = "created" if write else "missing"
            if write:
                output.write_bytes(expected)
        else:
            published = output.read_bytes()
            if published == expected:
                status = "identical"
            elif content_hash(json.loads(published)) == content_hash(content):
                status = "same_content_different_bytes"
            else:
                status = "different"
        results.append({"recipe": recipe_path.name, "output": recipe["output"], "status": status,
                        "content_hash": content_hash(content)})
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--library", type=Path, required=True)
    parser.add_argument("--write", action="store_true", help="create outputs that do not exist yet")
    args = parser.parse_args()
    try:
        results = run(args.library.resolve(), write=args.write)
    except CompileError as error:
        print(f"compile error: {error}", file=sys.stderr)
        raise SystemExit(2)
    print(json.dumps(results, ensure_ascii=False, indent=2))
    if any(item["status"] not in {"identical", "created"} for item in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
