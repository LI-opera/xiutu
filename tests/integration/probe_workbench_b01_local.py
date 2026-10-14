"""Bounded synthetic B01 local-instance exercise, no model or external calls."""
import json
import uuid

import httpx

from scripts.wp15_workbench import TEST_TOKEN

API = "http://127.0.0.1:8215/api/v2"
ORIGIN = "http://localhost:5215"


def main():
    with httpx.Client(base_url=API, headers={"Origin": ORIGIN}, trust_env=False, timeout=25) as client:
        login = client.post("/auth/login", json={"token": TEST_TOKEN})
        login.raise_for_status()
        headers = {"Origin": ORIGIN, "X-CSRF-Token": login.json()["csrf_token"]}
        def post(path, body):
            response = client.post(path, json=body, headers={**headers, "Idempotency-Key": "b01-"+uuid.uuid4().hex})
            if response.status_code >= 400:
                raise RuntimeError(f"{path}: {response.status_code} {response.text[:900]}")
            return response.json()
        def create(label):
            return post("/cases", {"vehicle": {"model": "虚拟探岳 DKVB 演示台架", "year": 2020,
                            "engine_family": "EA888 Gen3B DEMO", "engine_code": "DKVB-DEMO"},
                    "fault_description": f"【B01 独立 DEMO】{label} · 高负荷加速无力，P0299",
                    "fault_codes": ["P0299"], "diagnosis_mode": "conservative", "policy_version": "b01",
                    "topic_version": "2.2.0-b01", "topic_intake": {"symptom_condition": "high_load", "safety_gate": "none"}})
        work = create("集成验证")
        case_id = work["id"]
        path = f"/cases/{case_id}"
        def view():
            response = client.get(path+"/workbench-v2")
            if response.status_code >= 400: raise RuntimeError(f"GET view: {response.status_code} {response.text[:900]}")
            return response.json()
        current = view()
        assert len(current["topic"]["questions"]) == 78
        def save(qid, options, *, fields=None, note="实际观察", unavailable="", batch=None, round_id=None, original=None):
            nonlocal current
            body = {"expected_revision": current["case"]["revision"], "topic_version": "2.2.0-b01",
                    "question_id": qid, "option_ids": options, "fields": fields or {}, "note": note,
                    "unavailable_reason": unavailable, "batch_id": batch, "round_id": round_id}
            if original: body["correction_reason"] = "复核后更正实际读数"
            endpoint = path+"/topic-observations" + (f"/{original}/correct" if original else "")
            current = post(endpoint, body)["view"]
            return current
        questions = {q["id"]: q for q in current["topic"]["questions"]}
        def normal(qid):
            return next(o["id"] for o in questions[qid]["options"] if o["outcome"] == "normal")
        for qid in ("AIR-07", "PRS-07", "ACT-01", "TUR-01", "X-01"):
            save(qid, [normal(qid)], note="B01 synthetic user observation")
        assert {x["question_id"] for x in current["observations"]} >= {"AIR-07", "PRS-07", "ACT-01", "TUR-01", "X-01"}
        expected_revision = current["case"]["revision"]
        idempotent_body = {"expected_revision": expected_revision, "topic_version": "2.2.0-b01",
                           "question_id": "AIR-04", "option_ids": [normal("AIR-04")],
                           "note": "幂等验证"}
        fixed_headers = {**headers, "Idempotency-Key": "b01-fixed-"+uuid.uuid4().hex}
        first_save = client.post(path+"/topic-observations", json=idempotent_body, headers=fixed_headers)
        first_save.raise_for_status()
        repeated = client.post(path+"/topic-observations", json=idempotent_body, headers=fixed_headers)
        repeated.raise_for_status()
        assert first_save.json()["observation_id"] == repeated.json()["observation_id"]
        changed = client.post(path+"/topic-observations", json={**idempotent_body, "note": "不同请求"}, headers=fixed_headers)
        assert changed.status_code == 409 and changed.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"
        stale = client.post(path+"/topic-observations", json={**idempotent_body, "question_id": "AIR-05"},
                            headers={**headers, "Idempotency-Key": "b01-stale-"+uuid.uuid4().hex})
        assert stale.status_code == 409
        current = view()
        static_batch = current["plan"]["capture_batches"]["engine_off_static"]
        for qid, value in (("PRS-01", 1005), ("PRS-02", 1010), ("PRS-03", 1008)):
            save(qid, ["recorded"], fields={"hpa": {"value": value, "unit": "hPa absolute"}}, batch=static_batch)
        assert current["view"]["derived"]["PRS-04"]["option_id"] == "consistent"
        old_pressure = current["view"]["question_states"]["PRS-02"]["observation_id"]
        save("PRS-02", ["recorded"], fields={"hpa": {"value": 1450, "unit": "hPa absolute"}},
             batch=static_batch, original=old_pressure)
        assert current["view"]["derived"]["PRS-04"]["option_id"] == "g31_outlier"
        assert current["view"]["question_states"]["TUR-01"]["status"] == "saved"
        save("AIR-08", ["unavailable"], unavailable="当前无法安全接近接头")
        save("RET-01", ["reseat"], note="实际复位接头并检查锁止")
        round_id = current["view"]["active_round_id"]
        save("RET-03", ["not_comparable"], unavailable="无法重现相同负荷", round_id=round_id)
        save("RET-04", ["unavailable"], unavailable="新批次未取得可靠三帧", round_id=round_id)
        save("PRS-05", [normal("PRS-05")], note="开启复检后补录的独立处理前观察")
        assert current["view"]["question_states"]["PRS-05"]["status"] == "saved"
        assert next(r for r in current["observations"] if r["question_id"] == "PRS-05")["round_id"] is None
        reloaded = view()
        assert reloaded["view"]["active_round_id"] == round_id
        assert reloaded["view"]["question_states"]["PRS-02"]["option_ids"] == ["recorded"]
        assert len([r for r in reloaded["observations"] if r["question_id"] == "PRS-02"]) == 2
        assert reloaded["view"]["derived"]["RET-07"]["option_id"] == "critical"
        # Cross the legacy 50-effective/100-history read windows through the
        # public API. The same independent DEMO case is used; no direct SQL.
        for q in questions.values():
            if len([r for r in current["observations"] if r["effective"]]) > 50:
                break
            if q["stage"] in {"S0", "S6"} or q["answer_kind"] in {"automatic_derived", "conditional_operation"}:
                continue
            qid = q["id"]
            if current["view"]["question_states"][qid]["observation_id"]:
                continue
            unavailable = next((o for o in q["options"] if o["outcome"] == "unavailable"), None)
            if unavailable:
                save(qid, [unavailable["id"]], unavailable="边界验证：未进行实际检查")
        assert len([r for r in current["observations"] if r["effective"]]) > 50
        for index in range(53):
            prior = current["view"]["question_states"]["PRS-02"]["observation_id"]
            save("PRS-02", ["recorded"], fields={"hpa": {"value": 1450 + index + 1, "unit": "hPa absolute"}},
                 batch=static_batch, original=prior)
        assert len(current["observations"]) > 100
        first = client.get(path+"/topic-observations/history", params={"limit": 50})
        first.raise_for_status()
        first_page = first.json()
        assert len(first_page["items"]) == 50 and first_page["next"]
        cursor = first_page["next"]
        second = client.get(path+"/topic-observations/history", params={"limit": 100,
                            "after_revision": cursor["revision"], "after_id": cursor["id"]})
        second.raise_for_status()
        all_ids = [r["id"] for r in first_page["items"] + second.json()["items"]]
        assert len(all_ids) == len(set(all_ids)) == len(current["observations"])
        clean = create("待用户体验的干净病例")
        clean_view = client.get(f"/cases/{clean['id']}/workbench-v2").json()
        assert not clean_view["observations"]
        print(json.dumps({"verified_case_id": case_id, "clean_case_id": clean["id"],
                          "saved_observations": len(current["observations"]), "round_id": round_id,
                          "derived_static": reloaded["view"]["derived"]["PRS-04"]["option_id"]}, ensure_ascii=False))


if __name__ == "__main__": main()
