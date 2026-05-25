from pathlib import Path
import tempfile
import unittest

from agentport.core.generation.report_writer import write_reports
from agentport.core.mapping.generic_mapper import make_port_plan
from agentport.core.scanner.compatibility_profiler import profile_compatibility
from agentport.core.scanner.file_tree import scan_files
from agentport.core.scanner.framework_detector import detect_framework
from agentport.core.scanner.repository_extractor import extract_repository
from agentport.core.validation.gapman_runner import internal_schema_validate
from agentport.core.validation.readiness_score import assess_readiness
from agentport.models import ValidationResult
from agentport.orchestrator import port


FIXTURES = Path(__file__).parent / "fixtures"


class ReadinessScoreTests(unittest.TestCase):
    def test_validation_errors_are_hard_blockers(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "generated"
            port(str(FIXTURES / "crewai_schema_current"), str(out), validate=False, learn=False)
            source = FIXTURES / "crewai_schema_current"
            files = scan_files(source)
            detection = detect_framework(files)
            extraction = extract_repository(files)
            compatibility = profile_compatibility(files, detection)
            plan = make_port_plan(source, out, detection, extraction, compatibility)
            validation = ValidationResult(mode="internal-schema-fallback", ok=False, errors=["broken_reference: tools/search.yaml: missing"])

            readiness = assess_readiness(plan, validation)

        self.assertFalse(readiness.safe_to_publish)
        self.assertIn("broken_reference", readiness.hard_blockers[0])
        self.assertEqual(readiness.gates["schema_validation"], "fail")

    def test_readiness_report_lists_hard_blockers(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "generated"
            port(str(FIXTURES / "crewai_schema_current"), str(out), validate=False, learn=False)
            (out / "skills" / "ported-identity" / "SKILL.md").unlink()
            validation = internal_schema_validate(out)

            source = FIXTURES / "crewai_schema_current"
            files = scan_files(source)
            detection = detect_framework(files)
            extraction = extract_repository(files)
            compatibility = profile_compatibility(files, detection)
            plan = make_port_plan(source, out, detection, extraction, compatibility)
            write_reports(plan, [], validation, pr_ready=False)
            report = (out / "registry_readiness_report.md").read_text(encoding="utf-8")

        self.assertIn("Safe to publish: no", report)
        self.assertIn("## Hard Blockers", report)
        self.assertIn("broken_reference", report)
        self.assertIn("Schema Validation: fail", report)

    def test_passing_schema_with_manual_review_is_not_publish_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "generated"
            port(str(FIXTURES / "langchain_react_current"), str(out), validate=True, learn=False)
            report = (out / "registry_readiness_report.md").read_text(encoding="utf-8")

        self.assertIn("Safe to publish: no", report)
        self.assertIn("Manual Review: warning", report)
        self.assertIn("manual review item(s) remain open", report)


if __name__ == "__main__":
    unittest.main()
