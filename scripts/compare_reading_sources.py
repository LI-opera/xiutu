"""Read-only check: stored chunks/vectors choose exactly the sections computing them now would.

For every template case of the local workspace, builds the combined analysis input twice --
once searching the chunks and vectors stored at ingest, once splitting and embedding the
bodies now -- and compares the frozen-input identity (any difference in sent text or reading
guide changes it). Runs in a transaction that is rolled back; no model is called.

    uv run python -B scripts/compare_reading_sources.py
"""
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "backend")]

from sqlalchemy import create_engine, select  # noqa: E402

from scripts.wp15_workbench import STATE, environment  # noqa: E402


def main():
    state = json.loads(STATE.read_text(encoding="utf-8"))
    os.environ.update(environment(state))
    from app.config import load_settings
    from app.infrastructure.db_target import validate_target
    from app.infrastructure.orm import cases
    from app.services import reference_store
    from app.services.area_analysis_service import (
        MATCHED_SCOPE_ID,
        AreaAnalysisService,
        input_identity,
    )
    from app.services.case_service import CaseService
    from app.services.workbench_templates import is_template

    settings = load_settings()
    target = validate_target(os.environ["DATABASE_URL"], "migration")
    engine = create_engine(target.sqlalchemy_url(), connect_args=target.connect_kwargs())
    service = AreaAnalysisService(CaseService(engine, b"read-only-compare"), settings)
    print("加载向量模型…", file=sys.stderr, flush=True)
    service.reading_embeddings.warm()
    used = {"stored": 0, "computed": 0}
    real_load = reference_store.load

    def counting(conn, document, embeddings):
        source, always = real_load(conn, document, embeddings)
        used["stored" if source is not None else "computed"] += 1
        return source, always

    def computed_only(conn, document, embeddings):
        # What happens without stored data: compute now, with the row's always-sent sections.
        return None, real_load(conn, document, embeddings)[1]

    report = []
    with engine.connect() as conn:
        with conn.begin():
            rows = conn.execute(select(cases).where(cases.c.owner_id == state["actor"])
                                .order_by(cases.c.created_at)).mappings().all()
        targets = [r for r in rows if is_template(r)]
        print(f"共 {len(targets)} 个模板病例", file=sys.stderr, flush=True)
        for number, row in enumerate(targets, 1):
            print(f"  {number}/{len(targets)} {str(row['id'])[:8]}", file=sys.stderr, flush=True)
            transaction = conn.begin()  # one short read-only transaction per case, rolled back
            try:
                view = service._view(conn, state["actor"], row["id"])
                reference_store.load = counting
                started = time.perf_counter()
                stored = service._payload(conn, view, MATCHED_SCOPE_ID)
                stored_ms = (time.perf_counter() - started) * 1000
                reference_store.load = computed_only
                started = time.perf_counter()
                computed = service._payload(conn, view, MATCHED_SCOPE_ID)
                computed_ms = (time.perf_counter() - started) * 1000
            finally:
                reference_store.load = real_load
                transaction.rollback()
            same = input_identity(stored) == input_identity(computed)
            entry = {"case": str(row["id"])[:8], "documents": len(stored["documents"]), "same": same,
                     "stored_ms": round(stored_ms), "computed_ms": round(computed_ms)}
            if not same:
                entry["differences"] = [
                    {"area": a["area_id"], "document": a_doc["document_id"],
                     "stored": [s["heading"] for s in a_doc["sections"]],
                     "computed": [s["heading"] for s in b_doc["sections"]]}
                    for a, b in zip(stored["reference_reading_guide"], computed["reference_reading_guide"])
                    for a_doc, b_doc in zip(a["documents"], b["documents"])
                    if a_doc["sections"] != b_doc["sections"]]
            report.append(entry)
    engine.dispose()
    print(json.dumps({"cases": len(report), "all_same": all(r["same"] for r in report),
                      "document_searches": used, "results": report}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
