from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from agentport.models import IdentityFragment, ToolSchema

IDENTITY_NAMES = {
    "role",
    "goal",
    "backstory",
    "prompt",
    "system_prompt",
    "instructions",
    "description",
    "expected_output",
    "guardrail",
}
MODEL_NAMES = {"model", "llm", "model_name", "manager_llm", "function_calling_llm"}
REVIEW_NAMES = {
    "memory",
    "knowledge_sources",
    "callback",
    "callbacks",
    "async_execution",
    "context",
    "output_json",
    "output_pydantic",
    "guardrails",
    "process",
    "manager_llm",
}
CREWAI_RUNTIME_NAMES = {
    "allow_delegation",
    "max_iter",
    "max_execution_time",
    "max_rpm",
    "respect_context_window",
    "memory",
    "verbose",
    "cache",
    "async_execution",
    "context",
    "process",
    "manager_llm",
    "function_calling_llm",
}


def extract_python_identity(
    path: Path,
    rel_path: str,
) -> tuple[list[IdentityFragment], list[IdentityFragment], list[ToolSchema], list[str], dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, str]]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return [], [], [], [f"{rel_path}: Python syntax could not be parsed; manual review required."], {}, {}, []

    fragments: list[IdentityFragment] = []
    models: list[IdentityFragment] = []
    tools: list[ToolSchema] = []
    manual: list[str] = []
    hierarchy: list[dict[str, str]] = []
    constants = _collect_static_strings(tree)
    pydantic_schemas = _collect_pydantic_schemas(tree)
    crewai_runtime = _empty_crewai_runtime(rel_path)
    topology = _empty_langgraph_topology(rel_path)
    langchain_runtime = _empty_langchain_runtime(rel_path)
    _capture_crewai_config_mappings(tree, fragments, manual, hierarchy, rel_path, constants)

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            _capture_langgraph_stategraph(node, topology)
        elif isinstance(node, ast.AnnAssign):
            _capture_typed_dict_field(node, topology)

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if not isinstance(target, ast.Name):
                    continue
                target_name = target.id.lower()
                value = _static_text(node.value, constants)
                if value:
                    if any(marker in target_name for marker in ("prompt", "instruction", "persona", "role", "goal")):
                        fragments.append(IdentityFragment("constant", target.id, value, rel_path))
                    if target_name in {"model", "model_name", "llm"}:
                        models.append(IdentityFragment("model", target.id, value, rel_path))
                if isinstance(node.value, ast.Call):
                    call_name = _call_name(node.value.func)
                    if "tool" in call_name.lower():
                        tools.append(_tool_schema_from_call(node.value, target.id, call_name, rel_path, constants, pydantic_schemas, manual))
        elif isinstance(node, ast.Call):
            name = _call_name(node.func)
            _capture_langchain_call(node, name, rel_path, constants, fragments, manual, langchain_runtime)
            if name.lower().endswith(("agent", "task", "crew")):
                _capture_crewai_call(node, name, rel_path, constants, pydantic_schemas, fragments, manual, crewai_runtime)
                for keyword in node.keywords:
                    static_value = _static_text(keyword.value, constants)
                    if keyword.arg in IDENTITY_NAMES and static_value:
                        fragments.append(IdentityFragment(keyword.arg, name, static_value, rel_path))
                    if keyword.arg in MODEL_NAMES and static_value:
                        models.append(IdentityFragment("model", name, static_value, rel_path))
                    if keyword.arg in REVIEW_NAMES:
                        value_name = _call_name(keyword.value) or _constant_name(keyword.value)
                        suffix = f" ({value_name})" if value_name else ""
                        manual.append(f"{rel_path}:{node.lineno}: CrewAI field '{keyword.arg}'{suffix} requires manual review for runtime/schema-specific behavior.")
                    if keyword.arg == "tools" and isinstance(keyword.value, (ast.List, ast.Tuple)):
                        for item in keyword.value.elts:
                            tool_name = _call_name(item) or _constant_name(item)
                            if tool_name:
                                tools.append(
                                    ToolSchema(
                                        name=tool_name.split(".")[-1],
                                        description=f"Tool reference from {name} tools list. Implementation is not executed or ported automatically.",
                                        parameters={"type": "object", "properties": {}},
                                        source=rel_path,
                                        manual_review=True,
                                    )
                                )
            if "tool" in name.lower():
                tools.append(_tool_schema_from_call(node, name.split(".")[-1], name, rel_path, constants, pydantic_schemas, manual))
            if name.endswith((".add_node", "add_node")):
                graph_item = _first_call_arg(node)
                if graph_item:
                    fragments.append(IdentityFragment("langgraph_node", graph_item, f"LangGraph node: {graph_item}", rel_path))
                    manual.append(f"{rel_path}:{node.lineno}: LangGraph node '{graph_item}' is topology/runtime logic and requires manual review.")
                    topology["nodes"].append(
                        {
                            "name": graph_item,
                            "handler": _constant_name(node.args[1]) or _call_name(node.args[1]) if len(node.args) > 1 else "",
                            "source": rel_path,
                            "line": node.lineno,
                        }
                    )
            if name.endswith((".add_edge", "add_edge", ".add_conditional_edges", "add_conditional_edges")):
                args = [_constant_name(arg) or _call_name(arg) for arg in node.args]
                route = " -> ".join(arg for arg in args if arg)
                if route:
                    fragments.append(IdentityFragment("langgraph_edge", name.split(".")[-1], route, rel_path))
                    manual.append(f"{rel_path}:{node.lineno}: LangGraph edge '{route}' is graph routing and requires manual review.")
                    if name.endswith((".add_conditional_edges", "add_conditional_edges")):
                        topology["conditional_edges"].append(_conditional_edge_data(node, rel_path))
                    else:
                        topology["edges"].append(_edge_data(node, rel_path))
            if name.endswith((".compile", "compile")):
                manual.append(f"{rel_path}:{node.lineno}: LangGraph compile call detected; compiled runtime is not ported automatically.")
                topology["compile_calls"].append({"source": rel_path, "line": node.lineno, "call": name})
                for keyword in node.keywords:
                    if keyword.arg in {"checkpointer", "store", "interrupt_before", "interrupt_after", "debug"}:
                        value = _constant_name(keyword.value) or _call_name(keyword.value) or keyword.arg
                        topology["runtime_markers"].append({"kind": keyword.arg, "value": value, "source": rel_path, "line": node.lineno})
                        manual.append(f"{rel_path}:{node.lineno}: LangGraph compile option '{keyword.arg}' requires manual review.")
            if name.endswith((".stream", "stream", ".astream", "astream")):
                topology["runtime_markers"].append({"kind": "streaming", "value": name, "source": rel_path, "line": node.lineno})
                manual.append(f"{rel_path}:{node.lineno}: LangGraph streaming call detected; runtime streaming behavior is not ported automatically.")
            if name.endswith((".invoke", "invoke", ".ainvoke", "ainvoke")):
                topology["runtime_markers"].append({"kind": "invoke", "value": name, "source": rel_path, "line": node.lineno})
        elif isinstance(node, ast.ClassDef):
            _capture_typed_dict_class(node, topology)
            _capture_class_config_paths(node, fragments, rel_path, constants)
            bases = " ".join(_call_name(base) for base in node.bases)
            if "Tool" in bases or node.name.lower().endswith("tool"):
                doc = ast.get_docstring(node) or f"Tool class {node.name} detected."
                tools.append(ToolSchema(node.name, doc, {"type": "object", "properties": {}}, rel_path, manual_review=True))
        elif isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
            decorators = {_call_name(dec) for dec in node.decorator_list}
            if any(decorator.split(".")[-1] == "tool" for decorator in decorators):
                doc = ast.get_docstring(node) or f"LangChain tool function {node.name} detected."
                parameters = _function_input_schema(node)
                tools.append(ToolSchema(node.name, doc, parameters, rel_path, manual_review=True))
                langchain_runtime["tools"].append({"name": node.name, "kind": "decorated_function", "input_schema": parameters, "source": rel_path, "line": node.lineno})
                manual.append(f"{rel_path}:{node.lineno}: LangChain tool function '{node.name}' implementation requires manual review.")
            if decorators.intersection({"agent", "task", "crew", "CrewBase", "crewai.project.agent", "crewai.project.task", "crewai.project.crew"}):
                fragments.append(IdentityFragment("crewai_decorator", node.name, f"CrewAI decorated function: {node.name}", rel_path))
                if "crew" in decorators or "crewai.project.crew" in decorators:
                    manual.append(f"{rel_path}:{node.lineno}: CrewAI crew orchestration function '{node.name}' requires manual review.")
            if node.name in {"invoke", "ainvoke", "run", "arun", "execute"}:
                manual.append(f"{rel_path}:{node.lineno}: runtime execution function '{node.name}' requires manual review.")

    return fragments, models, tools, manual, _compact_crewai_runtime(crewai_runtime), _compact_langgraph_topology(topology), _compact_langchain_runtime(langchain_runtime), hierarchy


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = _call_name(node.value)
        return f"{left}.{node.attr}" if left else node.attr
    return ""


