"""Versioned application-trusted protocol schema for the bounded DKVB demo."""

from typing import Literal

from pydantic import Field, model_validator

from app.domain.schemas import InputModel, PersistedText


class ProtocolField(InputModel):
    name: Literal["leak_object_id", "leak_location", "evidence_kind"]
    label: PersistedText = Field(min_length=1, max_length=100)
    kind: Literal["text", "select"]
    required: bool = True
    options: list[PersistedText] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def bounded(self):
        if self.kind == "select" and not self.options:
            raise ValueError("Select protocol field requires options")
        if self.kind == "text" and self.options:
            raise ValueError("Text protocol field cannot publish options")
        return self


class ProtocolInput(InputModel):
    kind: Literal["choice"]
    observation_values: list[PersistedText] = Field(min_length=1, max_length=8)
    fields_by_value: dict[PersistedText, list[ProtocolField]] = Field(default_factory=dict)


class ProtocolCheck(InputModel):
    check_id: PersistedText = Field(min_length=1, max_length=64)
    current_stage: PersistedText = Field(min_length=1, max_length=64)
    input_schema: ProtocolInput
    evidence_refs: list[PersistedText] = Field(min_length=1, max_length=12)
    completion_conditions: list[PersistedText] = Field(min_length=1, max_length=12)


class ProtocolTransition(InputModel):
    transition_id: PersistedText = Field(min_length=1, max_length=100)
    current_check_id: PersistedText = Field(min_length=1, max_length=64)
    prerequisites: list[PersistedText] = Field(default_factory=list, max_length=12)
    observation_value: PersistedText = Field(min_length=1, max_length=100)
    next_check_id: PersistedText | None = Field(default=None, max_length=64)
    decision: Literal["next_check", "need_input", "handoff", "conclude"]
    need_input_fields: list[PersistedText] = Field(default_factory=list, max_length=12)
    handoff_reason: PersistedText | None = Field(default=None, max_length=500)


class TrustedProtocol(InputModel):
    protocol_id: PersistedText = Field(min_length=1, max_length=100)
    version: PersistedText = Field(min_length=1, max_length=32)
    synthetic: Literal[True]
    formal_usable: Literal[False]
    applicable_vehicle_profile: dict[PersistedText, PersistedText | int]
    checks: list[ProtocolCheck] = Field(min_length=1, max_length=16)
    transitions: list[ProtocolTransition] = Field(min_length=1, max_length=24)

    @model_validator(mode="after")
    def identities(self):
        checks = {x.check_id for x in self.checks}
        if len(checks) != len(self.checks):
            raise ValueError("Duplicate check id")
        if len({x.transition_id for x in self.transitions}) != len(self.transitions):
            raise ValueError("Duplicate transition id")
        if any(x.current_check_id not in checks or (x.next_check_id and x.next_check_id not in checks)
               for x in self.transitions):
            raise ValueError("Transition references unknown check")
        return self


PROFILE = {
    "model": "虚拟探岳 DKVB 演示台架",
    "year": 2020,
    "engine_family": "EA888 Gen3B DEMO",
    "engine_code": "DKVB-DEMO",
}

DKVB_DEMO_PROTOCOL = TrustedProtocol(
    protocol_id="dkvb-p0299-guided-demo",
    version="1.0.0",
    synthetic=True,
    formal_usable=False,
    applicable_vehicle_profile=PROFILE,
    checks=[
        ProtocolCheck(check_id="CHK-05", current_stage="localized_leak_check",
            input_schema=ProtocolInput(kind="choice", observation_values=["localized", "not_found", "inconclusive"],
                fields_by_value={"localized": [
                    ProtocolField(name="leak_object_id", label="发现泄漏的对象", kind="text"),
                    ProtocolField(name="leak_location", label="泄漏位置", kind="text"),
                    ProtocolField(name="evidence_kind", label="定位依据", kind="select", options=["visual", "touch", "leak_spray", "ultrasound"]),
                ]}),
            evidence_refs=["S02-P5", "S02-P6"], completion_conditions=["one_current_observation"]),
        ProtocolCheck(check_id="CHK-05-SUPPLEMENT", current_stage="localized_leak_evidence",
            input_schema=ProtocolInput(kind="choice", observation_values=["localized", "inconclusive"],
                fields_by_value={"localized": [
                    ProtocolField(name="leak_object_id", label="发现泄漏的对象", kind="text"),
                    ProtocolField(name="leak_location", label="泄漏位置", kind="text"),
                    ProtocolField(name="evidence_kind", label="定位依据", kind="select", options=["visual", "touch", "leak_spray", "ultrasound"]),
                ]}),
            evidence_refs=["S02-P5", "S02-P6"], completion_conditions=["locator_fields_complete"]),
        ProtocolCheck(check_id="CHK-06", current_stage="demo_pipe_followup",
            input_schema=ProtocolInput(kind="choice", observation_values=["intact", "damaged"]),
            evidence_refs=["S02-P2", "CHK-06"], completion_conditions=["one_current_observation"]),
        ProtocolCheck(check_id="CHK-07", current_stage="connection_recheck",
            input_schema=ProtocolInput(kind="choice", observation_values=["localized", "not_found", "inconclusive"]),
            evidence_refs=["S02-P5", "CHK-07"], completion_conditions=["one_current_observation"]),
        ProtocolCheck(check_id="CHK-08", current_stage="actuator_linkage_check",
            input_schema=ProtocolInput(kind="choice", observation_values=["loose", "secure"]),
            evidence_refs=["S03-P2", "S03-P8"], completion_conditions=["one_current_observation"]),
    ],
    transitions=[
        ProtocolTransition(transition_id="CHK05_LOCALIZED_TO_CHK06", current_check_id="CHK-05",
            prerequisites=["current_observation", "locator_fields_complete", "source_valid", "scope_matched"],
            observation_value="localized", next_check_id="CHK-06", decision="next_check"),
        ProtocolTransition(transition_id="CHK05_NOT_FOUND_TO_CHK08", current_check_id="CHK-05",
            prerequisites=["current_observation", "source_valid", "scope_matched"],
            observation_value="not_found", next_check_id="CHK-08", decision="next_check"),
        ProtocolTransition(transition_id="CHK05_INCONCLUSIVE_NEEDS_INPUT", current_check_id="CHK-05",
            prerequisites=["current_observation", "source_valid", "scope_matched"],
            observation_value="inconclusive", next_check_id="CHK-05-SUPPLEMENT", decision="need_input",
            need_input_fields=["leak_object_id", "leak_location", "evidence_kind"],
            handoff_reason="现有定位观察不足，请补充泄漏对象、位置和定位依据。"),
        ProtocolTransition(transition_id="CHK05_SUPPLEMENT_LOCALIZED_TO_CHK06", current_check_id="CHK-05-SUPPLEMENT",
            prerequisites=["current_observation", "locator_fields_complete", "source_valid", "scope_matched"],
            observation_value="localized", next_check_id="CHK-06", decision="next_check"),
        ProtocolTransition(transition_id="CHK05_SUPPLEMENT_STILL_NEEDS_INPUT", current_check_id="CHK-05-SUPPLEMENT",
            prerequisites=["current_observation", "source_valid", "scope_matched"],
            observation_value="inconclusive", next_check_id="CHK-05-SUPPLEMENT", decision="need_input",
            need_input_fields=["leak_object_id", "leak_location", "evidence_kind"],
            handoff_reason="仍缺少可核验的泄漏定位观察。"),
        ProtocolTransition(transition_id="CHK06_COMPLETED_TO_CHK07", current_check_id="CHK-06",
            prerequisites=["current_observation", "source_valid", "scope_matched"],
            observation_value="intact", next_check_id="CHK-07", decision="next_check"),
        ProtocolTransition(transition_id="CHK06_DAMAGED_TO_CHK07", current_check_id="CHK-06",
            prerequisites=["current_observation", "source_valid", "scope_matched"],
            observation_value="damaged", next_check_id="CHK-07", decision="next_check"),
    ],
)

