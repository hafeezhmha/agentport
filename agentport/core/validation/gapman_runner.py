from __future__ import annotations

import os
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Any

from agentport.models import ValidationResult
from agentport.core.scanner.yaml_extractor import load_yamlish
from agentport.core.validation.validation_parser import parse_external_validation


def validate_repo(path: Path, prefer_external: bool = True, validator_command: str | None = None) -> ValidationResult:
    if prefer_external:
        override = (validator_command or os.environ.get("AGENTPORT_VALIDATOR_COMMAND", "")).strip()
        if override:
            return _run_validator_override(path, override)
        for binary in ("gapman", "gitagent"):
            if shutil.which(binary):
                proc = subprocess.run(
                    [binary, "validate", "--compliance", str(path)],
                    text=True,
                    capture_output=True,
                    check=False,
                    timeout=120,
                )
                return parse_external_validation(proc.stdout, proc.stderr, proc.returncode, f"{binary}-validate")
    return internal_schema_validate(path)


def _run_validator_override(path: Path, command: str) -> ValidationResult:
    try:
        args = shlex.split(command)
    except ValueError as exc:
        return ValidationResult(
            mode="validator-override",
            ok=False,
            errors=[_error("invalid_validator_command", "AGENTPORT_VALIDATOR_COMMAND", str(exc))],
        )
    if not args:
        return ValidationResult(
            mode="validator-override",
            ok=False,
            errors=[_error("invalid_validator_command", "AGENTPORT_VALIDATOR_COMMAND", "Command is empty.")],
        )
    path_text = str(path)
    if any("{path}" in arg for arg in args):
        args = [arg.replace("{path}", path_text) for arg in args]
    else:
        args.append(path_text)
    try:
        proc = subprocess.run(
            args,
            text=True,
            capture_output=True,
            check=False,
            timeout=120,
        )
    except OSError as exc:
        return ValidationResult(
            mode="validator-override",
            ok=False,
            errors=[_error("validator_command_failed", args[0], str(exc))],
        )
    except subprocess.TimeoutExpired:
        return ValidationResult(
            mode="validator-override",
            ok=False,
            errors=[_error("validator_timeout", args[0], "Validator command timed out after 120 seconds.")],
        )
    return parse_external_validation(proc.stdout, proc.stderr, proc.returncode, "validator-override")


def structural_validate(path: Path) -> ValidationResult:
    return internal_schema_validate(path)


def internal_schema_validate(path: Path) -> ValidationResult:
    errors: list[str] = []
    warnings: list[str] = []
    required = [
        "agent.yaml",
        "SOUL.md",
        "RULES.md",
        "DUTIES.md",
        "conversion_map.json",
        "TODO_MANUAL_REVIEW.md",
        "migration_report.md",
        "validation_report.json",
        "framework_compatibility_report.md",
        "registry_readiness_report.md",
        "workflows/ported-identity-review.yaml",
    ]
    for rel in required:
        if not (path / rel).exists():
            errors.append(_error("missing_file", rel, "Required generated file is missing."))

    agent = _load_mapping(path / "agent.yaml", "agent.yaml", errors)
    if agent:
        _validate_agent_yaml(path, agent, errors, warnings)
        _validate_sod_policy(path, agent, errors)
    _validate_workflows(path, agent, errors)
    conversion = _load_mapping(path / "conversion_map.json", "conversion_map.json", errors)
    if conversion:
        _validate_conversion_map(conversion, errors)

    if not (path / "skills").exists():
        warnings.append(_warning("missing_optional_dir", "skills", "No skills directory generated."))
    if not (path / "tools").exists():
        warnings.append(_warning("missing_optional_dir", "tools", "No tools directory generated."))
    manual = path / "TODO_MANUAL_REVIEW.md"
    if manual.exists() and "Review these items" in manual.read_text(encoding="utf-8", errors="replace"):
        warnings.append(_warning("manual_review_open", "TODO_MANUAL_REVIEW.md", "Manual review file present; runtime equivalence is not claimed."))
    return ValidationResult(mode="internal-schema-fallback", ok=not errors, errors=errors, warnings=warnings)


