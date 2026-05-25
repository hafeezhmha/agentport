from __future__ import annotations

from pathlib import Path

from agentport.models import SourceFile

IGNORED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    "node_modules",
    ".venv",
    "venv",
    "dist",
    "build",
}


def scan_files(root: Path, max_bytes: int = 250_000) -> list[SourceFile]:
    root = root.resolve()
    files: list[SourceFile] = []
    for path in sorted(root.rglob("*")):
        if any(part in IGNORED_DIRS for part in path.relative_to(root).parts):
            continue
        if not path.is_file():
            continue
        try:
            size = path.stat().st_size
        except OSError:
            continue
        if size > max_bytes:
            continue
        files.append(
            SourceFile(
                path=path,
                rel_path=path.relative_to(root).as_posix(),
                suffix=path.suffix.lower(),
                size=size,
            )
        )
    return files


def read_text(path: Path, limit: int = 80_000) -> str:
    raw = path.read_bytes()[:limit]
    return raw.decode("utf-8", errors="replace")
