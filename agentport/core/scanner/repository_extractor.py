from __future__ import annotations

import re
from pathlib import Path

from agentport.models import ExtractionResult, IdentityFragment, SourceFile, ToolSchema
from agentport.core.scanner.prompt_extractor import extract_prompt_file
from agentport.core.scanner.python_ast_extractor import extract_python_identity
from agentport.core.scanner.tool_schema_extractor import extract_yaml_tool
from agentport.core.scanner.yaml_extractor import load_yamlish, yaml_line_index


def extract_repository(files: list[SourceFile]) -> ExtractionResult:
    result = ExtractionResult()
    by_rel = {file.rel_path: file for file in files}
    for file in files:
        path = file.path
        if file.suffix == ".py":
            fragments, models, tools, manual, crewai_runtime, graph_topology, langchain_runtime, hierarchy = extract_python_identity(path, file.rel_path)
            result.identity_fragments.extend(fragments)
            result.model_preferences.extend(models)
            result.tools.extend(tools)
            result.manual_review.extend(manual)
            result.hierarchy.extend(hierarchy)
            _merge_graph_topology(result.crewai_runtime, crewai_runtime)
            _merge_graph_topology(result.graph_topology, graph_topology)
            _merge_graph_topology(result.langchain_runtime, langchain_runtime)
        if file.suffix in {".md", ".mdc", ""}:
            fragments, rules = extract_prompt_file(path, file.rel_path)
            result.identity_fragments.extend(fragments)
            result.rules.extend(rules)
            _extract_claude_imports(file, by_rel, result)
        if file.suffix in {".yaml", ".yml", ".json"}:
            tool = extract_yaml_tool(path, file.rel_path)
            if tool:
                result.tools.append(tool)
            _extract_crewai_yaml(path, file.rel_path, result)

    runtime_markers = ("stategraph", "callback", "vectordb", "vectorstore", "memory", "async ", "ainvoke")
    for file in files:
        if file.suffix != ".py":
            continue
        text = file.path.read_text(encoding="utf-8", errors="replace").lower()
        if any(marker in text for marker in runtime_markers):
            result.manual_review.append(f"{file.rel_path}: possible runtime orchestration or memory implementation detected.")
    _dedupe_result(result)
    return result


def _extract_crewai_yaml(path: Path, rel_path: str, result: ExtractionResult) -> None:
    if not rel_path.lower().endswith(("agents.yaml", "tasks.yaml")):
        return
    data = load_yamlish(path)
    if not isinstance(data, dict):
        return
    line_index = yaml_line_index(path)
    for key, value in data.items():
        if not isinstance(value, dict):
            continue
        if rel_path.lower().endswith("agents.yaml"):
            if not value.get("role") and not value.get("goal"):
                continue
            role = _clean_value(value.get("role") or key)
            goal = value.get("goal")
            backstory = value.get("backstory")
            llm = value.get("llm")
            if goal:
                result.identity_fragments.append(IdentityFragment("goal", role, _clean_value(goal), rel_path))
            if backstory:
                result.identity_fragments.append(IdentityFragment("backstory", role, _clean_value(backstory), rel_path))
            if llm:
                result.model_preferences.append(IdentityFragment("model", role, _clean_value(llm), rel_path))
            _extract_tool_refs(value.get("tools"), rel_path, result)
            if "knowledge_sources" in value:
                _extract_knowledge_sources(value.get("knowledge_sources"), "agent", str(key), rel_path, result)
                result.manual_review.append(f"{_yaml_location(rel_path, line_index, str(key), 'knowledge_sources')}: agent '{key}' field 'knowledge_sources' requires manual review.")
            result.hierarchy.append({"name": role, "source": rel_path, "role": "source-agent"})
        else:
            description = value.get("description")
            expected = value.get("expected_output")
            guardrail = value.get("guardrail")
            guardrails = value.get("guardrails")
            if description:
                result.identity_fragments.append(IdentityFragment("task", str(key), _clean_value(description), rel_path))
            if expected:
                result.rules.append(IdentityFragment("expected_output", str(key), _clean_value(expected), rel_path))
            if isinstance(guardrail, str):
                result.rules.append(IdentityFragment("guardrail", str(key), _clean_value(guardrail), rel_path))
            if guardrails:
                result.manual_review.append(f"{rel_path}: task '{key}' uses guardrails; review schema/runtime behavior.")
            _extract_tool_refs(value.get("tools"), rel_path, result)
            if "knowledge_sources" in value:
                _extract_knowledge_sources(value.get("knowledge_sources"), "task", str(key), rel_path, result)
            if "context" in value:
                _extract_task_context(value.get("context"), str(key), rel_path, result)
            for runtime_key in ("context", "async_execution", "output_json", "output_pydantic", "tools", "knowledge_sources"):
                if runtime_key in value:
                    result.manual_review.append(f"{_yaml_location(rel_path, line_index, str(key), runtime_key)}: task '{key}' field '{runtime_key}' requires manual review.")


