from __future__ import annotations

import subprocess
from pathlib import Path


def commit_all(path: Path, message: str) -> None:
    subprocess.run(["git", "add", "."], cwd=path, check=True, timeout=60)
    subprocess.run(["git", "commit", "-m", message], cwd=path, check=True, timeout=60)
