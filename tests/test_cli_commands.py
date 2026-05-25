from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from agentport.cli.main import main
from agentport.models import FrameworkDetection, PortResult, ValidationResult
from agentport.orchestrator import doctor, explain, fixtures_list


FIXTURES = Path(__file__).parent / "fixtures"


class CliCommandTests(unittest.TestCase):
    def test_compatibility_json_command(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = main(["compatibility", "--source", str(FIXTURES / "crewai_schema_current"), "--json"])

        self.assertEqual(code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["framework"]["framework"], "crewai")
        self.assertEqual(payload["compatibility"]["profile"], "crewai-modern-yaml")
        self.assertIn("docs_evidence", payload)

    def test_explain_includes_extraction_boundary(self):
        result = explain(str(FIXTURES / "langchain_react_current"))

        self.assertEqual(result["framework"]["framework"], "langchain")
        self.assertIn("identity layer", result["boundary"])
        extraction = result["extraction"]
        self.assertGreaterEqual(len(extraction["manual_review"]), 1)
        self.assertIn("langchain_runtime", extraction)

    def test_explain_text_command(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = main(["explain", "--source", str(FIXTURES / "claude_cursor_schema_current")])

        self.assertEqual(code, 0)
        output = stdout.getvalue()
        self.assertIn("Framework: claude-cursor", output)
        self.assertIn("Manual review items:", output)

    def test_doctor_runs_fixture_smoke_checks(self):
        result = doctor(Path(__file__).resolve().parents[1])

        self.assertTrue(result["ok"])
        checks = result["checks"]
        names = {check["name"] for check in checks}
        self.assertIn("docs_registry", names)
        self.assertIn("fixture:crewai_schema_current", names)
        self.assertIn("fixture:langgraph_schema_current", names)

    def test_fixtures_list_inventory_includes_known_fixtures(self):
        result = fixtures_list(Path(__file__).resolve().parents[1])

        by_name = {fixture["name"]: fixture for fixture in result}
        self.assertIn("crewai_schema_current", by_name)
        self.assertIn("langgraph_schema_current", by_name)
        self.assertIn("langchain_react_current", by_name)
        self.assertEqual(by_name["crewai_schema_current"]["framework"]["framework"], "crewai")
        self.assertEqual(by_name["langgraph_schema_current"]["compatibility"]["profile"], "langgraph-v1")
        self.assertEqual(by_name["langchain_zeroshot_legacy"]["compatibility"]["profile"], "langchain-zeroshot-legacy")
        self.assertEqual(by_name["langchain_react_current"]["compatibility"]["profile"], "langchain-modern-agent-factory")
        self.assertEqual(by_name["langchain_args_schema_current"]["compatibility"]["profile"], "langchain-tool-args-schema")

    def test_fixtures_list_json_command(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = main(["fixtures", "list", "--json"])

        self.assertEqual(code, 0)
        payload = json.loads(stdout.getvalue())
        fixtures = {fixture["name"]: fixture for fixture in payload["fixtures"]}
        self.assertIn("crewai_schema_current", fixtures)
        self.assertIn("langgraph_schema_current", fixtures)
        self.assertIn("langchain_react_current", fixtures)
        self.assertIn("framework", fixtures["crewai_schema_current"])
        self.assertIn("compatibility", fixtures["crewai_schema_current"])

    def test_strict_mode_returns_three_for_low_confidence_detection(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = main(["compatibility", "--source", str(FIXTURES / "langgraph_schema_current"), "--strict"])

        self.assertEqual(code, 3)
        self.assertIn("strict mode failed", stderr.getvalue())

    def test_port_strict_mode_skips_generation_on_low_confidence_detection(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out"
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                code = main(["port", "--source", str(FIXTURES / "langgraph_schema_current"), "--output", str(out), "--strict"])

        self.assertEqual(code, 3)
        self.assertFalse(out.exists())
        self.assertIn("strict mode failed", stderr.getvalue())

    def test_port_validation_failure_returns_two(self):
        result = PortResult(
            output_path=Path("/tmp/agentport-test"),
            generated_files=["agent.yaml"],
            detection=FrameworkDetection("crewai", 0.94),
            validation=ValidationResult("internal-schema-fallback", False, errors=["missing_file: agent.yaml: Required generated file is missing."]),
        )
        stdout = io.StringIO()
        with patch("agentport.cli.main.port", return_value=result):
            with contextlib.redirect_stdout(stdout):
                code = main(["port", "--source", str(FIXTURES / "crewai_schema_current"), "--validate"])

        self.assertEqual(code, 2)
        self.assertIn("Validation: internal-schema-fallback failed", stdout.getvalue())

    def test_port_allow_partial_remains_permissive_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out"
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = main(["port", "--source", str(FIXTURES / "langchain_react_current"), "--output", str(out), "--allow-partial", "--no-learn"])

            self.assertEqual(code, 0)
            self.assertTrue((out / "TODO_MANUAL_REVIEW.md").exists())

    def test_cli_end_to_end_analyze_and_port_validate_json(self):
        analyze_stdout = io.StringIO()
        with contextlib.redirect_stdout(analyze_stdout):
            analyze_code = main(["analyze", "--source", str(FIXTURES / "crewai_yaml_hardening"), "--json"])

        self.assertEqual(analyze_code, 0)
        analyze_payload = json.loads(analyze_stdout.getvalue())
        self.assertEqual(analyze_payload["framework"]["framework"], "crewai")
        self.assertGreater(analyze_payload["identity_fragments"], 0)

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "ported"
            port_stdout = io.StringIO()
            with contextlib.redirect_stdout(port_stdout):
                port_code = main(
                    [
                        "port",
                        "--source",
                        str(FIXTURES / "crewai_yaml_hardening"),
                        "--output",
                        str(out),
                        "--validate",
                        "--json",
                        "--no-learn",
                    ]
                )

            self.assertEqual(port_code, 0)
            port_payload = json.loads(port_stdout.getvalue())
            self.assertEqual(port_payload["framework"]["framework"], "crewai")
            self.assertTrue(port_payload["validation"]["ok"])
            self.assertEqual(len(port_payload["generated_files"]), len(set(port_payload["generated_files"])))
            self.assertTrue((out / "agent.yaml").exists())
            self.assertTrue((out / "conversion_map.json").exists())
            self.assertTrue((out / "TODO_MANUAL_REVIEW.md").exists())

    def test_port_llm_review_without_api_key_writes_skipped_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "ported"
            stdout = io.StringIO()
            with patch.dict("os.environ", {}, clear=True):
                with contextlib.redirect_stdout(stdout):
                    code = main(
                        [
                            "port",
                            "--source",
                            str(FIXTURES / "crewai_schema_current"),
                            "--output",
                            str(out),
                            "--validate",
                            "--llm-review",
                            "--json",
                            "--no-learn",
                        ]
                    )

            self.assertEqual(code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["llm_review"]["status"], "skipped")
            self.assertIn("LLM_REVIEW.md", payload["generated_files"])
            review = (out / "LLM_REVIEW.md").read_text(encoding="utf-8")
            self.assertIn("Status: skipped", review)
            self.assertIn("source of truth", review)

    def test_port_validator_command_flag_is_used(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out"
            stdout = io.StringIO()
            with patch.dict("os.environ", {"AGENTPORT_VALIDATOR_COMMAND": "env-validator {path}"}):
                with patch("agentport.core.validation.gapman_runner.subprocess.run", return_value=_completed_process(0, "", "")) as run:
                    with contextlib.redirect_stdout(stdout):
                        code = main(
                            [
                                "port",
                                "--source",
                                str(FIXTURES / "crewai_schema_current"),
                                "--output",
                                str(out),
                                "--validate",
                                "--validator-command",
                                "flag-validator {path}",
                                "--json",
                                "--no-learn",
                            ]
                        )

        self.assertEqual(code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["validation"]["mode"], "validator-override")
        self.assertEqual(run.call_args.args[0], ["flag-validator", str(out.resolve())])


if __name__ == "__main__":
    unittest.main()


class _CompletedProcess:
    def __init__(self, returncode: int, stdout: str, stderr: str) -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _completed_process(returncode: int, stdout: str, stderr: str) -> _CompletedProcess:
    return _CompletedProcess(returncode, stdout, stderr)