def _extract_claude_imports(file: SourceFile, by_rel: dict[str, SourceFile], result: ExtractionResult) -> None:
    if file.path.name not in {"CLAUDE.md", "CLAUDE.local.md"} and file.rel_path != ".claude/CLAUDE.md":
        return
    text = file.path.read_text(encoding="utf-8", errors="replace")
    base = Path(file.rel_path).parent
    for match in re.finditer(r"(?<!\w)@([A-Za-z0-9_./-]+(?:\.md|\.txt|\.json|\.yaml|\.yml)?)", text):
        imported = (base / match.group(1)).as_posix()
        if imported.startswith("./"):
            imported = imported[2:]
        source = by_rel.get(imported)
        if not source:
            result.manual_review.append(f"{file.rel_path}: imported Claude memory '{match.group(1)}' was not found.")
            continue
        imported_text = source.path.read_text(encoding="utf-8", errors="replace").strip()
        if imported_text:
            result.identity_fragments.append(IdentityFragment("claude_import", match.group(1), imported_text, source.rel_path))


def _extract_tool_refs(value: object, rel_path: str, result: ExtractionResult) -> None:
    names: list[str] = []
    if isinstance(value, str):
        names.append(value)
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, str):
                names.append(item)
            elif isinstance(item, dict):
                name = item.get("name") or item.get("tool") or item.get("class")
                if name:
                    names.append(str(name))
    for name in names:
        clean = name.strip()
        if not clean:
            continue
        if any(tool.name == clean and tool.source == rel_path for tool in result.tools):
            continue
        result.tools.append(
            ToolSchema(
                name=clean,
                description=f"CrewAI YAML tool reference '{clean}'. Implementation is not executed or ported automatically.",
                parameters={"type": "object", "properties": {}},
                source=rel_path,
                manual_review=True,
            )
        )


def _extract_knowledge_sources(value: object, owner_kind: str, owner_name: str, rel_path: str, result: ExtractionResult) -> None:
    for source in _string_refs(value, ("path", "file", "name", "source")):
        result.identity_fragments.append(
            IdentityFragment(
                "knowledge_source",
                owner_name,
                f"{owner_kind} '{owner_name}' knowledge source: {source}",
                rel_path,
            )
        )


def _extract_task_context(value: object, task_name: str, rel_path: str, result: ExtractionResult) -> None:
    for context in _string_refs(value, ("task", "name", "id")):
        result.identity_fragments.append(
            IdentityFragment(
                "task_context",
                task_name,
                f"task '{task_name}' context dependency: {context}",
                rel_path,
            )
        )


def _string_refs(value: object, dict_keys: tuple[str, ...]) -> list[str]:
    refs: list[str] = []
    if isinstance(value, str):
        refs.append(value)
    elif isinstance(value, list):
        for item in value:
            refs.extend(_string_refs(item, dict_keys))
    elif isinstance(value, dict):
        for key in dict_keys:
            item = value.get(key)
            if isinstance(item, str):
                refs.append(item)
                break
    return [_clean_value(ref) for ref in refs if _clean_value(ref)]


def _clean_value(value: object) -> str:
    return " ".join(str(value).split())


def _yaml_location(rel_path: str, line_index: dict[tuple[str, str | None], int], top_key: str, field: str) -> str:
    line = line_index.get((top_key, field)) or line_index.get((top_key, None))
    return f"{rel_path}:{line}" if line else rel_path


def _merge_graph_topology(target: dict[str, object], incoming: dict[str, object]) -> None:
    for key, value in incoming.items():
        if not value:
            continue
        if isinstance(value, list):
            target.setdefault(key, [])
            existing = target[key]
            if isinstance(existing, list):
                existing.extend(value)
            else:
                target[key] = value
        elif isinstance(value, dict):
            target.setdefault(key, {})
            existing = target[key]
            if isinstance(existing, dict):
                existing.update(value)
            else:
                target[key] = value
        else:
            target[key] = value


def _dedupe_result(result: ExtractionResult) -> None:
    result.identity_fragments = _dedupe_dataclass_list(result.identity_fragments)
    result.rules = _dedupe_dataclass_list(result.rules)
    result.model_preferences = _dedupe_dataclass_list(result.model_preferences)
    result.tools = _dedupe_dataclass_list(result.tools)
    result.manual_review = list(dict.fromkeys(result.manual_review))
    result.hierarchy = _dedupe_dict_list(result.hierarchy)


def _dedupe_dataclass_list(items: list[object]) -> list[object]:
    seen: set[tuple[tuple[str, str], ...]] = set()
    deduped: list[object] = []
    for item in items:
        values = getattr(item, "__dict__", {})
        key = tuple(sorted((str(name), str(value)) for name, value in values.items()))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _dedupe_dict_list(items: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[tuple[str, str], ...]] = set()
    deduped: list[dict[str, str]] = []
    for item in items:
        key = tuple(sorted(item.items()))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped
