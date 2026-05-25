from __future__ import annotations

from agentport.models import ValidationResult


def parse_external_validation(stdout: str, stderr: str, returncode: int, mode: str) -> ValidationResult:
    text = "\n".join(part for part in (stdout, stderr) if part)
    warnings = [line for line in text.splitlines() if "warn" in line.lower() and "0 warnings" not in line.lower()]
    errors = [line for line in text.splitlines() if "error" in line.lower() or "fail" in line.lower()]
    if returncode != 0 and not errors:
        errors.append(text.strip() or f"{mode} exited with status {returncode}")
    return ValidationResult(mode=mode, ok=returncode == 0, errors=errors, warnings=warnings)