def _validate_agent_yaml(path: Path, agent: dict[str, Any], errors: list[str], warnings: list[str]) -> None:
    required_fields = {
        "spec_version": str,
        "name": str,
        "version": str,
        "description": str,
        "model": dict,
        "tools": list,
        "skills": list,
        "tags": list,
    }
    for field, expected in required_fields.items():
        if field not in agent:
            errors.append(_error("missing_field", f"agent.yaml:{field}", "Required agent.yaml field is missing."))
            continue
        if not isinstance(agent[field], expected):
            errors.append(_error("invalid_type", f"agent.yaml:{field}", f"Expected {expected.__name__}."))
            continue
        if isinstance(agent[field], str) and not agent[field].strip():
            errors.append(_error("empty_required_field", f"agent.yaml:{field}", "Required string field is empty."))

    model = agent.get("model")
    if isinstance(model, dict):
        preferred = model.get("preferred")
        if not isinstance(preferred, str) or not preferred.strip():
            errors.append(_error("missing_field", "agent.yaml:model.preferred", "Model preferred value is required."))

    for tool in agent.get("tools", []) if isinstance(agent.get("tools"), list) else []:
        if not isinstance(tool, str) or not tool.strip():
            errors.append(_error("invalid_reference", "agent.yaml:tools", "Tool references must be non-empty strings."))
            continue
        rel = f"tools/{tool}.yaml"
        if not (path / rel).exists():
            errors.append(_error("broken_reference", rel, f"Tool referenced by agent.yaml does not exist: {tool}."))
        else:
            _validate_tool_yaml(path / rel, rel, errors)

    for skill in agent.get("skills", []) if isinstance(agent.get("skills"), list) else []:
        if not isinstance(skill, str) or not skill.strip():
            errors.append(_error("invalid_reference", "agent.yaml:skills", "Skill references must be non-empty strings."))
            continue
        rel = f"skills/{skill}/SKILL.md"
        if not (path / rel).exists():
            errors.append(_error("broken_reference", rel, f"Skill referenced by agent.yaml does not exist: {skill}."))

    knowledge = agent.get("knowledge")
    if isinstance(knowledge, dict):
        paths = knowledge.get("paths")
        if not isinstance(paths, list):
            errors.append(_error("invalid_type", "agent.yaml:knowledge.paths", "Expected list."))
        else:
            for rel in paths:
                if not isinstance(rel, str) or not rel.strip():
                    errors.append(_error("invalid_reference", "agent.yaml:knowledge.paths", "Knowledge paths must be non-empty strings."))
                elif not (path / rel).exists():
                    errors.append(_error("broken_reference", rel, "Knowledge file referenced by agent.yaml does not exist."))

    memory = agent.get("memory")
    if isinstance(memory, dict):
        memory_path = memory.get("path")
        if not isinstance(memory_path, str) or not memory_path.strip():
            errors.append(_error("missing_field", "agent.yaml:memory.path", "Memory path is required."))
        elif not (path / memory_path).exists():
            errors.append(_error("broken_reference", memory_path, "Memory file referenced by agent.yaml does not exist."))

    if isinstance(agent.get("tags"), list) and "ported-agent" not in agent["tags"]:
        warnings.append(_warning("missing_recommended_tag", "agent.yaml:tags", "Generated agent is missing the recommended 'ported-agent' tag."))


def _validate_sod_policy(path: Path, agent: dict[str, Any], errors: list[str]) -> None:
    compliance = agent.get("compliance")
    if compliance is None:
        return
    if not isinstance(compliance, dict):
        errors.append(_error("invalid_type", "agent.yaml:compliance", "Expected mapping/object."))
        return
    sod_policy = compliance.get("sod_policy")
    if not isinstance(sod_policy, str) or not sod_policy.strip():
        errors.append(_error("missing_field", "agent.yaml:compliance.sod_policy", "SOD policy path is required when compliance is declared."))
        return
    policy_path = path / sod_policy
    if not policy_path.exists():
        errors.append(_error("broken_reference", sod_policy, "SOD policy referenced by agent.yaml does not exist."))
        return
    text = policy_path.read_text(encoding="utf-8", errors="replace")
    lowered = text.lower()
    required_markers = {
        "schema writer": "schema writer boundary",
        "validation": "validation responsibility",
        "pr writer": "PR writer boundary",
        "bypass": "validation bypass prohibition",
    }
    for marker, label in required_markers.items():
        if marker not in lowered:
            errors.append(_error("missing_field", sod_policy, f"SOD policy is missing {label}."))


