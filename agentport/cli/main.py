from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from agentport.orchestrator import analyze, compatibility, doctor, explain, fixtures_list, port
from agentport.core.docs_registry import docs_check

EXIT_ERROR = 1
EXIT_VALIDATION_FAILED = 2
EXIT_STRICT_FAILED = 3
STRICT_MIN_CONFIDENCE = 0.70
STRICT_PROFILE_MARKERS = ("generic", "unclassified", "unimplemented")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agentport", description="Port framework agent identity layers into GitAgent repos.")
    sub = parser.add_subparsers(dest="command", required=True)

    analyze_cmd = sub.add_parser("analyze", help="Detect framework and extract portable identity metadata without writing output.")
    analyze_cmd.add_argument("--source", required=True, help="Local source repo path or Git URL.")
    analyze_cmd.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    analyze_cmd.add_argument("--strict", action="store_true", help="Return exit code 3 when detection/profile confidence is low or generic.")

    compatibility_cmd = sub.add_parser("compatibility", help="Show framework/profile compatibility evidence for a source repo.")
    compatibility_cmd.add_argument("--source", required=True, help="Local source repo path or Git URL.")
    compatibility_cmd.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    compatibility_cmd.add_argument("--strict", action="store_true", help="Return exit code 3 when detection/profile confidence is low or generic.")

    explain_cmd = sub.add_parser("explain", help="Explain extracted identity evidence and manual-review boundaries.")
    explain_cmd.add_argument("--source", required=True, help="Local source repo path or Git URL.")
    explain_cmd.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    explain_cmd.add_argument("--strict", action="store_true", help="Return exit code 3 when detection/profile confidence is low or generic.")

    port_cmd = sub.add_parser("port", help="Generate a GitAgent identity repo from a source framework agent.")
    port_cmd.add_argument("--source", required=True, help="Local source repo path or Git URL.")
    port_cmd.add_argument("--output", help="Target output directory.")
    port_cmd.add_argument("--validate", action="store_true", help="Run external validation if available, otherwise internal schema validation.")
    port_cmd.add_argument("--validator-command", help="Validation command override. Use {path} for the generated repo path; otherwise the path is appended.")
    port_cmd.add_argument("--pr-ready", action="store_true", help="Write PULL_REQUEST.md and validation/readiness reports.")
    port_cmd.add_argument("--llm-review", action="store_true", help="Write optional LLM_REVIEW.md advisory notes. Requires AGENTPORT_LLM_API_KEY to call a provider.")
    port_cmd.add_argument("--strict", action="store_true", help="Return exit code 3 and skip generation when detection/profile confidence is low or generic.")
    port_cmd.add_argument("--allow-partial", action="store_true", default=True, help="Allow identity-layer ports with manual-review items. This is currently the default.")
    port_cmd.add_argument("--no-learn", action="store_true", help="Disable AgentPort memory updates from validation warnings/failures.")
    port_cmd.add_argument("--json", action="store_true", help="Print machine-readable JSON.")

    docs_cmd = sub.add_parser("docs", help="Inspect preloaded framework documentation evidence.")
    docs_sub = docs_cmd.add_subparsers(dest="docs_command", required=True)
    docs_check_cmd = docs_sub.add_parser("check", help="Check known docs links and verification recommendations.")
    docs_check_cmd.add_argument("--framework", help="Framework name or alias, for example crewai, langchain, adk, claude.")
    docs_check_cmd.add_argument("--profile", help="Optional compatibility profile.")
    docs_check_cmd.add_argument("--source", help="Optional source repo path. When provided, AgentPort detects framework/profile first.")
    docs_check_cmd.add_argument("--json", action="store_true", help="Print machine-readable JSON.")

    fixtures_cmd = sub.add_parser("fixtures", help="Inspect bundled source fixtures.")
    fixtures_sub = fixtures_cmd.add_subparsers(dest="fixtures_command", required=True)
    fixtures_list_cmd = fixtures_sub.add_parser("list", help="List bundled parser compatibility fixtures.")
    fixtures_list_cmd.add_argument("--json", action="store_true", help="Print machine-readable JSON.")

    doctor_cmd = sub.add_parser("doctor", help="Run AgentPort environment and fixture preflight checks.")
    doctor_cmd.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(__file__).resolve().parents[2]
    try:
        if args.command == "analyze":
            result = analyze(args.source)
            if args.json:
                print(json.dumps(result, indent=2))
            else:
                framework = result["framework"]
                assert isinstance(framework, dict)
                print(f"Framework: {framework['framework']} ({framework['confidence']:.2f})")
                print(f"Files scanned: {result['file_count']}")
                print(f"Identity fragments: {result['identity_fragments']}")
                print(f"Rules: {result['rules']}")
                print(f"Tools: {result['tools']}")
            return _strict_exit(result) if args.strict else 0

        if args.command == "compatibility":
            result = compatibility(args.source)
            if args.json:
                print(json.dumps(result, indent=2))
            else:
                framework = result["framework"]
                compat = result["compatibility"]
                docs = result["docs_evidence"]
                assert isinstance(framework, dict)
                assert isinstance(compat, dict)
                assert isinstance(docs, dict)
                print(f"Framework: {framework['framework']} ({framework['confidence']:.2f})")
                print(f"Profile: {compat['profile']} ({compat['confidence']:.2f})")
                print(f"Files scanned: {result['file_count']}")
                if compat["version_hints"]:
                    print("Version hints:")
                    for hint in compat["version_hints"]:
                        print(f"- {hint}")
                if compat["deprecated_patterns"]:
                    print("Deprecated patterns:")
                    for item in compat["deprecated_patterns"]:
                        print(f"- {item}")
                if compat["unknown_patterns"]:
                    print("Unknown patterns:")
                    for item in compat["unknown_patterns"]:
                        print(f"- {item}")
                print(f"Docs verification recommended: {docs['verification_recommended']}")
            return _strict_exit(result) if args.strict else 0

        if args.command == "explain":
            result = explain(args.source)
            if args.json:
                print(json.dumps(result, indent=2))
            else:
                framework = result["framework"]
                compat = result["compatibility"]
                extraction = result["extraction"]
                assert isinstance(framework, dict)
                assert isinstance(compat, dict)
                assert isinstance(extraction, dict)
                print(f"Framework: {framework['framework']} ({framework['confidence']:.2f})")
                print(f"Profile: {compat['profile']} ({compat['confidence']:.2f})")
                print(f"Files scanned: {result['file_count']}")
                print(f"Identity fragments: {len(extraction['identity_fragments'])}")
                print(f"Rules: {len(extraction['rules'])}")
                print(f"Model preferences: {len(extraction['model_preferences'])}")
                print(f"Tools: {len(extraction['tools'])}")
                print(f"Manual review items: {len(extraction['manual_review'])}")
                if extraction["manual_review"]:
                    print("Manual review:")
                    for item in extraction["manual_review"][:10]:
                        print(f"- {item}")
            return _strict_exit(result) if args.strict else 0

        if args.command == "port":
            if args.strict:
                preflight = compatibility(args.source)
                strict_code = _strict_exit(preflight)
                if strict_code:
                    return strict_code
            result = port(
                source=args.source,
                output=args.output,
                validate=args.validate,
                pr_ready=args.pr_ready,
                learn=not args.no_learn,
                agentport_root=root,
                validator_command=args.validator_command,
                llm_review=args.llm_review,
            )
            payload = {
                "output_path": str(result.output_path),
                "framework": result.detection.__dict__,
                "generated_files": result.generated_files,
                "validation": result.validation.__dict__ if result.validation else None,
                "llm_review": result.llm_review.__dict__ if result.llm_review else None,
            }
            if args.json:
                print(json.dumps(payload, indent=2))
            else:
                print(f"Output: {result.output_path}")
                print(f"Framework: {result.detection.framework} ({result.detection.confidence:.2f})")
                if result.validation:
                    print(f"Validation: {result.validation.mode} {'passed' if result.validation.ok else 'failed'}")
                if result.llm_review:
                    print(f"LLM review: {result.llm_review.status} ({result.llm_review.report_path})")
                print(f"Generated files: {len(result.generated_files)}")
            if result.validation and not result.validation.ok:
                return EXIT_VALIDATION_FAILED
            return 0

        if args.command == "docs" and args.docs_command == "check":
            if args.source:
                analysis = analyze(args.source)
                framework = analysis["compatibility"]["framework"]  # type: ignore[index]
                profile = analysis["compatibility"]["profile"]  # type: ignore[index]
                evidence = analysis["docs_evidence"]
                payload = {
                    "source": analysis["source"],
                    "framework": analysis["framework"],
                    "compatibility": analysis["compatibility"],
                    "docs_evidence": evidence,
                }
            else:
                if not args.framework:
                    raise ValueError("docs check requires --framework or --source")
                framework = args.framework
                profile = args.profile
                evidence_obj = docs_check(framework, profile)
                payload = {
                    "framework": framework,
                    "profile": profile,
                    "docs_evidence": evidence_obj.__dict__,
                }
            if args.json:
                print(json.dumps(payload, indent=2))
            else:
                docs = payload["docs_evidence"]
                assert isinstance(docs, dict)
                print(f"Framework docs: {docs['framework']}")
                if profile:
                    print(f"Profile: {profile}")
                print(f"Verification recommended: {docs['verification_recommended']}")
                print("Links:")
                for link in docs["links"]:
                    print(f"- {link['label']}: {link['url']}")
                if docs["reasons"]:
                    print("Reasons:")
                    for reason in docs["reasons"]:
                        print(f"- {reason}")
            return 0

        if args.command == "fixtures" and args.fixtures_command == "list":
            result = fixtures_list(root)
            if args.json:
                print(json.dumps({"fixtures": result}, indent=2))
            else:
                print(f"Fixtures: {len(result)}")
                for fixture in result:
                    framework = fixture["framework"]
                    compat = fixture["compatibility"]
                    assert isinstance(framework, dict)
                    assert isinstance(compat, dict)
                    print(f"- {fixture['name']}: {framework['framework']} / {compat['profile']} ({compat['confidence']:.2f})")
            return 0

        if args.command == "doctor":
            result = doctor(root)
            if args.json:
                print(json.dumps(result, indent=2))
            else:
                print(f"AgentPort doctor: {'ok' if result['ok'] else 'failed'}")
                print(f"Errors: {result['errors']}")
                print(f"Warnings: {result['warnings']}")
                checks = result["checks"]
                assert isinstance(checks, list)
                for check in checks:
                    assert isinstance(check, dict)
                    status = "ok" if check["ok"] else check["severity"]
                    print(f"- {check['name']}: {status} - {check['detail']}")
            return 0 if result["ok"] else 1
    except Exception as exc:
        print(f"agentport: {exc}", file=sys.stderr)
        return EXIT_ERROR
    return EXIT_ERROR


