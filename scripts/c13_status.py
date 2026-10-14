"""Read-only status for the single C13 analysis; never prints credentials or raw diagnostics."""

import json

import httpx

from scripts.legacy_analysis_ids import C13_CASE_ID as CASE_ID
from app.infrastructure.model_budget import BudgetLedger, LIVE_LEDGER
from scripts.wp15_workbench import TEST_TOKEN

from scripts.legacy_analysis_ids import C13_ANALYSIS_ID as ANALYSIS_ID


def main():
    with httpx.Client(base_url="http://127.0.0.1:8215", trust_env=False, timeout=20) as client:
        login = client.post("/api/v2/auth/login", json={"token": TEST_TOKEN},
                            headers={"Origin": "http://localhost:5215"})
        login.raise_for_status()
        result = client.get(f"/api/v2/cases/{CASE_ID}/analyses/{ANALYSIS_ID}")
        result.raise_for_status()
        row = result.json()
        content = row.get("content") or {}
        publication = content.get("publication") or {}
        listing = client.get(f"/api/v2/cases/{CASE_ID}/analyses")
        listing.raise_for_status()
        view = client.get(f"/api/v2/cases/{CASE_ID}/workbench-v2")
        view.raise_for_status()
        ledger = BudgetLedger(LIVE_LEDGER).read()
        metering = ledger["calls"].get(f"{ANALYSIS_ID}:1") or {}
        print(json.dumps({
            "analysis_id": row.get("id"), "status": row.get("status"),
            "run_status": row.get("run_status"), "mode": row.get("mode"),
            "model": row.get("model"), "input_revision": row.get("input_revision"),
            "publication": publication, "error_code": row.get("error_code"),
            "error_message": row.get("error_message"),
            "content_keys": list(content),
            "current_mode": listing.json()["configuration"]["mode"],
            "paid": listing.json()["configuration"]["paid"],
            "case_revision_after": view.json()["case"]["revision"],
            "effective_observations_after": sum(item["effective"] for item in view.json()["observations"]),
            "post_treatment_facts_after": sum(item["effective"] and item["question_id"].startswith("RET-")
                                              for item in view.json()["observations"]),
            "metering_status": metering.get("status"),
            "metering_usage": metering.get("usage"),
            "metering_finish_reason": metering.get("finish_reason"),
        }, indent=2))
        if row.get("status") == "failed":
            diagnostic = client.get(f"/api/v2/cases/{CASE_ID}/analyses/{ANALYSIS_ID}/diagnostic")
            diagnostic.raise_for_status()
            payload = diagnostic.json()
            detail = payload.get("diagnostic") or {}
            print(json.dumps({
                "diagnostic_availability": payload.get("availability"),
                "response": {key: detail.get(key) for key in
                             ("stage", "error_code", "sha256", "truncated",
                              "response_utf8_bytes", "response_characters")},
                "validation": detail.get("validation"),
            }, indent=2))


if __name__ == "__main__":
    main()
