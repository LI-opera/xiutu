"""DeepSeek gateway: native tool IDs, bounded JSON repair and shared paid ledger."""

import hashlib
import json
import re
import time
from copy import deepcopy
from uuid import uuid4

import httpx
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.messages.utils import convert_to_messages, convert_to_openai_messages
from langchain_deepseek import ChatDeepSeek
from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    ContentFilterFinishReasonError,
    LengthFinishReasonError,
)
from pydantic import ValidationError

from app.infrastructure.model_budget import (LIVE_LEDGER, MAX_MODEL_OUTPUT_TOKENS,
                                             BudgetError, BudgetLedger)


class ModelError(Exception):
    def __init__(self, code, *, details=None):
        self.code = code
        self.details = details
        super().__init__(code)


def structured_schema_instruction(schema):
    """Exact schema message sent by the one-shot structured-output path."""
    return "Return JSON only matching this schema: " + json.dumps(schema)


def _length_completion(error):
    """Read only fields actually present on the SDK's incomplete completion."""
    completion = getattr(error, "completion", None)
    choices = getattr(completion, "choices", None) or []
    choice = choices[0] if choices else None
    raw = getattr(getattr(choice, "message", None), "content", None)
    raw = raw if isinstance(raw, str) else None
    provider_usage = getattr(completion, "usage", None)
    prompt = getattr(provider_usage, "prompt_tokens", None)
    output = getattr(provider_usage, "completion_tokens", None)
    total = getattr(provider_usage, "total_tokens", None)
    usage = ({"input_tokens": prompt, "output_tokens": output, "total_tokens": total}
             if all(type(value) is int and value >= 0 for value in (prompt, output, total))
             else None)
    model = getattr(completion, "model", None)
    finish_reason = getattr(choice, "finish_reason", None) or "length"
    return raw, usage, model if isinstance(model, str) else None, finish_reason


def redact(value):
    value = re.sub(r"(?i)\b[A-HJ-NPR-Z0-9]{17}\b", "[VIN]", value)
    value = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[EMAIL]", value)
    return re.sub(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)", "[PHONE]", value)


def _redact_json(value):
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, list):
        return [_redact_json(item) for item in value]
    if isinstance(value, dict):
        # Keys carry structure: reject sensitive keys rather than rename/collide them.
        if any(redact(key) != key for key in value):
            raise ModelError("MODEL_MESSAGE_UNSUPPORTED")
        return {key: _redact_json(item) for key, item in value.items()}
    return value


def outbound_messages(messages):
    """Copy and sanitize only supported data fields; never rewrite protocol identities."""
    try:
        normalized = convert_to_messages(deepcopy(messages))
        # Validate before the SDK can flatten text blocks or discard unknown block fields.
        for message in normalized:
            if isinstance(message.content, list):
                for block in message.content:
                    if (not isinstance(block, dict) or set(block) != {"type", "text"}
                            or block["type"] != "text" or not isinstance(block["text"], str)):
                        raise ValueError()
        wire = convert_to_openai_messages(normalized)
        for message in wire:
            if not set(message) <= {"role", "content", "name", "tool_calls", "tool_call_id"}:
                raise ValueError()
            content = message.get("content")
            if isinstance(content, str):
                message["content"] = redact(content)
            elif isinstance(content, list):
                for block in content:
                    if (not isinstance(block, dict) or set(block) != {"type", "text"}
                            or block["type"] != "text" or not isinstance(block["text"], str)):
                        raise ValueError()
                    block["text"] = redact(block["text"])
            elif content is not None:
                raise ValueError()
            for call in message.get("tool_calls", []):
                if set(call) != {"id", "type", "function"} or call["type"] != "function":
                    raise ValueError()
                function = call["function"]
                if set(function) != {"name", "arguments"}:
                    raise ValueError()
                # Parse before sanitizing text leaves; keep numbers/bools/null and IDs intact.
                arguments = json.loads(function["arguments"])
                if not isinstance(arguments, dict):
                    raise ValueError()
                function["arguments"] = json.dumps(
                    _redact_json(arguments), ensure_ascii=False, allow_nan=False
                )
        return wire
    except (ValueError, TypeError, KeyError, AttributeError, NotImplementedError):
        raise ModelError("MODEL_MESSAGE_UNSUPPORTED") from None