def _strict_exit(result: dict[str, object]) -> int:
    failure = _strict_failure(result)
    if failure:
        print(f"agentport: strict mode failed: {failure}", file=sys.stderr)
        return EXIT_STRICT_FAILED
    return 0


def _strict_failure(result: dict[str, object]) -> str:
    framework = result.get("framework")
    compatibility_profile = result.get("compatibility")
    if not isinstance(framework, dict):
        return "framework detection result is missing"
    framework_name = str(framework.get("framework", "unknown"))
    framework_confidence = _float_value(framework.get("confidence"))
    if framework_confidence < STRICT_MIN_CONFIDENCE:
        return f"framework '{framework_name}' confidence {framework_confidence:.2f} is below {STRICT_MIN_CONFIDENCE:.2f}"
    if framework_name == "generic":
        return "framework is generic"

    if not isinstance(compatibility_profile, dict):
        return "compatibility profile is missing"
    profile = str(compatibility_profile.get("profile", "unknown"))
    profile_confidence = _float_value(compatibility_profile.get("confidence"))
    if profile_confidence < STRICT_MIN_CONFIDENCE:
        return f"profile '{profile}' confidence {profile_confidence:.2f} is below {STRICT_MIN_CONFIDENCE:.2f}"
    if any(marker in profile for marker in STRICT_PROFILE_MARKERS):
        return f"profile '{profile}' is not strict-compatible"
    return ""


def _float_value(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


if __name__ == "__main__":
    raise SystemExit(main())
