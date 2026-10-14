"""Public write boundary for archived, pre-template cases.

Historical reads and service-level replay tools remain available. Product
requests may only create and change cases on the template-match workflow.
"""

from uuid import UUID

from app.domain.policies import DomainError


def require_template_case(request, actor, case_id: UUID) -> None:
    case = request.app.state.case_service.get(actor, case_id)
    if (case.get("intake_snapshot") or {}).get("workbench_flow") != "template-match-v1":
        raise DomainError(
            "LEGACY_CASE_READ_ONLY",
            "旧版病例已归档，只能查看历史内容；请从新工作台创建模板病例。",
            409,
        )


def reject_legacy_creation(body) -> None:
    if body.workbench_flow != "template-match-v1":
        raise DomainError(
            "LEGACY_CASE_READ_ONLY",
            "旧版病例入口已停用；请使用车辆信息匹配模板创建病例。",
            409,
        )


def retire_legacy_case_route(request, actor, case_id: UUID) -> None:
    """Keep ownership checks, then reject a superseded workflow for any case."""
    require_template_case(request, actor, case_id)
    raise DomainError(
        "LEGACY_FLOW_RETIRED",
        "此操作属于已停用的诊断流程，请使用当前模板工作台。",
        410,
    )
