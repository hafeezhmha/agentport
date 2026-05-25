from __future__ import annotations

from pathlib import Path
from typing import Any

from agentport.models import ToolSchema
from agentport.core.scanner.yaml_extractor import load_yamlish


def extract_yaml_tool(path: Path, rel_path: str) -> ToolSchema | None:
    if path.suffix.lower() not in {".yaml", ".yml", ".json"}:
        return None
    data = load_yamlish(path)
    if not isinstance(data, dict):
        return None
    name = data.get("name") or data.get("tool") or path.stem
    description = data.get("description") or data.get("summary") or ""
    schema: Any = data.get("input_schema") or data.get("schema") or data.get("parameters")
    if not description and not schema:
        return None
    return ToolSchema(
        name=str(name),
        description=str(description or f"Tool metadata extracted from {rel_path}."),
        parameters=schema if isinstance(schema, dict) else {"type": "object", "properties": {}},
        source=rel_path,
        manual_review="implementation" in data,
    )
