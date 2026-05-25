from __future__ import annotations

import re
import tomllib
from typing import Any

from agentport.models import CompatibilityProfile, FrameworkDetection, SourceFile
from agentport.core.scanner.file_tree import read_text

DEPENDENCY_FILES = {
    "requirements.txt",
    "pyproject.toml",
    "poetry.lock",
    "uv.lock",
    "Pipfile",
    "Pipfile.lock",
    "package.json",
}


def profile_compatibility(files: list[SourceFile], detection: FrameworkDetection) -> CompatibilityProfile:
    evidence: list[str] = []
    deprecated: list[str] = []
    unknown: list[str] = []
    versions = _version_hints(files)
    names = {file.rel_path.lower() for file in files}
    python_text = "\n".join(read_text(file.path, limit=50_000) for file in files if file.suffix == ".py")
    lowered = python_text.lower()

    framework = detection.framework
    profile = f"{framework}-generic"
    confidence = detection.confidence

    if framework == "crewai":
        has_yaml = any(name.endswith(("agents.yaml", "tasks.yaml")) for name in names)
        has_crewai_project = "from crewai.project import" in lowered or "@crewbase" in lowered or "@agent" in lowered
        has_direct_code = "agent(" in lowered and "task(" in lowered and "crew(" in lowered
        if has_yaml and has_crewai_project:
            profile = "crewai-modern-yaml"
            confidence = max(confidence, 0.90)
            evidence.append("CrewAI YAML config with crewai.project decorators.")
        elif has_direct_code and not has_yaml:
            profile = "crewai-legacy-code-only"
            confidence = max(confidence, 0.82)
            evidence.append("CrewAI direct code-only Agent/Task/Crew definitions without YAML config.")
            deprecated.append("Code-only CrewAI definitions are common in older repos; YAML config is the modern recommended project shape.")
        elif has_yaml:
            profile = "crewai-yaml-with-custom-loader"
            confidence = max(confidence, 0.78)
            evidence.append("CrewAI YAML files found without standard crewai.project decorators.")
            unknown.append("Could not confirm how YAML files are loaded by code.")
        else:
            profile = "crewai-unclassified"
            unknown.append("CrewAI markers found, but no standard YAML/decorator/direct-code profile matched.")

    elif framework in {"langgraph", "langchain"}:
        has_start_end = "from langgraph.graph import" in lowered and ("start" in lowered and "end" in lowered)
        has_stategraph = "stategraph" in lowered
        has_compile = ".compile(" in lowered
        has_langchain_agentexecutor = "agentexecutor" in lowered or "initialize_agent" in lowered
        has_langchain_react = any(marker in lowered for marker in ("create_react_agent", "create_structured_chat_agent", "create_openai_tools_agent"))
        has_langchain_zeroshot = "zeroshotagent" in lowered
        has_langchain_tool_schema = "args_schema" in lowered and ("structuredtool" in lowered or "tool(" in lowered)
        if has_langchain_react and not has_stategraph:
            profile = "langchain-modern-agent-factory"
            confidence = max(confidence, 0.82)
            evidence.append("LangChain agent factory markers found.")
            framework = "langchain"
        elif has_langchain_tool_schema and not has_stategraph:
            profile = "langchain-tool-args-schema"
            confidence = max(confidence, 0.80)
            evidence.append("LangChain Tool/StructuredTool args_schema markers found.")
            framework = "langchain"
        elif has_langchain_zeroshot and not has_stategraph:
            profile = "langchain-zeroshot-legacy"
            confidence = max(confidence, 0.82)
            evidence.append("LangChain ZeroShotAgent markers found.")
            deprecated.append("ZeroShotAgent is a legacy LangChain agent style.")
            framework = "langchain"
        elif has_langchain_agentexecutor and not has_stategraph:
            profile = "langchain-agentexecutor"
            confidence = max(confidence, 0.82)
            evidence.append("LangChain AgentExecutor/initialize_agent markers found.")
            deprecated.append("initialize_agent and classic AgentExecutor patterns are legacy LangChain agent styles.")
            framework = "langchain"
        elif has_stategraph and has_start_end:
            profile = "langgraph-v1"
            confidence = max(confidence, 0.84)
            evidence.append("LangGraph StateGraph with START/END markers.")
        elif has_stategraph:
            profile = "langgraph-v0-or-legacy"
            confidence = max(confidence, 0.72)
            evidence.append("LangGraph StateGraph found without modern START/END markers.")
            deprecated.append("Graph uses legacy or incomplete LangGraph topology markers.")
        else:
            profile = "langchain-unclassified" if framework == "langchain" else "langgraph-unclassified"
            unknown.append("LangGraph/LangChain markers found, but no known graph or agent profile matched.")

    elif framework == "claude-cursor":
        has_mdc = any(name.startswith(".cursor/rules/") and name.endswith(".mdc") for name in names)
        has_cursorrules = ".cursorrules" in names
        has_claude = "claude.md" in names or ".claude/claude.md" in names or "claude.local.md" in names
        if has_mdc and has_cursorrules:
            profile = "cursor-mdc-plus-legacy-cursorrules"
            confidence = max(confidence, 0.92)
            evidence.append("Cursor MDC rules and legacy .cursorrules are both present.")
            deprecated.append(".cursorrules is legacy compared with .cursor/rules/*.mdc.")
        elif has_mdc:
            profile = "cursor-mdc-rules"
            confidence = max(confidence, 0.88)
            evidence.append("Cursor MDC rules found.")
        elif has_cursorrules:
            profile = "cursor-legacy-cursorrules"
            confidence = max(confidence, 0.82)
            evidence.append("Legacy .cursorrules file found.")
            deprecated.append(".cursorrules is a legacy Cursor rules format.")
        elif has_claude:
            profile = "claude-project-memory"
            confidence = max(confidence, 0.82)
            evidence.append("Claude project memory files found.")
        else:
            profile = "claude-cursor-unclassified"
            unknown.append("Instruction markers found, but no known Claude/Cursor profile matched.")

    elif framework == "openai-agents-sdk":
        profile = "openai-agents-sdk-unimplemented"
        evidence.append("OpenAI Agents SDK markers found.")
        unknown.append("OpenAI Agents SDK extraction is stretch support and not implemented yet.")
    elif framework == "google-adk":
        profile = "google-adk-unimplemented"
        evidence.append("Google ADK markers found.")
        unknown.append("Google ADK extraction is stretch support and not implemented yet.")
    else:
        profile = "generic-static-identity"
        evidence.append("No precise framework profile matched; using generic static extraction.")

    return CompatibilityProfile(
        framework=framework,
        profile=profile,
        confidence=min(0.99, confidence),
        evidence=evidence or detection.evidence,
        version_hints=versions,
        deprecated_patterns=deprecated,
        unknown_patterns=unknown,
    )