def _validate_workflows(path: Path, agent: dict[str, Any], errors: list[str]) -> None:
    workflows_dir = path / "workflows"
    if not workflows_dir.exists():
        return
    if not workflows_dir.is_dir():
        errors.append(_error("invalid_type", "workflows", "Expected workflows to be a directory."))
        return
    workflow_paths = sorted(workflows_dir.glob("*.yaml")) + sorted(workflows_dir.glob("*.yml"))
    if not workflow_paths:
        errors.append(_error("missing_file", "workflows/*.yaml", "At least one workflow YAML file is required."))
        return
    for workflow_path in workflow_paths:
        rel = workflow_path.relative_to(path).as_posix()
        workflow = _load_mapping(workflow_path, rel, errors)
        if workflow:
            _validate_workflow_yaml(path, rel, workflow, agent, errors)


def _validate_workflow_yaml(path: Path, rel: str, workflow: dict[str, Any], agent: dict[str, Any], errors: list[str]) -> None:
    required_fields = {
        "name": str,
        "description": str,
        "steps": list,
    }
    for field, expected in required_fields.items():
        if field not in workflow:
            errors.append(_error("missing_field", f"{rel}:{field}", "Required workflow field is missing."))
            continue
        if not isinstance(workflow[field], expected):
            errors.append(_error("invalid_type", f"{rel}:{field}", f"Expected {expected.__name__}."))
            continue
        if isinstance(workflow[field], str) and not workflow[field].strip():
            errors.append(_error("empty_required_field", f"{rel}:{field}", "Required string field is empty."))

    channel = workflow.get("channel")
    if channel is not None and (not isinstance(channel, str) or not channel.strip()):
        errors.append(_error("invalid_type", f"{rel}:channel", "Expected non-empty string."))

    steps = workflow.get("steps")
    if not isinstance(steps, list):
        return
    if not steps:
        errors.append(_error("empty_required_field", f"{rel}:steps", "Workflow must contain at least one step."))
        return

    agent_defs = agent.get("agents") if isinstance(agent.get("agents"), dict) else {}
    seen_agents: list[str] = []
    for index, step in enumerate(steps, start=1):
        step_location = f"{rel}:steps[{index}]"
        if not isinstance(step, dict):
            errors.append(_error("invalid_type", step_location, "Workflow step must be a mapping/object."))
            continue
        prompt = step.get("prompt")
        if prompt is not None and (not isinstance(prompt, str) or not prompt.strip()):
            errors.append(_error("invalid_type", f"{step_location}.prompt", "Expected non-empty string."))
        if not any(key in step for key in ("prompt", "agent", "skill", "tool")):
            errors.append(_error("missing_field", step_location, "Workflow step must declare a prompt, agent, skill, or tool."))
        agent_name = step.get("agent")
        if agent_name is not None:
            if not isinstance(agent_name, str) or not agent_name.strip():
                errors.append(_error("invalid_reference", f"{step_location}.agent", "Agent reference must be a non-empty string."))
            else:
                seen_agents.append(agent_name)
                _validate_workflow_agent_reference(path, agent_defs, agent_name, f"{step_location}.agent", errors)
        skill_name = step.get("skill")
        if skill_name is not None:
            _validate_workflow_named_reference(path, "skills", skill_name, f"{step_location}.skill", errors)
        tool_name = step.get("tool")
        if tool_name is not None:
            _validate_workflow_named_reference(path, "tools", tool_name, f"{step_location}.tool", errors)

    _validate_workflow_sod_order(rel, seen_agents, errors)


