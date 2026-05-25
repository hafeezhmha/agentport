from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from agentport.core.validation.gapman_runner import internal_schema_validate, structural_validate, validate_repo
from agentport.orchestrator import port


FIXTURES = Path(__file__).parent / "fixtures"


class ValidationParserTests(unittest.TestCase):
    def test_structural_validation_finds_missing_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = structural_validate(Path(tmp))
        self.assertFalse(result.ok)
        self.assertTrue(result.errors)
        self.assertEqual(result.mode, "internal-schema-fallback")

    def test_internal_schema_validation_accepts_generated_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "generated"
            port(str(FIXTURES / "crewai_schema_current"), str(out), validate=False, learn=False)
            result = internal_schema_validate(out)

        self.assertTrue(result.ok, result.errors)
        self.assertEqual(result.mode, "internal-schema-fallback")

    def test_internal_schema_validation_finds_broken_references(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "generated"
            port(str(FIXTURES / "crewai_schema_current"), str(out), validate=False, learn=False)
            (out / "skills" / "ported-identity" / "SKILL.md").unlink()
            result = internal_schema_validate(out)

        self.assertFalse(result.ok)
        self.assertTrue(any("broken_reference" in error and "skills/ported-identity/SKILL.md" in error for error in result.errors))

    def test_internal_schema_validation_finds_invalid_agent_field_type(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_minimal_repo(root)
            text = (root / "agent.yaml").read_text(encoding="utf-8")
            (root / "agent.yaml").write_text(text.replace("tools:\n  []", 'tools: "search"'), encoding="utf-8")
            result = internal_schema_validate(root)

        self.assertFalse(result.ok)
        self.assertTrue(any("invalid_type: agent.yaml:tools" in error for error in result.errors))

    def test_internal_schema_validation_requires_identity_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_minimal_repo(root)
            conversion = (root / "conversion_map.json").read_text(encoding="utf-8")
            (root / "conversion_map.json").write_text(conversion.replace("identity layer", "runtime"), encoding="utf-8")
            result = internal_schema_validate(root)

        self.assertFalse(result.ok)
        self.assertTrue(any("invalid_boundary" in error for error in result.errors))

    def test_internal_schema_validation_finds_malformed_workflow(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_minimal_repo(root)
            (root / "workflows" / "ported-identity-review.yaml").write_text(
                "\n".join(
                    [
                        "name: ported-identity-review",
                        "description: Broken workflow",
                        "steps:",
                        "  - 42",
                    ]
                ),
                encoding="utf-8",
            )
            result = internal_schema_validate(root)

        self.assertFalse(result.ok)
        self.assertTrue(any("invalid_type: workflows/ported-identity-review.yaml:steps[1]" in error for error in result.errors))

    def test_internal_schema_validation_finds_missing_sod_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_minimal_repo(root)
            text = (root / "agent.yaml").read_text(encoding="utf-8")
            (root / "agent.yaml").write_text(
                text + "\ncompliance:\n  sod_policy: compliance/migration-sod-policy.md\n",
                encoding="utf-8",
            )
            result = internal_schema_validate(root)

        self.assertFalse(result.ok)
        self.assertTrue(any("broken_reference: compliance/migration-sod-policy.md" in error for error in result.errors))

    def test_internal_schema_validation_finds_incomplete_sod_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_minimal_repo(root)
            (root / "compliance").mkdir()
            (root / "compliance" / "migration-sod-policy.md").write_text("# Policy\n\nValidation happens.\n", encoding="utf-8")
            text = (root / "agent.yaml").read_text(encoding="utf-8")
            (root / "agent.yaml").write_text(
                text + "\ncompliance:\n  sod_policy: compliance/migration-sod-policy.md\n",
                encoding="utf-8",
            )
            result = internal_schema_validate(root)

        self.assertFalse(result.ok)
        self.assertTrue(any("SOD policy is missing schema writer boundary" in error for error in result.errors))

    def test_internal_schema_validation_finds_invalid_sod_workflow_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_minimal_repo(root)
            (root / "agents").mkdir()
            for name in ("schema-writer", "validation-auditor", "pr-writer"):
                (root / "agents" / name).mkdir()
            text = (root / "agent.yaml").read_text(encoding="utf-8")
            (root / "agent.yaml").write_text(
                text
                + "\nagents:\n"
                + "  schema-writer:\n    path: agents/schema-writer\n"
                + "  validation-auditor:\n    path: agents/validation-auditor\n"
                + "  pr-writer:\n    path: agents/pr-writer\n",
                encoding="utf-8",
            )
            (root / "workflows" / "ported-identity-review.yaml").write_text(
                "\n".join(
                    [
                        "name: ported-identity-review",
                        "description: Broken SOD order",
                        "steps:",
                        "  - agent: validation-auditor",
                        "    prompt: Validate too early.",
                        "  - agent: schema-writer",
                        "    prompt: Generate files too late.",
                        "channel: chat",
                    ]
                ),
                encoding="utf-8",
            )
            result = internal_schema_validate(root)

        self.assertFalse(result.ok)
        self.assertTrue(any("invalid_sod_order" in error for error in result.errors))

    def test_validator_override_replaces_path_placeholder(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            completed = _completed_process(0, "validation passed\n", "")
            with patch.dict("os.environ", {"AGENTPORT_VALIDATOR_COMMAND": "gitagent validate {path}"}):
                with patch("agentport.core.validation.gapman_runner.subprocess.run", return_value=completed) as run:
                    result = validate_repo(root)

        self.assertTrue(result.ok)
        self.assertEqual(result.mode, "validator-override")
        self.assertEqual(run.call_args.args[0], ["gitagent", "validate", str(root)])

    def test_validator_override_appends_path_when_no_placeholder(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            completed = _completed_process(0, "", "")
            with patch.dict("os.environ", {"AGENTPORT_VALIDATOR_COMMAND": "gitagent validate --compliance"}):
                with patch("agentport.core.validation.gapman_runner.subprocess.run", return_value=completed) as run:
                    result = validate_repo(root)

        self.assertTrue(result.ok)
        self.assertEqual(result.mode, "validator-override")
        self.assertEqual(run.call_args.args[0], ["gitagent", "validate", "--compliance", str(root)])

    def test_validator_override_reports_failure(self):
        completed = _completed_process(1, "", "schema failed")
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict("os.environ", {"AGENTPORT_VALIDATOR_COMMAND": "gitagent validate {path}"}):
                with patch("agentport.core.validation.gapman_runner.subprocess.run", return_value=completed):
                    result = validate_repo(Path(tmp))

        self.assertFalse(result.ok)
        self.assertEqual(result.mode, "validator-override")
        self.assertTrue(result.errors)

    def test_validator_command_argument_wins_over_environment(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            completed = _completed_process(0, "", "")
            with patch.dict("os.environ", {"AGENTPORT_VALIDATOR_COMMAND": "env-validator {path}"}):
                with patch("agentport.core.validation.gapman_runner.subprocess.run", return_value=completed) as run:
                    result = validate_repo(root, validator_command="flag-validator {path}")

        self.assertTrue(result.ok)
        self.assertEqual(run.call_args.args[0], ["flag-validator", str(root)])


def _write_minimal_repo(root: Path) -> None:
    (root / "knowledge").mkdir()
    (root / "memory").mkdir()
    (root / "workflows").mkdir()
    for rel in ("SOUL.md", "RULES.md", "DUTIES.md", "TODO_MANUAL_REVIEW.md", "migration_report.md", "framework_compatibility_report.md", "registry_readiness_report.md"):
        (root / rel).write_text("# Test\n\nReview these items\n", encoding="utf-8")
    (root / "validation_report.json").write_text('{"mode": "not-run", "ok": null, "errors": [], "warnings": []}', encoding="utf-8")
    (root / "knowledge" / "source-framework.md").write_text("# Source\n", encoding="utf-8")
    (root / "memory" / "MEMORY.md").write_text("# Memory\n", encoding="utf-8")
    (root / "workflows" / "ported-identity-review.yaml").write_text(
        "\n".join(
            [
                "name: ported-identity-review",
                "description: Review generated identity files.",
                "steps:",
                "  - prompt: Review generated files.",
                "channel: chat",
            ]
        ),
        encoding="utf-8",
    )
    (root / "agent.yaml").write_text(
        "\n".join(
            [
                'spec_version: "0.1.0"',
                "name: test-agent",
                'version: "0.1.0"',
                'description: "test"',
                "model:",
                '  preferred: "gpt-4o-mini"',
                "tools:",
                "  []",
                "skills:",
                "  []",
                "knowledge:",
                "  paths:",
                "    - knowledge/source-framework.md",
                "memory:",
                "  path: memory/MEMORY.md",
                "tags:",
                "  - ported-agent",
            ]
        ),
        encoding="utf-8",
    )
    (root / "conversion_map.json").write_text(
        "\n".join(
            [
                "{",
                '  "source": "test",',
                '  "framework": {"framework": "generic"},',
                '  "generated_agent": "test-agent",',
                '  "identity_fragments": [],',
                '  "rules": [],',
                '  "model_preferences": [],',
                '  "tools": [],',
                '  "manual_review": [],',
                '  "boundary": "This migration ports the agent identity layer, not the full runtime implementation."',
                "}",
            ]
        ),
        encoding="utf-8",
    )


class _CompletedProcess:
    def __init__(self, returncode: int, stdout: str, stderr: str) -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _completed_process(returncode: int, stdout: str, stderr: str) -> _CompletedProcess:
    return _CompletedProcess(returncode, stdout, stderr)


if __name__ == "__main__":
    unittest.main()