def _constant_name(node: ast.AST) -> str:
    if isinstance(node, ast.Constant):
        return str(node.value)
    if isinstance(node, ast.Name):
        return node.id
    return ""


def _collect_static_strings(tree: ast.AST) -> dict[str, str]:
    constants: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            value = _static_text(node.value, constants)
            if not value:
                continue
            for target in node.targets:
                if isinstance(target, ast.Name):
                    constants[target.id] = value
    return constants


def _collect_pydantic_schemas(tree: ast.AST) -> dict[str, dict[str, Any]]:
    schemas: dict[str, dict[str, Any]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        bases = {_call_name(base).split(".")[-1] for base in node.bases}
        if not bases.intersection({"BaseModel", "pydantic.BaseModel"}):
            continue
        properties: dict[str, Any] = {}
        required: list[str] = []
        for statement in node.body:
            if not isinstance(statement, ast.AnnAssign) or not isinstance(statement.target, ast.Name):
                continue
            field_name = statement.target.id
            schema = _annotation_schema(statement.annotation)
            default = statement.value
            description = _field_description(default)
            if description:
                schema = {**schema, "description": description}
            properties[field_name] = schema
            if _pydantic_field_required(default):
                required.append(field_name)
        schema: dict[str, Any] = {"type": "object", "properties": properties}
        if required:
            schema["required"] = required
        schemas[node.name] = schema
    return schemas


def _pydantic_field_required(default: ast.AST | None) -> bool:
    if default is None:
        return True
    if isinstance(default, ast.Constant) and default.value is None:
        return False
    if isinstance(default, ast.Call) and _call_name(default.func).split(".")[-1] == "Field":
        if not default.args:
            return False
        first = default.args[0]
        if isinstance(first, ast.Constant):
            if first.value is ...:
                return True
            if first.value is None:
                return False
            return False
        if isinstance(first, ast.Name) and first.id == "Ellipsis":
            return True
        return False
    return False


def _field_description(default: ast.AST | None) -> str:
    if not isinstance(default, ast.Call) or _call_name(default.func).split(".")[-1] != "Field":
        return ""
    for keyword in default.keywords:
        if keyword.arg == "description" and isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str):
            return keyword.value.value
    return ""