def _validate_workflow_agent_reference(path: Path, agent_defs: dict[str, Any], agent_name: str, location: str, errors: list[str]) -> None:
    if not agent_defs:
        return
    definition = agent_defs.get(agent_name)
    if definition is None:
        errors.append(_error("broken_reference", location, f"Workflow references unknown agent: {agent_name}."))
        return
    if not isinstance(definition, dict):
        errors.append(_error("invalid_type", f"agent.yaml:agents.{agent_name}", "Expected mapping/object."))
        return
    rel = definition.get("path")
    if not isinstance(rel, str) or not rel.strip():
        errors.append(_error("missing_field", f"agent.yaml:agents.{agent_name}.path", "Agent path is required."))
    elif not (path / rel).exists():
        errors.append(_error("broken_reference", rel, f"Agent path for workflow reference does not exist: {agent_name}."))


def _validate_workflow_named_reference(path: Path, kind: str, name: Any, location: str, errors: list[str]) -> None:
    if not isinstance(name, str) or not name.strip():
        errors.append(_error("invalid_reference", location, f"{kind[:-1].title()} reference must be a non-empty string."))
        return
    if kind == "skills":
        rel = f"skills/{name}/SKILL.md"
    else:
        rel = f"tools/{name}.yaml"
    if not (path / rel).exists():
        errors.append(_error("broken_reference", rel, f"Workflow referenced {kind[:-1]} does not exist: {name}."))


def _validate_workflow_sod_order(rel: str, seen_agents: list[str], errors: list[str]) -> None:
    positions = {agent_name: index for index, agent_name in enumerate(seen_agents)}
    schema_writer = positions.get("schema-writer")
    validation_auditor = positions.get("validation-auditor")
    pr_writer = positions.get("pr-writer")
    if schema_writer is not None and validation_auditor is not None and validation_auditor < schema_writer:
        errors.append(_error("invalid_sod_order", rel, "validation-auditor must run after schema-writer."))
    if pr_writer is not None and validation_auditor is not None and pr_writer < validation_auditor:
        errors.append(_error("invalid_sod_order", rel, "pr-writer must not run before validation-auditor."))


def _validate_tool_yaml(path: Path, rel: str, errors: list[str]) -> None:
    tool = _load_mapping(path, rel, errors)
    if not tool:
        return
    for field in ("name", "description", "version", "input_schema"):
        if field not in tool:
            errors.append(_error("missing_field", f"{rel}:{field}", "Required tool field is missing."))
    if "input_schema" in tool and not isinstance(tool["input_schema"], dict):
        errors.append(_error("invalid_type", f"{rel}:input_schema", "Expected mapping/object."))


def _validate_conversion_map(conversion: dict[str, Any], errors: list[str]) -> None:
    required_fields = {
        "source": str,
        "framework": dict,
        "generated_agent": str,
        "identity_fragments": list,
        "rules": list,
        "model_preferences": list,
        "tools": list,
        "manual_review": list,
        "boundary": str,
    }
    for field, expected in required_fields.items():
        if field not in conversion:
            errors.append(_error("missing_field", f"conversion_map.json:{field}", "Required conversion map field is missing."))
        elif not isinstance(conversion[field], expected):
            errors.append(_error("invalid_type", f"conversion_map.json:{field}", f"Expected {expected.__name__}."))
    boundary = conversion.get("boundary")
    if isinstance(boundary, str) and "identity layer" not in boundary.lower():
        errors.append(_error("invalid_boundary", "conversion_map.json:boundary", "Boundary must state that only the identity layer was ported."))


def _load_mapping(path: Path, rel: str, errors: list[str]) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = load_yamlish(path)
    except Exception as exc:
        errors.append(_error("malformed_document", rel, f"Could not parse document: {exc}"))
        return {}
    if not isinstance(data, dict):
        errors.append(_error("invalid_type", rel, "Expected top-level mapping/object."))
        return {}
    return data


def _error(code: str, location: str, message: str) -> str:
    return f"{code}: {location}: {message}"


def _warning(code: str, location: str, message: str) -> str:
    return f"{code}: {location}: {message}"
