from __future__ import annotations

import json
from pathlib import Path

from agentport.models import PortPlan, ValidationResult
from agentport.core.validation.readiness_score import assess_readiness


def write_reports(plan: PortPlan, generated_files: list[str], validation: ValidationResult | None, pr_ready: bool) -> list[str]:
    output = plan.output_path
    written: list[str] = []

    def write(rel: str, text: str) -> None:
        (output / rel).write_text(text.rstrip() + "\n", encoding="utf-8")
        written.append(rel)

    write("migration_report.md", _migration_report(plan, generated_files, validation))
    write("validation_report.json", _validation_report(validation))
    write("framework_compatibility_report.md", _compatibility_report(plan))
    write("registry_readiness_report.md", _readiness_report(plan, validation))
    if pr_ready:
        write("PULL_REQUEST.md", _pr_body(plan, generated_files, validation))
    return written


def _migration_report(plan: PortPlan, generated_files: list[str], validation: ValidationResult | None) -> str:
    status = "not run" if validation is None else ("passed" if validation.ok else "failed")
    return "\n".join(
        [
            "# Migration Report",
            "",
            "This migration ports the agent identity layer, not the full runtime implementation.",
            "",
            f"- Source: `{plan.source_path}`",
            f"- Output: `{plan.output_path}`",
            f"- Detected framework: `{plan.framework.framework}`",
            f"- Detection confidence: `{plan.framework.confidence:.2f}`",
            f"- Compatibility profile: `{plan.compatibility.profile if plan.compatibility else 'unknown'}`",
            f"- Profile confidence: `{plan.compatibility.confidence if plan.compatibility else plan.framework.confidence:.2f}`",
            f"- Validation: `{status}`",
            "",
            "## Detection Evidence",
            "",
            *[f"- {item}" for item in plan.framework.evidence],
            "",
            "## Version Hints",
            "",
            *([f"- {item}" for item in (plan.compatibility.version_hints if plan.compatibility else [])] or ["- No dependency version hints found."]),
            "",
            "## Deprecated / Legacy Patterns",
            "",
            *([f"- {item}" for item in (plan.compatibility.deprecated_patterns if plan.compatibility else [])] or ["- None detected."]),
            "",
            "## Unknown Patterns",
            "",
            *([f"- {item}" for item in (plan.compatibility.unknown_patterns if plan.compatibility else [])] or ["- None detected."]),
            "",
            "## Documentation Evidence",
            "",
            *(_docs_lines(plan)),
            "",
            "## Generated Files",
            "",
            *[f"- `{rel}`" for rel in generated_files],
            "",
            "## Manual Review",
            "",
            *([f"- {item}" for item in plan.extraction.manual_review] or ["- No scanner warnings."]),
        ]
    )


def _validation_report(validation: ValidationResult | None) -> str:
    if validation is None:
        return json.dumps({"mode": "not-run", "ok": None, "errors": [], "warnings": []}, indent=2)
    return json.dumps(validation.__dict__, indent=2)


def _readiness_report(plan: PortPlan, validation: ValidationResult | None) -> str:
    readiness = assess_readiness(plan, validation)
    hard_blockers = readiness.hard_blockers or ["None."]
    warnings = readiness.warnings or ["None."]
    return "\n".join(
        [
            "# Registry Readiness Report",
            "",
            f"Score: {readiness.score}/100",
            f"Safe to publish: {'yes' if readiness.safe_to_publish else 'no'}",
            "",
            "## Gates",
            "",
            *[f"- {name.replace('_', ' ').title()}: {status}" for name, status in readiness.gates.items()],
            "",
            "## Hard Blockers",
            "",
            *[f"- {item}" for item in hard_blockers],
            "",
            "## Warnings",
            "",
            *[f"- {item}" for item in warnings],
        ]
    )


def _compatibility_report(plan: PortPlan) -> str:
    framework = plan.framework.framework
    supported, manual = _compatibility_lists(framework)
    profile = plan.compatibility.profile if plan.compatibility else "unknown"
    profile_confidence = plan.compatibility.confidence if plan.compatibility else plan.framework.confidence
    version_hints = plan.compatibility.version_hints if plan.compatibility else []
    evidence = plan.compatibility.evidence if plan.compatibility else []
    deprecated = plan.compatibility.deprecated_patterns if plan.compatibility else []
    unknown = plan.compatibility.unknown_patterns if plan.compatibility else []
    docs_lines = _docs_lines(plan)
    return "\n".join(
        [
            "# Framework Compatibility Report",
            "",
            f"Framework: `{framework}`",
            f"Profile: `{profile}`",
            f"Profile confidence: `{profile_confidence:.2f}`",
            "",
            "This report describes what AgentPort extracted deterministically and what remains manual review.",
            "",
            "## Profile Evidence",
            "",
            *([f"- {item}" for item in evidence] or ["- No profile evidence captured."]),
            "",
            "## Version Hints",
            "",
            *([f"- {item}" for item in version_hints] or ["- No dependency version hints found."]),
            "",
            "## Deprecated / Legacy Patterns",
            "",
            *([f"- {item}" for item in deprecated] or ["- None detected."]),
            "",
            "## Unknown Patterns",
            "",
            *([f"- {item}" for item in unknown] or ["- None detected."]),
            "",
            "## Documentation Evidence",
            "",
            *docs_lines,
            "",
            "## Supported Deterministic Extraction",
            "",
            *[f"- {item}" for item in supported],
            "",
            "## Manual Review Boundary",
            "",
            *[f"- {item}" for item in manual],
            "",
            "## Current Migration Coverage",
            "",
            f"- Identity fragments: {len(plan.extraction.identity_fragments)}",
            f"- Rules: {len(plan.extraction.rules)}",
            f"- Tools: {len(plan.extraction.tools)}",
            f"- Manual review items: {len(plan.extraction.manual_review)}",
        ]
    )