def _static_text(node: ast.AST, constants: dict[str, str]) -> str:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value.strip()
    if isinstance(node, ast.Name):
        return constants.get(node.id, "")
    if isinstance(node, ast.JoinedStr):
        parts: list[str] = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                parts.append(value.value)
            elif isinstance(value, ast.FormattedValue):
                resolved = _static_text(value.value, constants)
                if not resolved:
                    return ""
                parts.append(resolved)
            else:
                return ""
        return "".join(parts).strip()
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _static_text(node.left, constants)
        right = _static_text(node.right, constants)
        if left and right:
            return f"{left}{right}".strip()
    return ""


def _first_call_arg(node: ast.Call) -> str:
    if not node.args:
        return ""
    return _constant_name(node.args[0]) or _call_name(node.args[0])


def _empty_langgraph_topology(rel_path: str) -> dict[str, Any]:
    return {
        "source_files": [rel_path],
        "state_schemas": [],
        "nodes": [],
        "edges": [],
        "conditional_edges": [],
        "compile_calls": [],
        "runtime_markers": [],
    }


def _empty_crewai_runtime(rel_path: str) -> dict[str, Any]:
    return {
        "source_files": [rel_path],
        "agents": [],
        "tasks": [],
        "crews": [],
        "runtime_markers": [],
        "output_schemas": [],
    }


