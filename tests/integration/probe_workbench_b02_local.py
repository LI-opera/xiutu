"""Bounded B02 API exercise on the owned 5215/8215 synthetic instance."""
import json
from uuid import uuid4

import httpx

from scripts.wp15_workbench import TEST_TOKEN


def main():
    with httpx.Client(base_url="http://127.0.0.1:8215/api/v2",
                      headers={"Origin": "http://localhost:5215"},
                      trust_env=False, timeout=25) as client:
        login = client.post("/auth/login", json={"token": TEST_TOKEN})
        login.raise_for_status()
        headers = {"X-CSRF-Token": login.json()["csrf_token"]}

        def post(path, body, *, key=None, expected=200):
            response = client.post(path, json=body, headers={**headers, "Idempotency-Key": key or uuid4().hex})
            if response.status_code != expected:
                raise AssertionError(f"{path}: expected {expected}, got {response.status_code} {response.text[:500]}")
            return response.json()

        def create(label):
            return post("/cases", {"vehicle": {"model": "虚拟探岳 DKVB 演示台架", "year": 2020,
                         "engine_family": "EA888 Gen3B DEMO", "engine_code": "DKVB-DEMO"},
                         "fault_description": f"【B02 独立 DEMO】{label} · 高负荷加速无力，P0299",
                         "fault_codes": ["P0299"], "diagnosis_mode": "conservative",
                         "policy_version": "b02", "topic_version": "2.2.1-b02",
                         "topic_intake": {"symptom_condition": "high_load", "safety_gate": "none"}}, expected=201)["id"]

        def get(case_id):
            response = client.get(f"/cases/{case_id}/workbench-v2")
            response.raise_for_status()
            return response.json()

        def save(case_id, state, qid, options, *, fields=None, batch=None, reason="", original=None, key=None, expected=200):
            body = {"expected_revision": state["case"]["revision"], "topic_version": "2.2.1-b02",
                    "question_id": qid, "option_ids": options, "fields": fields or {},
                    "unavailable_reason": reason, "batch_id": batch}
            endpoint = f"/cases/{case_id}/topic-observations" + (f"/{original}/correct" if original else "")
            response = post(endpoint, body, key=key, expected=expected)
            return response["view"] if expected == 200 else response

        condition_case = create("条件与首次建议准备验证")
        state = get(condition_case)
        assert len(state["topic"]["questions"]) == 78 and state["topic"]["version"] == "2.2.1-b02"
        state = save(condition_case, state, "ACT-08", ["voltage_low"])
        blocked = save(condition_case, state, "ACT-09", ["completed"], reason="填写原因不得绕过", expected=422)
        assert blocked["error"]["code"] == "PREREQUISITE_MISSING"
        assert blocked["error"]["details"]["missing"][0]["ref"] == "ACT-08"
        state = save(condition_case, state, "ACT-09", ["unavailable"], reason="设备条件不具备")
        assert state["view"]["question_states"]["ACT-09"]["status"] == "saved"
        old = state["view"]["question_states"]["ACT-08"]["observation_id"]
        state = save(condition_case, state, "ACT-08", ["ready"], original=old)
        old = state["view"]["question_states"]["ACT-09"]["observation_id"]
        state = save(condition_case, state, "ACT-09", ["completed"], original=old)
        assert state["plan"]["capture_batches"]["after_setting_new_batch"]
        # All initial required raw checks explicitly unable to obtain; the
        # derived questions must not trap the first advice readiness forever.
        questions = {q["id"]: q for q in state["topic"]["questions"]}
        for qid in list(state["plan"]["required_question_ids"]):
            if state["view"]["question_states"][qid]["status"] != "unanswered":
                continue
            question = questions[qid]
            if question["answer_kind"] == "automatic_derived":
                continue
            option = next((o["id"] for o in question["options"] if o["id"] == "unavailable"), None) or next(
                o["id"] for o in question["options"] if o["outcome"] == "unavailable")
            state = save(condition_case, state, qid, [option], reason="本轮无法取得该项")
        state = get(condition_case)
        assert state["view"]["derived"]["PRS-04"]["option_id"] == "unavailable"
        assert state["view"]["derived"]["PRS-11"]["option_id"] == "unreliable"
        assert state["view"]["ai_readiness"]["ready_for_first_advice"], {"case_id": condition_case, "missing": state["view"]["synthesis"]["missing_question_ids"], "matched_rules": state["view"]["plan_evaluation"]["matched_rule_ids"]}
        assert state["view"]["ai_readiness"]["advice_scope"] == "supplement_or_handoff"
        assert not state["view"]["ai_readiness"]["repair_conclusion_supported"]
        assert not state["view"]["final_report_gate"]["available"]

        repair_case = create("处理与复检轮次验证")
        state = get(repair_case)
        state = save(repair_case, state, "RET-01", ["none"])
        assert not state["plan"]["rounds"] and state["view"]["active_round_id"] is None
        old = state["view"]["question_states"]["RET-01"]["observation_id"]
        key = uuid4().hex
        revision = state["case"]["revision"]
        state = save(repair_case, state, "RET-01", ["reseat"], original=old, key=key)
        round_id = state["view"]["active_round_id"]
        assert round_id and len(state["plan"]["rounds"]) == 1
        repeated = post(f"/cases/{repair_case}/topic-observations/{old}/correct",
                        {"expected_revision": revision, "topic_version": "2.2.1-b02",
                         "question_id": "RET-01", "option_ids": ["reseat"], "fields": {},
                         "unavailable_reason": "", "batch_id": None}, key=key)
        assert repeated["view"]["view"]["active_round_id"] == round_id
        assert len(get(repair_case)["plan"]["rounds"]) == 1
        old = state["view"]["question_states"]["RET-01"]["observation_id"]
        state = save(repair_case, state, "RET-01", ["none"], original=old)
        assert state["view"]["active_round_id"] is None
        assert "RET-07" not in state["view"]["derived"]
        assert len(state["plan"]["rounds"]) == 1  # historical round preserved

        priority_case = create("推荐与独立记录验证")
        state = get(priority_case)
        static_batch = state["plan"]["capture_batches"]["engine_off_static"]
        for qid, value in (("PRS-01", 1005), ("PRS-02", 1450), ("PRS-03", 1008)):
            state = save(priority_case, state, qid, ["recorded"],
                         fields={"hpa": {"value": value, "unit": "hPa absolute"}}, batch=static_batch)
        state = save(priority_case, state, "TUR-01", ["crack_clue"])
        state = save(priority_case, state, "TUR-07", ["scrape"])
        assert state["view"]["areas"][1]["priority"] == 1
        prior = state["view"]["question_states"]["PRS-02"]["observation_id"]
        state = save(priority_case, state, "PRS-02", ["recorded"],
                     fields={"hpa": {"value": 1010, "unit": "hPa absolute"}}, batch=static_batch, original=prior)
        refreshed = get(priority_case)
        assert refreshed["view"]["areas"][3]["priority"] == 1
        assert [a["area_id"] for a in refreshed["view"]["areas"]] == [a["id"] for a in refreshed["topic"]["areas"]]
        assert refreshed["view"]["question_states"]["TUR-01"]["status"] == "saved"
        assert len([o for o in refreshed["observations"] if o["question_id"] == "PRS-02"]) == 2

        clean_case = create("待用户体验的干净病例")
        clean = get(clean_case)
        assert clean["observations"] == [] and clean["topic"]["version"] == "2.2.1-b02"
        print(json.dumps({"condition_case": condition_case, "repair_case": repair_case,
                          "priority_case": priority_case, "clean_case": clean_case,
                          "round_id": round_id}, ensure_ascii=False))


if __name__ == "__main__":
    main()
