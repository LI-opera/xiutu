"""Read the one C18 task and metering ledger; never prints a raw failed response."""

import json

import httpx

from scripts.legacy_analysis_ids import C18_CASE_ID as CASE_ID, ORIGIN
from scripts.wp15_workbench import TEST_TOKEN
from app.infrastructure.model_budget import BudgetLedger, LIVE_LEDGER

from scripts.legacy_analysis_ids import C18_ANALYSIS_ID as ANALYSIS_ID


def main():
    with httpx.Client(base_url="http://127.0.0.1:8215", trust_env=False, timeout=20) as client:
        login = client.post("/api/v2/auth/login", json={"token": TEST_TOKEN},
                            headers={"Origin": ORIGIN})
        login.raise_for_status()
        result = client.get(f"/api/v2/cases/{CASE_ID}/analyses/{ANALYSIS_ID}")
        result.raise_for_status()
        row = result.json()
        content = row.get("content") or {}
        listing = client.get(f"/api/v2/cases/{CASE_ID}/analyses")
        listing.raise_for_status()
        view = client.get(f"/api/v2/cases/{CASE_ID}/workbench-v2")
        view.raise_for_status()
        ledger = BudgetLedger(LIVE_LEDGER).read()
        attempts = {key: value for key, value in ledger["calls"].items()
                    if key.startswith(ANALYSIS_ID + ":")}
        first = attempts.get(ANALYSIS_ID + ":1") or {}
        print(json.dumps({
            "analysis_id": row["id"], "status": row["status"],
            "mode": row["mode"], "provider": row["provider"], "model": row["model"],
            "input_revision": row["input_revision"], "current_revision": row["current_revision"],
            "prompt_version": row["prompt_version"], "allowed_scope": row["allowed_scope"],
            "publication": content.get("publication"), "content_keys": list(content),
            "error_code": row.get("error_code"), "error_message": row.get("error_message"),
            "case_revision_after": view.json()["case"]["revision"],
            "effective_observations_after": sum(item["effective"] for item in view.json()["observations"]),
            "ret_facts_after": sum(item["effective"] and item["question_id"].startswith("RET-")
                                   for item in view.json()["observations"]),
            "current_mode": listing.json()["configuration"]["mode"],
            "paid_enabled": listing.json()["configuration"]["paid"],
            "ledger_attempts": len(attempts), "metering_status": first.get("status"),
            "usage": first.get("usage"), "finish_reason": first.get("finish_reason"),
        }, ensure_ascii=False, indent=2))
        if row["status"] == "failed":
            diagnostic = client.get(f"/api/v2/cases/{CASE_ID}/analyses/{ANALYSIS_ID}/diagnostic")
            diagnostic.raise_for_status()
            data = diagnostic.json()
            detail = data.get("diagnostic") or {}
            print(json.dumps({"availability": data.get("availability"),
                              "stage": detail.get("stage"), "sha256": detail.get("sha256"),
                              "truncated": detail.get("truncated"),
                              "error_code": detail.get("error_code"),
                              "validation": detail.get("validation")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