def _empty_langchain_runtime(rel_path: str) -> dict[str, Any]:
    return {
        "source_files": [rel_path],
        "agents": [],
        "executors": [],
        "prompts": [],
        "tools": [],
        "runtime_markers": [],
    }


def _compact_crewai_runtime(runtime: dict[str, Any]) -> dict[str, Any]:
    if not any(value for key, value in runtime.items() if key != "source_files"):
        return {}
    return {key: value for key, value in runtime.items() if value}


def _compact_langgraph_topology(topology: dict[str, Any]) -> dict[str, Any]:
    if not any(value for key, value in topology.items() if key != "source_files"):
        return {}
    return {key: value for key, value in topology.items() if value}


def _compact_langchain_runtime(runtime: dict[str, Any]) -> dict[str, Any]:
    if not any(value for key, value in runtime.items() if key != "source_files"):
        return {}
    return {key: value for key, value in runtime.items() if value}


def _capture_langgraph_stategraph(node: ast.Assign, topology: dict[str, Any]) -> None:
    if not isinstance(node.value, ast.Call):
        return
    if _call_name(node.value.func).split(".")[-1] != "StateGraph":
        return
    state_schema = _constant_name(node.value.args[0]) or _call_name(node.value.args[0]) if node.value.args else ""
    graph_names = [target.id for target in node.targets if isinstance(target, ast.Name)]
    topology["state_schemas"].append(
        {
            "name": state_schema or "unknown",
            "graph_variables": graph_names,
            "line": node.lineno,
        }
    )


def _capture_typed_dict_class(node: ast.ClassDef, topology: dict[str, Any]) -> None:
    bases = {_call_name(base).split(".")[-1] for base in node.bases}
    if "TypedDict" not in bases:
        return
    fields: list[dict[str, str]] = []
    for statement in node.body:
        if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
            fields.append({"name": statement.target.id, "type": _annotation_name(statement.annotation)})
    topology["state_schemas"].append({"name": node.name, "kind": "TypedDict", "fields": fields, "line": node.lineno})


def _capture_typed_dict_field(node: ast.AnnAssign, topology: dict[str, Any]) -> None:
    if not isinstance(node.target, ast.Name):
        return
    annotation = _annotation_name(node.annotation)
    if "State" in node.target.id and annotation:
        topology["runtime_markers"].append({"kind": "state_annotation", "value": f"{node.target.id}: {annotation}", "line": node.lineno})


def _capture_class_config_paths(node: ast.ClassDef, fragments: list[IdentityFragment], rel_path: str, constants: dict[str, str]) -> None:
    for statement in node.body:
        if not isinstance(statement, ast.Assign):
            continue
        value = _static_text(statement.value, constants)
        if not value:
            continue
        for target in statement.targets:
            if not isinstance(target, ast.Name):
                continue
            if target.id in {"agents_config", "tasks_config"} or target.id.endswith("_config"):
                fragments.append(IdentityFragment("config_path", f"{node.name}.{target.id}", value, rel_path))