REGISTRY = {(DKVB_DEMO_PROTOCOL.protocol_id, DKVB_DEMO_PROTOCOL.version): DKVB_DEMO_PROTOCOL}



def build_demo_candidates(cite):
    """Assemble bounded candidates from already bound full-paragraph evidence."""
    def step(component, title, purpose, location, action, choices):
        return {
            "type": "propose_step", "component_key": component, "title": title,
            "purpose": cite(purpose), "location": cite(location),
            "prerequisites": [cite("演示操作只填写已给出的模拟结果，不操作真实气源。")],
            "actions": [{**cite(action), "operation": "inspect"}],
            "input": {"kind": "choice", "choices": [cite(x) for x in choices]},
            "interpretation": [],
        }
    return {
        "CHK-05": step("增压空气系统", "检查增压空气系统是否存在可定位漏点（DEMO）",
            "增压空气系统局部泄漏检查用于确认有无可定位漏点，而不是用整个系统压降推断泄漏。",
            "增压空气系统位置见 S02-P5/P6 装配图。",
            "检查 增压空气系统 的局部泄漏。",
            ["增压空气系统已定位局部泄漏。", "增压空气系统未发现局部泄漏。", "增压空气系统局部泄漏结果无法确定。"]),
        "CHK-05-SUPPLEMENT": step("增压空气系统定位证据", "补充局部泄漏定位观察（DEMO）",
            "增压空气系统定位证据用于补充泄漏对象、位置和定位方法，不用于推导系统正常。",
            "增压空气系统定位证据位置见 S02-P5/P6 装配图。",
            "检查 增压空气系统定位证据 的局部泄漏。",
            ["增压空气系统定位证据已定位局部泄漏。", "增压空气系统定位证据局部泄漏结果无法确定。"]),
        "CHK-06": step("增压空气系统", "记录处理后管路外观（DEMO）",
            "增压空气系统处理后只记录当前外观观察，不代表故障已经排除。",
            "增压空气系统位于演示台架前部。",
            "检查 增压空气系统 外观。",
            ["增压空气系统外观完好。", "增压空气系统外观损坏。"]),
        "CHK-07": step("增压空气系统", "复查连接部位状态（DEMO）",
            "增压空气系统连接部位复查只记录当前插头观察，不代表故障已经排除。",
            "增压空气系统位置见 S02-P5/P6 装配图。",
            "检查 增压空气系统 插头。",
            ["增压空气系统插头松动。", "增压空气系统插头牢固。"]),
        "CHK-08": step("增压空气系统", "观察 V465 调节机构及连接机构（DEMO）",
            "增压空气系统中的 V465 调节机构检查只记录连接机构观察，不据此直接判定涡轮增压器损坏。",
            "增压空气系统位置见 S03-P2/P8 装配图。",
            "检查 增压空气系统 外壳。",
            ["增压空气系统外壳完整。", "增压空气系统外壳破损。"]),
    }


# R1 uses the immutable v2 package.  The v1 definitions above remain readable
# solely so historical source snapshots are not deleted from this uncommitted repository.
from app.agents.trusted_protocol_v2 import (  # noqa: E402,F401
    APPROVED_PROTOCOLS,
    DKVB_DEMO_PROTOCOL,
    PROFILE,
    ProtocolField,
    ProtocolOption,
    TrustedProtocol,
    build_demo_candidates,
    required_demo_material_texts,
    validate_protocol_package,
)
from app.agents.trusted_protocol_v2 import REGISTRY  # noqa: E402,F401
