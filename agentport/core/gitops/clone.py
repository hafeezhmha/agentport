from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path


def resolve_source(source: str) -> tuple[Path, tempfile.TemporaryDirectory[str] | None]:
    if source.startswith(("https://", "git@")):
        tmp = tempfile.TemporaryDirectory(prefix="agentport-source-")
        subprocess.run(["git", "clone", "--depth", "1", source, tmp.name], check=True, timeout=180)
        return Path(tmp.name), tmp
    path = Path(source).expanduser().resolve()
    if not path.exists() or not path.is_dir():
        raise FileNotFoundError(f"Source repo path does not exist: {source}")
    return path, None