def _compatibility_lists(framework: str) -> tuple[list[str], list[str]]:
    if framework == "crewai":
        return (
            [
                "agents.yaml role/goal/backstory",
                "tasks.yaml description/expected_output/string guardrail",
                "Agent(...)/Task(...) literal identity fields",
                "@agent/@task/@crew decorator markers",
                "static tool references",
            ],
            [
                "Crew/process orchestration",
                "hierarchical manager behavior",
                "function guardrails",
                "output_json/output_pydantic runtime validation",
                "async_execution/context wiring",
            ],
        )
    if framework == "langchain":
        return (
            [
                "legacy AgentExecutor/initialize_agent markers",
                "modern create_*_agent factory markers",
                "PromptTemplate and ChatPromptTemplate static prompt text",
                "@tool decorated function metadata",
                "prompt/instruction constants",
                "static tool references",
            ],
            [
                "agent execution loop",
                "tool function implementation",
                "retriever/vectorstore behavior",
                "callback/runtime configuration",
            ],
        )
    if framework == "langgraph":
        return (
            [
                "StateGraph import detection",
                "prompt/instruction constants",
                "add_node/add_edge/add_conditional_edges topology evidence",
                "model constants",
            ],
            [
                "state schema behavior",
                "node execution functions",
                "conditional routing semantics",
                "Command/Send runtime behavior",
                "checkpointing/store/memory",
            ],
        )
    if framework == "claude-cursor":
        return (
            [
                "CLAUDE.md",
                ".claude/CLAUDE.md",
                "CLAUDE.local.md",
                "CLAUDE.md @imports",
                ".cursorrules",
                ".cursor/rules/*.mdc with frontmatter",
            ],
            [
                "Claude local/user/global memories outside source repo",
                "Cursor rule activation semantics",
                "editor-specific runtime enforcement",
            ],
        )
    return (
        ["generic prompt, Markdown, YAML, JSON, and Python literal extraction"],
        ["framework-specific runtime behavior"],
    )


def _pr_body(plan: PortPlan, generated_files: list[str], validation: ValidationResult | None) -> str:
    validation_line = "not run" if validation is None else ("passed" if validation.ok else "failed")
    return "\n".join(
        [
            "# Port Agent Identity To GitAgent",
            "",
            "## Summary",
            "",
            f"- Ported `{plan.framework.framework}` identity artifacts from `{plan.source_path}`.",
            f"- Compatibility profile: `{plan.compatibility.profile if plan.compatibility else 'unknown'}`.",
            f"- Docs verification recommended: `{plan.docs_evidence.verification_recommended if plan.docs_evidence else True}`.",
            "- Generated GitAgent/Open GAP identity repo files.",
            "- Runtime framework implementation is flagged for manual review where detected.",
            "",
            "## Validation",
            "",
            f"- Result: {validation_line}",
            "",
            "## Files",
            "",
            *[f"- `{rel}`" for rel in generated_files],
            "",
            "## Manual Review Checklist",
            "",
            "- [ ] Review TODO_MANUAL_REVIEW.md",
            "- [ ] Confirm no secrets were copied",
            "- [ ] Confirm runtime-specific code was not claimed as ported",
            "- [ ] Run GitAgent validation in the target environment",
        ]
    )


def _docs_lines(plan: PortPlan) -> list[str]:
    docs = plan.docs_evidence
    if not docs:
        return ["- No docs evidence available."]
    lines = [f"- Docs framework key: `{docs.framework}`", f"- Verification recommended: `{docs.verification_recommended}`"]
    if docs.reasons:
        lines.append("- Reasons:")
        lines.extend(f"  - {reason}" for reason in docs.reasons)
    if docs.links:
        lines.append("- Links:")
        lines.extend(f"  - {link['label']}: {link['url']}" for link in docs.links)
    else:
        lines.append("- Links: none")
    return lines