def _capture_crewai_config_mappings(
    tree: ast.AST,
    fragments: list[IdentityFragment],
    manual: list[str],
    hierarchy: list[dict[str, str]],
    rel_path: str,
    constants: dict[str, str],
) -> None:
    for class_node in (node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)):
        class_constants = {**constants, **_class_static_strings(class_node, constants)}
        config_paths = _class_config_paths(class_node, class_constants)
        if not config_paths:
            continue
        for statement in class_node.body:
            if not isinstance(statement, (ast.AsyncFunctionDef, ast.FunctionDef)):
                continue
            decorators = {_call_name(dec).split(".")[-1] for dec in statement.decorator_list}
            if "agent" not in decorators and "task" not in decorators:
                continue
            mapping = _decorated_config_mapping(statement, config_paths, class_constants)
            if not mapping:
                continue
            config_name, config_path, key = mapping
            role = "source-agent" if "agent" in decorators or config_name == "agents_config" else "source-task"
            fragments.append(IdentityFragment("crewai_config_mapping", statement.name, f"{statement.name} -> {config_path}:{key}", rel_path))
            hierarchy.append({"name": key, "source": config_path, "role": role})
            manual.append(f"{rel_path}:{statement.lineno}: CrewAI decorated function '{statement.name}' maps to {config_path}:{key}; review runtime wiring.")


def _capture_crewai_call(
    node: ast.Call,
    name: str,
    rel_path: str,
    constants: dict[str, str],
    pydantic_schemas: dict[str, dict[str, Any]],
    fragments: list[IdentityFragment],
    manual: list[str],
    runtime: dict[str, Any],
) -> None:
    short_name = name.split(".")[-1]
    lowered = short_name.lower()
    if lowered not in {"agent", "task", "crew"}:
        return

    kwargs = {keyword.arg: _argument_value(keyword.value, constants) for keyword in node.keywords if keyword.arg}
    item = {
        "kind": short_name,
        "kwargs": kwargs,
        "source": rel_path,
        "line": node.lineno,
    }
    if lowered == "agent":
        runtime["agents"].append(item)
    elif lowered == "task":
        runtime["tasks"].append(item)
    else:
        runtime["crews"].append(item)

    for keyword in node.keywords:
        if not keyword.arg:
            continue
        if keyword.arg in CREWAI_RUNTIME_NAMES:
            value = _argument_value(keyword.value, constants)
            runtime["runtime_markers"].append(
                {
                    "kind": keyword.arg,
                    "value": value,
                    "call": short_name,
                    "source": rel_path,
                    "line": node.lineno,
                }
            )
            manual.append(f"{rel_path}:{node.lineno}: CrewAI runtime option '{keyword.arg}' on {short_name} requires manual review.")
        if keyword.arg in {"output_json", "output_pydantic"}:
            schema_ref = _node_ref(keyword.value) or keyword.arg
            schema = pydantic_schemas.get(schema_ref)
            schema_data: dict[str, Any] = {
                "kind": keyword.arg,
                "name": schema_ref,
                "source": rel_path,
                "line": node.lineno,
            }
            if schema:
                schema_data["schema"] = schema
                field_names = ", ".join(schema.get("properties", {}).keys())
                fragments.append(
                    IdentityFragment(
                        "output_schema",
                        schema_ref,
                        f"{keyword.arg}: {schema_ref}" + (f" fields: {field_names}" if field_names else ""),
                        rel_path,
                    )
                )
            else:
                schema_data["unresolved"] = True
                fragments.append(IdentityFragment("output_schema", schema_ref, f"{keyword.arg}: {schema_ref}", rel_path))
                manual.append(f"{rel_path}:{node.lineno}: CrewAI output schema '{schema_ref}' could not be resolved statically.")
            runtime["output_schemas"].append(schema_data)


def _class_config_paths(node: ast.ClassDef, constants: dict[str, str]) -> dict[str, str]:
    paths: dict[str, str] = {}
    for statement in node.body:
        if not isinstance(statement, ast.Assign):
            continue
        value = _static_text(statement.value, constants)
        if not value:
            continue
        for target in statement.targets:
            if isinstance(target, ast.Name) and (target.id in {"agents_config", "tasks_config"} or target.id.endswith("_config")):
                paths[target.id] = value
    return paths


