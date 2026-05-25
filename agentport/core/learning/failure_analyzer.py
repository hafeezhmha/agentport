from __future__ import annotations

from agentport.models import ValidationResult


def summarize_failure(validation: ValidationResult) -> str:
    if validation.ok:
        return "No validation failure."
    return "; ".join(validation.errors[:5]) or "Validation failed without detailed errors."
