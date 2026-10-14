"""Explicit, idempotent template installation; never overwrites a published version."""
import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

RELATIONS = ROOT / "backend/app/topics/workbench_template_relations_v1.json"


def _independent_content(config_path, relation):
    relative = Path(relation["content_file"])
    root = config_path.parent.resolve()
    path = (root / relative).resolve()
    if relative.is_absolute() or not path.is_relative_to(root) or not path.is_file():
        raise ValueError(f"Invalid template content file: {relation['id']}")
    topic = json.loads(path.read_text(encoding="utf-8"))
    if topic.get("calculation_catalog") is not None:
        raise ValueError(f"Independent template cannot use B01/B02 calculation_catalog: {relation['id']}")
    expected_version = relation["template_id"] + "-v" + relation["version"]
    if (topic.get("topic_id") != relation["template_id"] or
            topic.get("version") != expected_version or
            [area["id"] for area in topic.get("areas", [])] != relation["area_ids"]):
        raise ValueError(f"Template identity or areas mismatch: {relation['id']}")
    area_ids = set(relation["area_ids"])
    questions = topic.get("questions", [])
    cards = topic.get("cards", [])
    qids = {question["id"] for question in questions}
    card_ids = {card["id"] for card in cards}
    if (len(qids) != len(questions) or len(card_ids) != len(cards) or
            any(question.get("area_id") not in area_ids for question in questions) or
            any(question.get("cardId") not in card_ids for question in questions) or
            any(card.get("areaId") not in area_ids or
                not set(card.get("questionIds", [])) <= qids for card in cards) or
            any(not set(area.get("componentIds", [])) <= card_ids for area in topic["areas"])):
        raise ValueError(f"Template hierarchy invalid: {relation['id']}")
    from app.services.template_observation_rules import validate as validate_observation_rules
    from app.services.template_projection import _validate_calculations as validate
    validate(topic)
    validate_observation_rules(topic)
    return topic


def build_templates(config_path=RELATIONS):
    config_path = Path(config_path).resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config_path != RELATIONS.resolve() and config.get("runtime_importable") is not True:
        raise ValueError("New template package is not approved for runtime import")
    base = None
    for relation in config["relations"]:
        if "content_file" in relation:
            yield relation, _independent_content(config_path, relation)
            continue
        if config_path != RELATIONS.resolve():
            raise ValueError(f"New template requires content_file: {relation['id']}")
        # Only the already published v1 installation uses the frozen B02 source.
        if base is None:
            from app.topics import dkvb_b02
            base, _ = dkvb_b02.catalog()
        topic = deepcopy(base)
        topic["calculation_catalog"] = deepcopy(base)
        topic["topic_id"] = relation["template_id"]
        topic["version"] = relation["template_id"] + "-v" + relation["version"]
        topic["authority"] = config["boundary"]
        topic["areas"] = [a for a in topic["areas"] if a["id"] in relation["area_ids"]]
        topic["questions"] = [q for q in topic["questions"] if q["area_id"] in relation["area_ids"] or q["id"] == "IN-08"]
        ids = {q["id"] for q in topic["questions"]}
        topic["cards"] = [c for c in topic["cards"] if set(c["questionIds"]) & ids]
        for card in topic["cards"]:
            card["questionIds"] = [qid for qid in card["questionIds"] if qid in ids]
        for q in topic["questions"]:
            unresolved = set(q["prerequisites"]["refs"]) - ids
            if unresolved:
                raise ValueError(f"Template {relation['id']} has absent prerequisites: {q['id']} {unresolved}")
        # Existing local question rules remain versioned; the route does not rank areas.
        topic["match_provenance"] = {"relation": relation, "package": config["package_root"], "boundary": config["boundary"]}
        yield relation, topic


def seed(conn, config_path=RELATIONS):
    from app.infrastructure.orm import workbench_template_matches, workbench_templates
    from app.services.workbench_templates import content_hash
    from sqlalchemy import select

    result = []
    for relation, topic in build_templates(config_path):
        record = {"template_id": relation["template_id"], "version": relation["version"],
                  "title": relation["title"], "content_hash": content_hash(topic), "content_json": topic}
        prior = conn.execute(select(workbench_templates).where(
            workbench_templates.c.template_id == record["template_id"],
            workbench_templates.c.version == record["version"])).mappings().first()
        if prior:
            if prior["content_hash"] != record["content_hash"]:
                raise ValueError("Existing template version changed; publish a new version instead")
        else:
            conn.execute(workbench_templates.insert().values(**record))
        mapping = {name: relation[name] for name in workbench_template_matches.c.keys()}
        existing = conn.execute(select(workbench_template_matches).where(
            workbench_template_matches.c.id == mapping["id"])).mappings().first()
        if existing and dict(existing) != mapping:
            raise ValueError("Existing applicability relation changed")
        if not existing:
            conn.execute(workbench_template_matches.insert().values(**mapping))
        result.append({"template_id": record["template_id"], "areas": len(topic["areas"]),
                       "questions": len(topic["questions"]), "hash": record["content_hash"]})
    return result


if __name__ == "__main__":
    # Target is only the existing isolated workbench database, never project .env.
    from app.infrastructure.db_target import validate_target
    from sqlalchemy import create_engine

    from scripts.wp15_workbench import STATE, environment
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=RELATIONS)
    args = parser.parse_args()
    env = environment(json.loads(STATE.read_text(encoding="utf-8")))
    target = validate_target(env["DATABASE_URL"], "migration")
    engine = create_engine(target.sqlalchemy_url(), connect_args=target.connect_kwargs())
    with engine.begin() as conn:
        print(json.dumps(seed(conn, args.config), ensure_ascii=False, indent=2))
    engine.dispose()