def _class_static_strings(node: ast.ClassDef, constants: dict[str, str]) -> dict[str, str]:
    values: dict[str, str] = {}
    for statement in node.body:
        if not isinstance(statement, ast.Assign):
            continue
        value = _static_text(statement.value, constants)
        if not value:
            continue
        for target in statement.targets:
            if isinstance(target, ast.Name):
                values[target.id] = value
    return values


def _decorated_config_mapping(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    config_paths: dict[str, str],
    constants: dict[str, str],
) -> tuple[str, str, str] | None:
    local_constants = dict(constants)
    local_config_refs: dict[str, tuple[str, str]] = {}

    for statement in ast.walk(node):
        if not isinstance(statement, ast.Assign):
            continue
        value = _static_text(statement.value, local_constants)
        ref = _config_ref(statement.value, local_constants)
        for target in statement.targets:
            if not isinstance(target, ast.Name):
                continue
            if value:
                local_constants[target.id] = value
            if ref:
                local_config_refs[target.id] = ref

    for statement in ast.walk(node):
        if not isinstance(statement, ast.Call):
            continue
        for keyword in statement.keywords:
            if keyword.arg != "config":
                continue
            ref = _config_ref(keyword.value, local_constants)
            if ref is None and isinstance(keyword.value, ast.Name):
                ref = local_config_refs.get(keyword.value.id)
            if not ref:
                continue
            config_name, key = ref
            config_path = config_paths.get(config_name)
            if config_path:
                return config_name, config_path, key
    return None


def _config_ref(node: ast.AST, constants: dict[str, str]) -> tuple[str, str] | None:
    if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Attribute):
        config_name = node.value.attr
        key = _static_key(node.slice, constants)
        if config_name and key:
            return config_name, key
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "get":
        config_source = node.func.value
        if isinstance(config_source, ast.Attribute) and node.args:
            config_name = config_source.attr
            key = _static_key(node.args[0], constants)
            if config_name and key:
                return config_name, key
    return None


def _static_key(node: ast.AST, constants: dict[str, str]) -> str:
    value = _static_text(node, constants) or _constant_name(node)
    if value:
        return value
    if isinstance(node, ast.Attribute):
        return constants.get(node.attr, "")
    return ""


def _capture_langchain_call(
    node: ast.Call,
    name: str,
    rel_path: str,
    constants: dict[str, str],
    fragments: list[IdentityFragment],
    manual: list[str],
    runtime: dict[str, Any],
) -> None:
    short_name = name.split(".")[-1]
    lowered = name.lower()
    if short_name in {"initialize_agent", "create_react_agent", "create_structured_chat_agent", "create_openai_tools_agent"}:
        runtime["agents"].append(_langchain_call_data(node, short_name, rel_path, constants))
        manual.append(f"{rel_path}:{node.lineno}: LangChain agent constructor '{short_name}' requires manual review for runtime behavior.")
    elif short_name == "ZeroShotAgent" or name.endswith("ZeroShotAgent.from_llm_and_tools"):
        runtime["agents"].append(_langchain_call_data(node, "ZeroShotAgent", rel_path, constants))
        manual.append(f"{rel_path}:{node.lineno}: LangChain ZeroShotAgent constructor requires manual review for runtime behavior.")
    elif short_name == "AgentExecutor":
        runtime["executors"].append(_langchain_call_data(node, short_name, rel_path, constants))
        manual.append(f"{rel_path}:{node.lineno}: LangChain AgentExecutor runtime loop requires manual review.")

    if short_name == "PromptTemplate" or name.endswith("PromptTemplate.from_template"):
        prompt = _first_static_arg(node, constants) or _keyword_static(node, "template", constants)
        runtime["prompts"].append({"kind": short_name, "template": prompt, "source": rel_path, "line": node.lineno})
        if prompt:
            fragments.append(IdentityFragment("langchain_prompt", short_name, prompt, rel_path))
    elif short_name == "ChatPromptTemplate" or name.endswith("ChatPromptTemplate.from_messages"):
        messages = _message_templates(node, constants)
        runtime["prompts"].append({"kind": short_name, "messages": messages, "source": rel_path, "line": node.lineno})
        for message in messages:
            text = message.get("template", "")
            if text:
                fragments.append(IdentityFragment("langchain_chat_prompt", message.get("role", "message"), text, rel_path))

    if short_name in {"Tool", "StructuredTool"} or name.endswith(("StructuredTool.from_function", "Tool.from_function")):
        runtime["tools"].append(_langchain_call_data(node, short_name, rel_path, constants))
    if any(marker in lowered for marker in ("retriever", "vectorstore", "faiss", "chroma")):
        runtime["runtime_markers"].append({"kind": "retrieval_or_vectorstore", "value": name, "source": rel_path, "line": node.lineno})
        manual.append(f"{rel_path}:{node.lineno}: LangChain retriever/vectorstore call '{name}' requires manual review.")


