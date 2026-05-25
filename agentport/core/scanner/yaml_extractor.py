from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def yaml_line_index(path: Path) -> dict[tuple[str, str | None], int]:
    text = path.read_text(encoding="utf-8", errors="replace")
    index: dict[tuple[str, str | None], int] = {}
    current_top: str | None = None
    for line_no, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        match = re.match(r"([^:#][^:]*):", stripped)
        if not match:
            continue
        key = match.group(1).strip().strip("'\"")
        if indent == 0:
            current_top = key
            index[(key, None)] = line_no
        elif current_top and indent > 0:
            index[(current_top, key)] = line_no
    return index


def load_yamlish(path: Path) -> Any:
    text = path.read_text(encoding="utf-8", errors="replace")
    try:
        import yaml  # type: ignore

        return yaml.safe_load(text) or {}
    except Exception:
        pass
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return _minimal_yaml_mapping(text)


def _minimal_yaml_mapping(text: str) -> dict[str, Any]:
    data: dict[str, Any] = {}
    current_key: str | None = None
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if not raw.startswith((" ", "\t")) and ":" in raw:
            key, value = raw.split(":", 1)
            current_key = key.strip()
            data[current_key] = value.strip().strip("'\"") or {}
        elif current_key and ":" in raw:
            key, value = raw.strip().split(":", 1)
            if not isinstance(data[current_key], dict):
                data[current_key] = {}
            data[current_key][key.strip()] = value.strip().strip("'\"")
    return data
