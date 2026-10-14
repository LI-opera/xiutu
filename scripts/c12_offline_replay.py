"""Read-only C10 replay against its original frozen snapshot; no model task.

The owner-checked loader verifies the retained response hash and failed row.
Only bounded publication metadata is printed, never the model response.
"""

import json

from scripts.c11_offline_replay import ANALYSIS_ID, CASE_ID, load_frozen
from app.legacy_execution.case_analysis import assemble_proposal, validate_advice


def main():
    snapshot, proposal, diagnostic, row = load_frozen()
    published = validate_advice(snapshot, assemble_proposal(snapshot, proposal))
    print(json.dumps({
        "label": "C10 原响应的 C12 离线校验结果；未发布为病例建议",
        "case_id": str(CASE_ID), "analysis_id": str(ANALYSIS_ID),
        "original_status": row["status"], "input_revision": row["input_revision"],
        "original_contract": snapshot["output_contract_version"],
        "raw_sha256": diagnostic["sha256"],
        "raw_complete": not diagnostic["truncated"],
        "offline_publication": published["publication"],
        "direction_count": len(published["supported_directions"]),
        "published_step_indices": [index for index in range(len(proposal["steps"]))
                                   if not any(item["field_path"].startswith(f"steps[{index}]")
                                              for item in published["publication"]["rejected_sections"])],
        "published_controlled_action_ids": [step["action_id"] for step in published["steps"]
                                            if step["action_id"]],
        "retest_published": published["retest_plan"] is not None,
        "case_or_analysis_written": False,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
