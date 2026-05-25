from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path
from dataclasses import asdict

from agentport.models import PortResult
from agentport.core.docs_registry import docs_check
from agentport.core.generation.gitagent_writer import write_gitagent_repo
from agentport.core.generation.report_writer import write_reports
from agentport.core.gitops.clone import resolve_source
from agentport.core.learning.memory_updater import update_memory
from agentport.core.mapping.generic_mapper import make_port_plan
from agentport.core.scanner.file_tree import scan_files
from agentport.core.scanner.compatibility_profiler import profile_compatibility
from agentport.core.scanner.framework_detector import detect_framework
from agentport.core.scanner.repository_extractor import extract_repository
from agentport.core.validation.gapman_runner import validate_repo


def _scan_source(source: str) -> tuple[Path, object, list[object], object, object, object, object]:
    source_path, tmp = resolve_source(source)
    try:
        files = scan_files(source_path)
        detection = detect_framework(files)
        compatibility = profile_compatibility(files, detection)
        docs = docs_check(compatibility.framework, compatibility.profile, compatibility, detection)
        extraction = extract_repository(files)
        return source_path, tmp, files, detection, compatibility, docs, extraction
    except Exception:
        if tmp is not None:
            tmp.cleanup()
        raise


def analyze(source: str) -> dict[str, object]:
    source_path, tmp, files, detection, compatibility, docs, extraction = _scan_source(source)
    try:
        return {
            "source": str(source_path),
            "framework": detection.__dict__,
            "compatibility": compatibility.__dict__,
            "docs_evidence": docs.__dict__,
            "file_count": len(files),
            "identity_fragments": len(extraction.identity_fragments),
            "rules": len(extraction.rules),
            "tools": len(extraction.tools),
            "manual_review": extraction.manual_review,
        }
    finally:
        if tmp is not None:
            tmp.cleanup()


def compatibility(source: str) -> dict[str, object]:
    source_path, tmp, files, detection, compatibility_profile, docs, _ = _scan_source(source)
    try:
        return {
            "source": str(source_path),
            "file_count": len(files),
            "framework": detection.__dict__,
            "compatibility": compatibility_profile.__dict__,
            "docs_evidence": docs.__dict__,
        }
    finally:
        if tmp is not None:
            tmp.cleanup()


def fixtures_list(agentport_root: Path | None = None) -> list[dict[str, object]]:
    root = agentport_root or Path(__file__).resolve().parents[1]
    fixtures_dir = root / "tests" / "fixtures"
    if not fixtures_dir.exists():
        raise FileNotFoundError(f"Fixtures directory not found: {fixtures_dir}")
    fixtures: list[dict[str, object]] = []
    for fixture in sorted(item for item in fixtures_dir.iterdir() if item.is_dir()):
        files = scan_files(fixture)
        detection = detect_framework(files)
        compatibility_profile = profile_compatibility(files, detection)
        fixtures.append(
            {
                "name": fixture.name,
                "path": str(fixture),
                "file_count": len(files),
                "framework": detection.__dict__,
                "compatibility": compatibility_profile.__dict__,
                "evidence_count": len(detection.evidence) + len(compatibility_profile.evidence),
                "first_evidence": (detection.evidence + compatibility_profile.evidence)[0] if (detection.evidence + compatibility_profile.evidence) else "",
            }
        )
    return fixtures


def explain(source: str) -> dict[str, object]:
    source_path, tmp, files, detection, compatibility_profile, docs, extraction = _scan_source(source)
    try:
        return {
            "source": str(source_path),
            "file_count": len(files),
            "framework": detection.__dict__,
            "compatibility": compatibility_profile.__dict__,
            "docs_evidence": docs.__dict__,
            "extraction": asdict(extraction),
            "boundary": "AgentPort statically explains the source identity layer and runtime/manual-review boundary. It does not execute source repository code.",
        }
    finally:
        if tmp is not None:
            tmp.cleanup()


def doctor(agentport_root: Path | None = None) -> dict[str, object]:
    root = agentport_root or Path(__file__).resolve().parents[1]
    checks: list[dict[str, object]] = []

    def check(name: str, ok: bool, detail: str, severity: str = "error") -> None:
        checks.append({"name": name, "ok": ok, "severity": severity, "detail": detail})

    check("agentport_root", root.exists(), str(root))
    registry = root / "agents" / "agentport" / "knowledge" / "framework-docs" / "framework-links.md"
    check("docs_registry", registry.exists(), str(registry))
    check("pyyaml", importlib.util.find_spec("yaml") is not None, "PyYAML is available." if importlib.util.find_spec("yaml") else "PyYAML is not installed; minimal YAML fallback will be used.", "warning")
    gapman = shutil.which("gapman")
    gitagent = shutil.which("gitagent")
    check("external_gapman_validator", gapman is not None, gapman or "gapman not found; internal schema fallback will be used.", "warning")
    check("external_gitagent_validator", gitagent is not None, gitagent or "gitagent validate not found; internal schema fallback will be used.", "warning")

    fixtures = root / "tests" / "fixtures"
    smoke_sources = [
        fixtures / "crewai_schema_current",
        fixtures / "langgraph_schema_current",
        fixtures / "langchain_react_current",
        fixtures / "claude_cursor_schema_current",
    ]
    for fixture in smoke_sources:
        if not fixture.exists():
            check(f"fixture:{fixture.name}", False, f"Missing fixture {fixture}", "error")
            continue
        try:
            result = analyze(str(fixture))
            framework = result["framework"]
            assert isinstance(framework, dict)
            check(f"fixture:{fixture.name}", True, f"Detected {framework['framework']} at confidence {framework['confidence']:.2f}.")
        except Exception as exc:
            check(f"fixture:{fixture.name}", False, f"Smoke analysis failed: {exc}", "error")

    errors = [item for item in checks if not item["ok"] and item["severity"] == "error"]
    warnings = [item for item in checks if not item["ok"] and item["severity"] == "warning"]
    return {
        "ok": not errors,
        "checks": checks,
        "errors": len(errors),
        "warnings": len(warnings),
    }


def port(
    source: str,
    output: str | None,
    validate: bool = False,
    pr_ready: bool = False,
    learn: bool = True,
    agentport_root: Path | None = None,
    validator_command: str | None = None,
) -> PortResult:
    source_path, tmp = resolve_source(source)
    try:
        files = scan_files(source_path)
        detection = detect_framework(files)
        compatibility = profile_compatibility(files, detection)
        docs = docs_check(compatibility.framework, compatibility.profile, compatibility, detection)
        extraction = extract_repository(files)
        output_path = Path(output).expanduser().resolve() if output else (Path.cwd() / "generated" / f"{source_path.name}-gitagent").resolve()
        plan = make_port_plan(source_path, output_path, detection, extraction, compatibility, docs)

        generated = write_gitagent_repo(plan)
        validation = None
        if validate or pr_ready:
            write_reports(plan, generated, None, pr_ready=False)
            validation = validate_repo(output_path, validator_command=validator_command)
        generated += write_reports(plan, generated, validation, pr_ready=pr_ready)

        if validation is not None and learn and agentport_root is not None:
            updated = update_memory(agentport_root, plan, validation)
            if updated is not None:
                generated.append(str(updated.relative_to(agentport_root)))

        return PortResult(output_path=output_path, generated_files=generated, detection=detection, validation=validation)
    finally:
        if tmp is not None:
            tmp.cleanup()
