"""C19 open advice: JSON shape and storage only, never technical-content approval."""

from app.domain.case_analysis import CaseAdviceOpenV1, CaseAdviceOpenV2
from app.services.case_analysis_context import OUTPUT_CONTRACT_VERSION, PREVIOUS_OUTPUT_CONTRACT_VERSION

VERSION = OUTPUT_CONTRACT_VERSION


def _model(snapshot):
    version = snapshot["output_contract_version"]
    if version == VERSION:
        return CaseAdviceOpenV2
    if version == PREVIOUS_OUTPUT_CONTRACT_VERSION:
        return CaseAdviceOpenV1
    raise ValueError("Unknown C19 output contract")


def assemble(snapshot, raw):
    value = _model(snapshot).model_validate(raw).model_dump(mode="json")
    value["publication"] = {"contract_version": snapshot["output_contract_version"]}
    return value


def validate(snapshot, content):
    # This is a storage/rendering invariant, not an evidence or operation review.
    value = _model(snapshot).model_validate({key: value for key, value in content.items()
                                             if key != "publication"}).model_dump(mode="json")
    if content.get("publication") != {"contract_version": snapshot["output_contract_version"]}:
        raise ValueError("C19 content contract mismatch")
    value["publication"] = {"contract_version": snapshot["output_contract_version"]}
    return value


def substitute(snapshot):
    """Explicit local test sample through the same assembler; not model output."""
    observations = snapshot["observations"]
    anchor = observations[0] if observations else None
    unresolved = snapshot.get("unresolved_questions", [])
    existing_questions = {item["question_id"] for item in observations}
    missing = unresolved[0] if unresolved else None
    if not missing:
        missing = next(({"question_id": item["id"]} for item in snapshot.get("question_catalog", [])
                        if item["id"] not in existing_questions and not item["id"].startswith(("IN-", "RET-"))
                        and item["answer_kind"] != "automatic_derived"), None)
    proposal = {
        "summary": "替身测试：根据已保存的模拟观察，优先核对异常出现的部位；这不是实车结论。",
        "directions": [{"title": "增压空气连接处可能影响压力表现",
                        "explanation": "此方向只用于演示事实引用和可读分析。",
                        "basis_observation_ids": [anchor["id"]] if anchor else []}],
        "missing": ([{"question_id": missing["question_id"],
                      "missing": "该题尚未记录",
                      "reason": "确定观察能否用于后续判断",
                      "suggestion": "在原问题中补充或更正记录"}] if missing else []),
        "steps": [{"kind": "repair", "action": "替身测试步骤：核对接头状态，再依据现场和原始资料决定是否处理。",
                   "basis_observation_ids": [anchor["id"]] if anchor else [],
                   "question_ids": [missing["question_id"]] if missing else []}],
        "precautions": ["替身内容仅验证正式保存与导航链路。"],
        "verification": "如实际实施处理，应另行记录处理及复检；本替身未写入这些事实。",
        "if_unresolved": "继续核对现场条件与资料。",
        "uncertainty": "模拟数据不能替代实车检查。",
    }
    return assemble(snapshot, proposal)
