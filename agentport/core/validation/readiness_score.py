from __future__ import annotations

from dataclasses import dataclass, field

from agentport.models import PortPlan, ValidationResult


@dataclass
class ReadinessAssessment:
    score: int
    safe_to_publish: bool
    hard_blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    gates: dict[str, str] = field(default_factory=dict)


def readiness_score(plan: PortPlan, validation: ValidationResult | None) -> int:
    return assess_readiness(plan, validation).score


def assess_readiness(plan: PortPlan, validation: ValidationResult | None) -> ReadinessAssessment:
    score = 50
    hard_blockers: list[str] = []
    warnings: list[str] = []

    score += 15 if plan.extraction.identity_fragments else 0
    score += 10 if plan.extraction.rules else 0
    score += 10 if plan.extraction.tools else 0
    if validation is None:
        hard_blockers.append("Validation has not been run.")
        score -= 25
    elif validation.ok:
        score += 15
    else:
        hard_blockers.extend(validation.errors or ["Validation failed."])
        score -= 35

    if plan.framework.confidence < 0.65:
        warnings.append(f"Framework detection confidence is low ({plan.framework.confidence:.2f}).")
        score -= 5

    if plan.compatibility and plan.compatibility.confidence < 0.70:
        warnings.append(f"Compatibility profile confidence is low ({plan.compatibility.confidence:.2f}).")
        score -= 5

    score -= min(20, len(plan.extraction.manual_review) * 3)
    if plan.extraction.manual_review:
        warnings.append(f"{len(plan.extraction.manual_review)} manual review item(s) remain open.")

    if not plan.extraction.identity_fragments and not plan.extraction.rules:
        hard_blockers.append("No portable identity or rule fragments were extracted.")
        score -= 20

    safe_to_publish = not hard_blockers and bool(validation and validation.ok) and score >= 75
    gates = {
        "schema_validation": "pass" if validation and validation.ok else "fail",
        "hard_blockers": "pass" if not hard_blockers else "fail",
        "manual_review": "warning" if plan.extraction.manual_review else "pass",
        "runtime_equivalence": "not claimed",
    }
    return ReadinessAssessment(
        score=max(0, min(100, score)),
        safe_to_publish=safe_to_publish,
        hard_blockers=hard_blockers,
        warnings=warnings,
        gates=gates,
    )