def _tool_schema_from_call(
    node: ast.Call,
    fallback_name: str,
    call_name: str,
    rel_path: str,
    constants: dict[str, str],
    pydantic_schemas: dict[str, dict[str, Any]],
    manual: list[str],
) -> ToolSchema:
    tool_name = _keyword_static(node, "name", constants) or _function_name_from_tool_call(node) or fallback_name
    description = _keyword_static(node, "description", constants)
    if not description:
        description = f"Tool instance {tool_name} created from {call_name}. Implementation is not executed or ported automatically."
    args_schema = _keyword_ref(node, "args_schema")
    parameters = {"type": "object", "properties": {}}
    if args_schema:
        resolved = pydantic_schemas.get(args_schema)
        if resolved:
            parameters = resolved
        else:
            manual.append(f"{rel_path}:{node.lineno}: LangChain tool args_schema '{args_schema}' could not be resolved statically.")
    return ToolSchema(
        name=tool_name.split(".")[-1],
        description=description,
        parameters=parameters,
        source=rel_path,
        manual_review=True,
    )


def _function_name_from_tool_call(node: ast.Call) -> str:
    for keyword in node.keywords:
        if keyword.arg in {"func", "coroutine"}:
            value = _node_ref(keyword.value)
            if value:
                return value.split(".")[-1]
    if node.args:
        first = _node_ref(node.args[0])
        if first:
            return first.split(".")[-1]
    return ""


def _keyword_ref(node: ast.Call, key: str) -> str:
    for keyword in node.keywords:
        if keyword.arg == key:
            return _node_ref(keyword.value)
    return ""


def _langchain_call_data(node: ast.Call, kind: str, rel_path: str, constants: dict[str, str]) -> dict[str, Any]:
    return {
        "kind": kind,
        "args": [_argument_value(arg, constants) for arg in node.args],
        "kwargs": {keyword.arg or "kwargs": _argument_value(keyword.value, constants) for keyword in node.keywords},
        "source": rel_path,
        "line": node.lineno,
    }


def _argument_value(node: ast.AST, constants: dict[str, str]) -> Any:
    try:
        return ast.literal_eval(node)
    except (ValueError, SyntaxError):
        pass
    static = _static_text(node, constants)
    if static:
        return static
    ref = _node_ref(node)
    if ref:
        return ref
    if isinstance(node, (ast.List, ast.Tuple)):
        return [_argument_value(item, constants) for item in node.elts]
    if isinstance(node, ast.Dict):
        return {_argument_value(key, constants): _argument_value(value, constants) for key, value in zip(node.keys, node.values) if key is not None}
    return ""


