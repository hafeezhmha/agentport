from __future__ import annotations

from pathlib import Path

from agentport.models import IdentityFragment

PROMPT_FILES = {
    "CLAUDE.md",
    "CLAUDE.local.md",
    "AGENTS.md",
    "PROMPT.md",
    "RULES.md",
    ".cursorrules",
}


def extract_prompt_file(path: Path, rel_path: str) -> tuple[list[IdentityFragment], list[IdentityFragment]]:
    name = path.name
    if name not in PROMPT_FILES and not rel_path.startswith(".cursor/rules/") and rel_path != ".claude/CLAUDE.md":
        return [], []
    text = path.read_text(encoding="utf-8", errors="replace").strip()
    if not text:
        return [], []
    if rel_path.startswith(".cursor/rules/") and text.startswith("---"):
        text = _format_mdc_rule(text)
    kind = "rules" if "rule" in rel_path.lower() or name in {"RULES.md", ".cursorrules"} else "prompt"
    fragment = IdentityFragment(kind, name, text, rel_path)
    if kind == "rules":
        return [], [fragment]
    return [fragment], []


def _format_mdc_rule(text: str) -> str:
    parts = text.split("---", 2)
    if len(parts) != 3:
        return text
    _, metadata, body = parts
    metadata = metadata.strip()
    body = body.strip()
    if not metadata:
        return body
    return f"Cursor rule metadata:\n{metadata}\n\n{body}"
