from __future__ import annotations


def pr_branch_name(source_name: str) -> str:
    safe = "".join(ch.lower() if ch.isalnum() else "-" for ch in source_name).strip("-")
    return f"agentport/{safe or 'ported-agent'}"
