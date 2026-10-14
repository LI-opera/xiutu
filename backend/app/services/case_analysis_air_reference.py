"""Case-bound, versioned Markdown excerpts; no changes to the topic or case facts."""

import hashlib
import json
from pathlib import Path

PACK_PATH = Path(__file__).resolve().parents[1] / "topics" / "tanyue_air_reference_v1.json"


def reference_context(case_id):
    pack = json.loads(PACK_PATH.read_text(encoding="utf-8"))
    if str(case_id) not in pack["case_ids"]:
        return None
    context = pack["context"]
    digest = hashlib.sha256(json.dumps(context, ensure_ascii=False,
                                     sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {**context, "hash": digest}


def authorize_context_window(snapshot, case_id, revision, key, environ):
    """An explicit new-context grant never resets an earlier paid attempt."""
    digest = environ.get("XIUTU_C19_ALLOWED_CONTEXT_HASH")
    if not digest:
        return None
    expected_key = environ.get("XIUTU_C05_ALLOWED_KEY", "")
    if (digest != snapshot["source_context"]["hash"]
            or snapshot["source_context"].get("version") != "air-reference-1.0-c19"
            or environ.get("XIUTU_C05_ALLOWED_CASE_ID") != str(case_id)
            or environ.get("XIUTU_C05_ALLOWED_REVISION") != str(revision)
            or not key or key != expected_key):
        from app.domain.policies import DomainError
        raise DomainError("PAID_CALL_SCOPE_DENIED", "本次资料版本授权不匹配", 403)
    grant = {"context_hash": digest, "key_sha256": hashlib.sha256(key.encode()).hexdigest()}
    prompt_version = environ.get("XIUTU_C19_ALLOWED_PROMPT_VERSION")
    if prompt_version:
        from app.services.case_analysis_context import OUTPUT_CONTRACT_VERSION, PROMPT_VERSION
        if (prompt_version != PROMPT_VERSION or snapshot.get("prompt_version") != prompt_version
                or snapshot.get("output_contract_version") != OUTPUT_CONTRACT_VERSION):
            from app.domain.policies import DomainError
            raise DomainError("PAID_CALL_SCOPE_DENIED", "本次提示词与契约授权不匹配", 403)
        grant.update(prompt_version=prompt_version, output_contract_version=OUTPUT_CONTRACT_VERSION)
    return grant
