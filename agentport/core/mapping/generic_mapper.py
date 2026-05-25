from __future__ import annotations

import re
from pathlib import Path

from agentport.models import PortPlan


def safe_repo_name(source: Path) -> str:
    name = re.sub(r"[^a-zA-Z0-9_-]+", "-", source.name.strip()).strip("-").lower()
    return name or "ported-agent"


def make_port_plan(source: Path, output: Path, detection, extraction, compatibility=None, docs_evidence=None) -> PortPlan:
    return PortPlan(
        name=f"{safe_repo_name(source)}-gitagent",
        framework=detection,
        extraction=extraction,
        source_path=source,
        output_path=output,
        compatibility=compatibility,
        docs_evidence=docs_evidence,
    )
