from __future__ import annotations

import subprocess
from pathlib import Path


def create_branch(path: Path, name: str) -> None:
    subprocess.run(["git", "checkout", "-B", name], cwd=path, check=True, timeout=60)