def _version_hints(files: list[SourceFile]) -> list[str]:
    hints: list[str] = []
    for file in files:
        if file.rel_path not in DEPENDENCY_FILES:
            continue
        text = read_text(file.path, limit=100_000)
        if file.rel_path == "pyproject.toml":
            hints.extend(_pyproject_version_hints(text, file.rel_path))
        if file.rel_path in {"poetry.lock", "uv.lock"}:
            hints.extend(_lockfile_version_hints(text, file.rel_path))
        for package in ("crewai", "langgraph", "langchain", "openai-agents", "google-adk"):
            for match in re.finditer(rf"(?im)(?:^|[\"'])({re.escape(package)})(?:\[.*?\])?\s*([=<>!~]=?|==)?\s*([0-9][A-Za-z0-9_.!+-]*)?", text):
                name, op, version = match.groups()
                if version:
                    hints.append(f"{name}{op or ''}{version} from {file.rel_path}")
                else:
                    hints.append(f"{name} from {file.rel_path}")
                break
    return sorted(set(hints))


def _lockfile_version_hints(text: str, rel_path: str) -> list[str]:
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return []
    packages = data.get("package")
    if not isinstance(packages, list):
        return []
    hints: list[str] = []
    tracked = {"crewai", "langgraph", "langchain", "openai-agents", "google-adk"}
    for package in packages:
        if not isinstance(package, dict):
            continue
        name = package.get("name")
        version = package.get("version")
        if not isinstance(name, str):
            continue
        normalized = name.lower().replace("_", "-")
        if normalized not in tracked:
            continue
        if isinstance(version, str) and version:
            hints.append(f"{normalized}=={version} from {rel_path}")
        else:
            hints.append(f"{normalized} from {rel_path}")
    return hints


def _pyproject_version_hints(text: str, rel_path: str) -> list[str]:
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return []

    entries: list[str] = []
    project = data.get("project")
    if isinstance(project, dict):
        entries.extend(_string_list(project.get("dependencies")))
        optional = project.get("optional-dependencies")
        if isinstance(optional, dict):
            for value in optional.values():
                entries.extend(_string_list(value))

    dependency_groups = data.get("dependency-groups")
    if isinstance(dependency_groups, dict):
        for value in dependency_groups.values():
            entries.extend(_string_list(value))

    poetry = data.get("tool", {}).get("poetry") if isinstance(data.get("tool"), dict) else None
    if isinstance(poetry, dict):
        entries.extend(_poetry_dependency_entries(poetry.get("dependencies")))
        group = poetry.get("group")
        if isinstance(group, dict):
            for group_data in group.values():
                if isinstance(group_data, dict):
                    entries.extend(_poetry_dependency_entries(group_data.get("dependencies")))

    hints = [_dependency_hint(entry, rel_path) for entry in entries]
    return [hint for hint in hints if hint]


def _string_list(value: Any) -> list[str]:
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def _poetry_dependency_entries(value: Any) -> list[str]:
    if not isinstance(value, dict):
        return []
    entries: list[str] = []
    for name, spec in value.items():
        if str(name).lower() == "python":
            continue
        if isinstance(spec, str):
            entries.append(f"{name}{spec if spec.startswith(('=', '<', '>', '!', '~', '^')) else ' ' + spec}")
        elif isinstance(spec, dict):
            version = spec.get("version")
            if isinstance(version, str):
                entries.append(f"{name}{version if version.startswith(('=', '<', '>', '!', '~', '^')) else ' ' + version}")
            else:
                entries.append(str(name))
    return entries


def _dependency_hint(entry: str, rel_path: str) -> str:
    packages = ("crewai", "langgraph", "langchain", "openai-agents", "google-adk")
    match = re.match(r"^\s*([A-Za-z0-9_.-]+)(?:\[.*?\])?\s*([^;,\s]+)?", entry)
    if not match:
        return ""
    name, spec = match.groups()
    normalized = name.lower().replace("_", "-")
    if normalized not in packages:
        return ""
    if spec and spec not in {"*", ""}:
        return f"{normalized}{spec} from {rel_path}"
    return f"{normalized} from {rel_path}"