class DeepSeekGateway:
    def __init__(
        self,
        settings,
        *,
        paid=False,
        transport=None,
        ledger=None,
        turn_id=None,
        prompt_version="wp09-v1",
        turn_seconds_remaining=120,
        resume_existing=False,
        max_output_tokens=768,
        max_model_calls=5,
        input_profile="default",
    ):
        if settings.llm_provider != "deepseek":
            raise ModelError("LLM_PROVIDER_UNKNOWN")
        if not settings.deepseek_api_key:
            raise ModelError("MODEL_CONFIG_UNAVAILABLE")
        if settings.deepseek_base_url.rstrip("/") not in (
            "https://api.deepseek.com",
            "https://api.deepseek.com/v1",
        ):
            raise ModelError("MODEL_TARGET_DENIED")
        if not paid and not isinstance(transport, httpx.MockTransport):
            raise ModelError("PAID_CALL_NOT_AUTHORIZED")
        if paid and transport is not None:
            raise ModelError("PAID_TRANSPORT_INVALID")
        self.ledger = BudgetLedger(LIVE_LEDGER) if paid else ledger
        if self.ledger is None:
            raise ModelError("MODEL_LEDGER_REQUIRED")
        ledger_state = self.ledger.read()  # Never initialize/reset on call or restart.
        if ledger_state["version"] != 2:
            raise ModelError("BUDGET_POLICY_MIGRATION_REQUIRED")
        self.model = settings.deepseek_model
        self.turn = turn_id or uuid4().hex
        self.prompt_version = prompt_version
        if not 0 < turn_seconds_remaining <= 120:
            raise ModelError("MODEL_TURN_TIMEOUT")
        self.started = time.monotonic() - (120 - turn_seconds_remaining)
        self.calls = (
            sum(key.startswith(self.turn + ":") for key in ledger_state["calls"])
            if resume_existing else 0
        )
        self.trace = []
        if type(max_model_calls) is not int or not 1 <= max_model_calls <= 5:
            raise ModelError("MODEL_CALL_LIMIT_INVALID")
        self.call_limit = max_model_calls
        self.input_profile = input_profile
        if (type(max_output_tokens) is not int
                or not 256 <= max_output_tokens <= MAX_MODEL_OUTPUT_TOKENS):
            raise ModelError("MODEL_OUTPUT_LIMIT_INVALID")
        self.max_tokens = max_output_tokens
        self.http = httpx.Client(
            transport=transport,
            timeout=90 if input_profile == "matched_areas" else 30,
            follow_redirects=False,
            trust_env=False,
        )
        self.adapter = ChatDeepSeek(
            model=self.model,
            api_key=settings.deepseek_api_key.get_secret_value(),
            base_url=settings.deepseek_base_url,
            max_retries=0,
            max_tokens=self.max_tokens,
            http_client=self.http,
            temperature=0,
            extra_body={"thinking": {"type": "disabled"}},
        )

    def close(self):
        self.http.close()

    def health_config(self):
        return dict(
            provider="deepseek",
            model=self.model,
            configured=True,
            verified=False,
            prompt_version=self.prompt_version,
        )

    def request(self, messages, *, retry_transient=True, on_response=None, **options):
        if not set(options) <= {"tools", "response_format"}:
            raise ModelError("MODEL_OPTIONS_DENIED")
        mode = "tools" if "tools" in options else "json" if "response_format" in options else "plain"
        wire = outbound_messages(messages)
        for attempt in range(2):
            if self.calls >= self.call_limit or time.monotonic() - self.started >= 120:
                raise ModelError("MODEL_TURN_BUDGET_EXHAUSTED")
            self.calls += 1
            key = self.turn + ":" + str(self.calls)
            start = time.monotonic()
            payload = json.dumps(dict(messages=wire, options=options), ensure_ascii=False)
            try:
                self.ledger.reserve(key, self.model, payload, self.max_tokens,
                                    input_profile=self.input_profile)
            except BudgetError as e:
                raise ModelError(str(e)) from None
            # reserve may wait on another process. Recheck immediately before dispatch.
            if time.monotonic() - self.started >= 120:
                self.ledger.finish(
                    key, dict(status="not_sent", error_code="MODEL_TURN_TIMEOUT",
                              usage=None, dispatched=False,
                              latency_ms=int((time.monotonic() - start) * 1000))
                )
                raise ModelError("MODEL_TURN_TIMEOUT")
            try:
                result = self.adapter.bind(**options).invoke(wire)
            except LengthFinishReasonError as e:
                raw, usage, returned_model, finish_reason = _length_completion(e)
                meta = dict(status="failed", error_code="MODEL_TRUNCATED", usage=usage,
                            request_mode=mode, prompt_version=self.prompt_version,
                            returned_model=returned_model, finish_reason=finish_reason,
                            latency_ms=int((time.monotonic() - start) * 1000))
                self.ledger.finish(key, meta)
                self.trace.append(dict(call_key=key, **meta))
                if on_response is not None:
                    on_response(raw, {"call_key": key, "finish_reason": finish_reason,
                                      "returned_model": returned_model, "usage": usage,
                                      "provider_output_truncated": True})
                raise ModelError("MODEL_TRUNCATED", details={
                    "response_available": raw is not None,
                    "usage_available": usage is not None}) from None
            except ContentFilterFinishReasonError:
                self.ledger.finish(
                    key, dict(status="failed", error_code="MODEL_FILTERED", usage=None,
                              request_mode=mode, prompt_version=self.prompt_version,
                              latency_ms=int((time.monotonic() - start) * 1000)))
                raise ModelError("MODEL_FILTERED") from None
            except (APIStatusError, APITimeoutError, APIConnectionError) as e:
                status = getattr(e, "status_code", None)
                code = (
                    ("PROVIDER_HTTP_" + str(status)) if status else "PROVIDER_TIMEOUT_OR_CONNECTION"
                )
                self.ledger.finish(
                    key,
                    dict(
                        status="failed",
                        error_code=code,
                        usage=None,
                        latency_ms=int((time.monotonic() - start) * 1000),
                        prompt_version=self.prompt_version,
                        request_mode=mode,
                    ),
                )
                if retry_transient and status is not None and (status == 429 or status >= 500) and attempt == 0:
                    continue
                raise ModelError(code) from None
            except Exception:
                self.ledger.finish(
                    key, dict(status="failed", error_code="PROVIDER_PROTOCOL_ERROR", usage=None,
                              request_mode=mode, prompt_version=self.prompt_version)
                )
                raise ModelError("PROVIDER_PROTOCOL_ERROR") from None
            usage = result.usage_metadata
            truncated = result.response_metadata.get("finish_reason") == "length"
            meta = dict(
                status="failed" if truncated else "received",
                usage=dict(usage) if usage else None,
                latency_ms=int((time.monotonic() - start) * 1000),
                prompt_version=self.prompt_version,
                request_mode=mode,
                returned_model=result.response_metadata.get("model_name"),
                finish_reason=result.response_metadata.get("finish_reason"),
                tool_calls=[dict(id=x["id"], name=x["name"]) for x in result.tool_calls],
            )
            if truncated:
                meta["error_code"] = "MODEL_TRUNCATED"
            self.ledger.finish(key, meta)
            self.trace.append(dict(call_key=key, **meta))
            if on_response is not None:
                # Persist the returned content before any parser/finish-reason
                # rejection. This callback must fail closed and never retry.
                on_response(result.content, {"call_key": key,
                                             "finish_reason": meta["finish_reason"],
                                             "returned_model": meta["returned_model"],
                                             "usage": meta["usage"],
                                             "provider_output_truncated": truncated})
            if truncated:
                raise ModelError("MODEL_TRUNCATED", details={
                    "response_available": isinstance(result.content, str),
                    "usage_available": meta["usage"] is not None})
            if time.monotonic() - self.started >= 120:
                raise ModelError("MODEL_TURN_TIMEOUT")
            if result.invalid_tool_calls:
                raise ModelError("MODEL_TOOL_ARGUMENTS_INVALID")
            if not result.content and not result.tool_calls:
                raise ModelError("MODEL_EMPTY")
            return result

    def invoke_with_tools(self, messages, tool_schemas):
        return self.request(messages, tools=tool_schemas)

    def generate_structured(self, schema, messages):
        history = list(messages) + [
            SystemMessage(
                content="Return JSON only matching this schema: "
                + json.dumps(schema.model_json_schema())
            )
        ]
        for repair in range(2):
            answer = self.request(history, response_format={"type": "json_object"})
            try:
                if answer.tool_calls:
                    raise ValueError()
                return schema.model_validate_json(answer.content, strict=True)
            except (ValidationError, ValueError, TypeError):
                if repair:
                    raise ModelError("MODEL_SCHEMA_INVALID") from None
                history += [
                    answer,
                    HumanMessage(
                        content="Invalid JSON/schema. Repair once. Return only the required JSON object."
                    ),
                ]

    def generate_structured_once(self, schema, messages, *, on_response=None, schema_override=None):
        """Exactly one provider attempt: no HTTP retry and no schema-repair request."""
        history = list(messages) + [
            SystemMessage(content=structured_schema_instruction(
                schema_override or schema.model_json_schema()))
        ]
        request_args = {"retry_transient": False, "response_format": {"type": "json_object"}}
        if on_response is not None:
            request_args["on_response"] = on_response
        answer = self.request(history, **request_args)
        try:
            if answer.tool_calls:
                raise ValueError()
            payload = json.loads(answer.content)
        except (ValueError, TypeError) as exc:
            raise ModelError("MODEL_JSON_INVALID_NO_RETRY", details={
                "rule_id": "response.json_parse", "field_path": "$",
                "expected": "合法 JSON", "actual": type(exc).__name__,
                "response_offset": getattr(exc, "pos", None)}) from None
        try:
            return schema.model_validate(payload, strict=True)
        except ValidationError as exc:
            issue = exc.errors()[0]
            path = "$" + "".join(f"[{item}]" if isinstance(item, int) else f".{item}"
                                 for item in issue.get("loc", ()))
            raise ModelError("MODEL_SCHEMA_INVALID_NO_RETRY", details={
                "rule_id": "response.structure", "field_path": path[:160],
                "expected": (schema_override or schema.model_json_schema()).get("title", "冻结输出契约")[:120],
                "actual": str(issue.get("type", "invalid"))[:80]}) from None

    def run_tools(
        self, messages, schema, executor, context, *, allowed_tools, skill=None,
        tool_round_limit=3, structured_repair=True
    ):

        from app.tools.schemas import INPUTS

        permitted = set(allowed_tools)
        if skill is not None:
            permitted &= set(skill["allowed_tools"])
        if not permitted <= set(INPUTS):
            raise ModelError("TOOL_ALLOWLIST_INVALID")
        tools = [
            {
                "type": "function",
                "function": {
                    "name": n,
                    "description": "Authorized bounded business tool",
                    "parameters": INPUTS[n].model_json_schema(),
                },
            }
            for n in sorted(permitted)
        ]
        if type(tool_round_limit) is not int or not 1 <= tool_round_limit <= 3:
            raise ModelError("TOOL_ROUNDS_INVALID")
        history = list(messages)
        seen = set()
        records = []
        self.tool_records = records
        searches = 0
        rounds = 0

        def parse_without_repair(current):
            final = self.request(current, response_format={"type": "json_object"})
            try:
                if final.tool_calls:
                    raise ValueError()
                return schema.model_validate_json(final.content, strict=True), records
            except (ValidationError, ValueError, TypeError):
                raise ModelError("MODEL_SCHEMA_INVALID") from None

        while True:
            answer = self.invoke_with_tools(history, tools)
            if not answer.tool_calls:
                if structured_repair:
                    return self.generate_structured(schema, history + [answer]), records
                return parse_without_repair(history + [answer])
            history.append(answer)
            rounds += 1
            for call in answer.tool_calls:
                cid = call["id"]
                name = call["name"]
                if not cid or cid in seen:
                    raise ModelError("TOOL_CALL_ID_INVALID")
                seen.add(cid)
                searches += int(name == "search_manuals")
                if len(seen) > 6 or searches > 3:
                    raise ModelError("TOOL_TURN_BUDGET_EXHAUSTED")
                if name not in permitted:
                    raise ModelError("TOOL_FORBIDDEN")
                # Trusted context supplied by application, never constructed from model arguments.
                key = "model-" + hashlib.sha256((self.turn + ":" + cid).encode()).hexdigest()
                if time.monotonic() - self.started >= 120:
                    raise ModelError("MODEL_TURN_TIMEOUT")
                data = executor.execute(context, name, call["args"], key)
                records.append(
                    dict(
                        tool_call_id=cid,
                        name=name,
                        call_key=key,
                        ok=data["ok"],
                        provenance=data["provenance"],
                    )
                )
                history.append(
                    ToolMessage(content=json.dumps(data, ensure_ascii=False), tool_call_id=cid)
                )

            if rounds >= tool_round_limit:
                if structured_repair:
                    return self.generate_structured(schema, history), records
                return parse_without_repair(history)
