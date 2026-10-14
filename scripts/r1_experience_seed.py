"""Seed the existing formal experience instance with bounded R1 synthetic material."""

import json
import os
import time
from pathlib import Path
from uuid import uuid4

import httpx

from app.agents.trusted_protocol import PROFILE


ROOT = Path(__file__).resolve().parents[1]
WP15_SOURCE = os.environ.get("R1_WP15_SOURCE") == "1"
RUNTIME = ROOT / ".local-data" / ("wp15-workbench" if WP15_SOURCE else "formal-user-experience-r1")
SOURCE = ROOT / "tests" / "fixtures" / "diagnosis-slice" / "dkvb-guided.md"
ORIGIN = "http://localhost:5215"
API = "http://127.0.0.1:8215"


def wait_run(client: httpx.Client, run_id: str, *, waiting_input=False) -> None:
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        response = client.get(f"/api/v2/runs/{run_id}")
        response.raise_for_status()
        status = response.json()["status"]
        if status == "succeeded" or (waiting_input and status == "waiting_input"):
            return
        if status in {"failed", "cancelled"}:
            raise RuntimeError(f"R1 seed run ended as {status}")
        time.sleep(0.25)
    raise RuntimeError("R1 seed run timed out")


def main() -> None:
    state = json.loads((RUNTIME / ("runtime.json" if WP15_SOURCE else "runtime.private.json")).read_text(encoding="utf-8"))
    if WP15_SOURCE:
        from wp15_workbench import TEST_TOKEN
        state["token"] = TEST_TOKEN
    headers = {"Origin": ORIGIN}
    with httpx.Client(base_url=API, headers=headers, trust_env=False, timeout=30) as client:
        login = client.post("/api/v2/auth/login", json={"token": state["token"]})
        login.raise_for_status()
        write_headers = {"Origin": ORIGIN, "X-CSRF-Token": login.json()["csrf_token"]}
        metadata = {
            "title": "DKVB P0299 保守协议资料（R1 DEMO）",
            "source_kind": "synthetic_fixture",
            "source_reference": "R1 local synthetic protocol fixture",
            "source_status": "unknown",
            "license_status": "unknown",
            "scope": {
                "model": PROFILE["model"],
                "year_from": PROFILE["year"],
                "year_to": PROFILE["year"],
                "engine_family": PROFILE["engine_family"],
                "engine_code": PROFILE["engine_code"],
            },
            "synthetic": True,
        }
        if os.environ.get("R1_CASES_ONLY") != "1":
            upload = client.post(
                "/api/v2/documents",
                headers={**write_headers, "Idempotency-Key": "r1-source-" + uuid4().hex},
                files={
                    "file": (SOURCE.name, SOURCE.read_bytes(), "text/markdown"),
                    "metadata": (None, json.dumps(metadata, ensure_ascii=False), "application/json"),
                },
            )
            upload.raise_for_status()
            source = upload.json()
            wait_run(client, source["run_id"])
            review = client.post(
                f"/api/v2/documents/{source['document_id']}/versions/{source['version_id']}/review",
                headers={**write_headers, "Idempotency-Key": "r1-review-" + uuid4().hex},
                json={
                    "decision": "approved",
                    "scope": metadata["scope"],
                    "source_status": "unknown",
                    "license_status": "unknown",
                    "review_note": "Synthetic R1 experience fixture; not real repair evidence.",
                },
            )
            review.raise_for_status()
            wait_run(client, review.json()["index_run_id"])
        if os.environ.get("R1_SOURCE_ONLY") == "1":
            print(json.dumps({"status": "source_ready", "synthetic": True,
                              "formal_usable": False}, ensure_ascii=False))
            return
        cases = []
        if os.environ.get("R1_WORKBENCH_01_CASES") == "1":
            suffixes = (
                "【验证参考】R1-WORKBENCH-01 最长路径",
                "【验证参考】R1-WORKBENCH-01 保守交接",
                "【待体验】R1-WORKBENCH-01 最长路径",
                "【待体验】R1-WORKBENCH-01 保守交接",
            )
        else:
            suffixes = (("R1-FLOW-02 数据继承与最长路径", "R1-FLOW-02 测量不可信交接")
                    if os.environ.get("R1_FLOW_02_CASES") == "1" else
                    (("R1-FLOW-01 测量不可信交接",) if os.environ.get("R1_FLOW_LAST") == "1" else
                    ("R1-FLOW-01 泄漏处理后直接恢复", "R1-FLOW-01 测量不可信交接")
                    if os.environ.get("R1_FLOW_REMAINING") == "1" else
                    ("R1-FLOW-01 最长完整路径", "R1-FLOW-01 泄漏处理后直接恢复", "R1-FLOW-01 测量不可信交接")) if os.environ.get("R1_FLOW_CASES") == "1" else ("R1 完整路径", "R1 无法检查路径"))
        existing_by_title = {}
        if os.environ.get("R1_WORKBENCH_01_CASES") == "1":
            cursor = None
            while True:
                params = {"limit": 50}
                if cursor:
                    params["cursor"] = cursor
                page = client.get("/api/v2/cases", params=params)
                page.raise_for_status()
                payload = page.json()
                for item in payload["items"]:
                    existing_by_title[item["fault_description"]] = item
                cursor = payload.get("next_cursor")
                if not cursor:
                    break
        for suffix in suffixes:
            if suffix in existing_by_title:
                cases.append({"id": existing_by_title[suffix]["id"], "path": suffix})
                continue
            response = client.post(
                "/api/v2/cases",
                headers={**write_headers, "Idempotency-Key": "r1-case-" + uuid4().hex},
                json={
                    "vehicle": PROFILE,
                    "fault_description": suffix if os.environ.get("R1_WORKBENCH_01_CASES") == "1" else f"【待体验】{suffix}",
                    "fault_codes": ["P0299"],
                    "diagnosis_mode": "conservative",
                    "policy_version": "r1",
                },
            )
            response.raise_for_status()
            case = response.json()
            if os.environ.get("R1_FLOW_CASES") == "1" and os.environ.get("R1_FLOW_02_CASES") != "1":
                started = client.post(
                    f"/api/v2/cases/{case['id']}/diagnosis/runs",
                    headers={**write_headers, "Idempotency-Key": "r1-start-" + uuid4().hex},
                    json={"expected_revision": case["revision"]},
                )
                started.raise_for_status()
                wait_run(client, started.json()["run_id"], waiting_input=True)
            cases.append({"id": case["id"], "path": suffix})
        print(json.dumps({"status": "seeded", "synthetic": True, "formal_usable": False,
                          "cases": cases}, ensure_ascii=False))


if __name__ == "__main__":
    main()
