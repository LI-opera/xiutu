import hashlib
import json

from langchain_core.tools import StructuredTool
from langchain_core.utils.function_calling import convert_to_openai_tool

from app.tools.schemas import INPUTS, OUTPUTS

DESCRIPTIONS = {
    "search_manuals": "Search reviewed manuals in the trusted case frozen corpus. Scope only narrows. Empty means no eligible matches; never invent repair facts.",
    "get_evidence_context": "Read a permitted chunk and at most two neighbors each side in the same version. Requires current source authorization, returns locators; chunk ID is not evidence ID.",
    "get_measurement_spec": "List approved applicable specifications for this case and component/quantity. Multiple candidates require selection; empty is not a fabricated standard.",
    "compare_measurement": "Compare a measurement using a currently approved case specification and required conditions. Persists one idempotent comparison; within_range is not diagnosis.",
    "get_case_observations": "Read real immutable observations at an allowed case revision, optionally area filtered. Empty means no recorded observations; this tool never writes observations.",
}


def langchain_tool(executor, context, name, call_key):
    # Logical call identity is bound by trusted caller, absent from model args_schema.
    def invoke(**kwargs):
        return executor.execute(context, name, kwargs, call_key)

    return StructuredTool.from_function(
        func=invoke,
        name=name,
        description=DESCRIPTIONS[name],
        args_schema=INPUTS[name],
        handle_validation_error=lambda _: json.dumps(executor.error("PARAM_INVALID")),
    )


def export_schemas():
    result = {}
    for name, model in INPUTS.items():
        tool = StructuredTool.from_function(
            func=lambda **kwargs: None, name=name, description=DESCRIPTIONS[name], args_schema=model
        )
        exported = convert_to_openai_tool(tool)
        # SDK's tool_call_schema removes object config. Preserve the actual args_schema,
        # including typed condition maps; provider strict mode would forbid their keys.
        exported["function"]["parameters"] = tool.get_input_schema().model_json_schema()
        result[name] = dict(
            input=model.model_json_schema(),
            output=OUTPUTS[name].model_json_schema(),
            langchain=exported,
        )
    raw = json.dumps(result, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return dict(
        schemas=result, sha256=hashlib.sha256(raw.encode()).hexdigest(), allowlist=list(INPUTS)
    )