def _function_input_schema(node: ast.FunctionDef | ast.AsyncFunctionDef) -> dict[str, Any]:
    properties: dict[str, Any] = {}
    required: list[str] = []

    positional = list(node.args.posonlyargs) + list(node.args.args)
    positional_defaults = [None] * (len(positional) - len(node.args.defaults)) + list(node.args.defaults)
    for arg, default in zip(positional, positional_defaults):
        if arg.arg in {"self", "cls"}:
            continue
        properties[arg.arg] = _annotation_schema(arg.annotation)
        if default is None:
            required.append(arg.arg)

    for arg, default in zip(node.args.kwonlyargs, node.args.kw_defaults):
        properties[arg.arg] = _annotation_schema(arg.annotation)
        if default is None:
            required.append(arg.arg)

    schema: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema


def _annotation_schema(node: ast.AST | None) -> dict[str, Any]:
    if node is None:
        return {}
    name = _annotation_name(node)
    lowered = name.lower()
    if lowered in {"str", "builtins.str"}:
        return {"type": "string"}
    if lowered in {"int", "builtins.int"}:
        return {"type": "integer"}
    if lowered in {"float", "builtins.float"}:
        return {"type": "number"}
    if lowered in {"bool", "builtins.bool"}:
        return {"type": "boolean"}
    if lowered.startswith(("list[", "typing.list[", "sequence[", "typing.sequence[")):
        return {"type": "array"}
    if lowered.startswith(("dict[", "typing.dict[", "mapping[", "typing.mapping[")):
        return {"type": "object"}
    if lowered in {"any", "typing.any"}:
        return {}
    return {"x-python-type": name}


def _first_static_arg(node: ast.Call, constants: dict[str, str]) -> str:
    if not node.args:
        return ""
    return _static_text(node.args[0], constants)


def _keyword_static(node: ast.Call, key: str, constants: dict[str, str]) -> str:
    for keyword in node.keywords:
        if keyword.arg == key:
            return _static_text(keyword.value, constants)
    return ""


def _message_templates(node: ast.Call, constants: dict[str, str]) -> list[dict[str, str]]:
    if not node.args or not isinstance(node.args[0], (ast.List, ast.Tuple)):
        return []
    messages: list[dict[str, str]] = []
    for item in node.args[0].elts:
        if isinstance(item, (ast.List, ast.Tuple)) and len(item.elts) >= 2:
            role = _static_text(item.elts[0], constants) or _node_ref(item.elts[0])
            template = _static_text(item.elts[1], constants) or _node_ref(item.elts[1])
            messages.append({"role": role, "template": template})
        else:
            ref = _node_ref(item) or _static_text(item, constants)
            if ref:
                messages.append({"role": "message", "template": ref})
    return messages


def _edge_data(node: ast.Call, rel_path: str) -> dict[str, Any]:
    return {
        "source": _node_ref(node.args[0]) if len(node.args) > 0 else "",
        "target": _node_ref(node.args[1]) if len(node.args) > 1 else "",
        "file": rel_path,
        "line": node.lineno,
    }


def _conditional_edge_data(node: ast.Call, rel_path: str) -> dict[str, Any]:
    return {
        "source": _node_ref(node.args[0]) if len(node.args) > 0 else "",
        "router": _node_ref(node.args[1]) if len(node.args) > 1 else "",
        "path_map": _literal_mapping(node.args[2]) if len(node.args) > 2 else {},
        "file": rel_path,
        "line": node.lineno,
    }


def _node_ref(node: ast.AST) -> str:
    return _constant_name(node) or _call_name(node)


def _literal_mapping(node: ast.AST) -> dict[str, str]:
    try:
        value = ast.literal_eval(node)
    except (ValueError, SyntaxError):
        return {}
    if not isinstance(value, dict):
        return {}
    return {str(key): str(item) for key, item in value.items()}


def _annotation_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return _call_name(node)
    if isinstance(node, ast.Subscript):
        left = _annotation_name(node.value)
        right = _annotation_name(node.slice)
        return f"{left}[{right}]" if right else left
    if isinstance(node, ast.Constant):
        return str(node.value)
    if isinstance(node, ast.Tuple):
        return ", ".join(_annotation_name(item) for item in node.elts)
    return ""
