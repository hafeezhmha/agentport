from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from agentport.models import PortPlan, ValidationResult
from agentport.core.learning.failure_analyzer import summarize_failure


def update_memory(agentport_root: Path, plan: PortPlan, validation: ValidationResult) -> Path | None:
    if validation.ok and not validation.warnings:
        return None
    memory = agentport_root / "agents" / "agentport" / "memory" / "migration-patterns.md"
    memory.parent.mkdir(parents=True, exist_ok=True)
    existing = memory.read_text(encoding="utf-8") if memory.exists() else "# Migration Patterns\n"
    entry = "\n".join(
        [
            "",
            f"## {datetime.now(timezone.utc).date()} {plan.framework.framework}",
            "",
            f"- Source: `{plan.source_path}`",
            f"- Validation mode: `{validation.mode}`",
            f"- Failure summary: {summarize_failure(validation)}",
            f"- Warnings: {len(validation.warnings)}",
        ]
    )
    memory.write_text(existing.rstrip() + entry + "\n", encoding="utf-8")
    return memory
