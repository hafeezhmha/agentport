from pathlib import Path
import tempfile
import unittest

from agentport.orchestrator import port


FIXTURES = Path(__file__).parent / "fixtures"


class SchemaCompatibilityTests(unittest.TestCase):
    def test_current_crewai_schema_fields_are_extracted_and_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "crewai-out"
            result = port(str(FIXTURES / "crewai_schema_current"), str(out), validate=True, pr_ready=True, learn=False)
            conversion = (out / "conversion_map.json").read_text(encoding="utf-8")
            compat = (out / "framework_compatibility_report.md").read_text(encoding="utf-8")

        self.assertEqual(result.detection.framework, "crewai")
        self.assertIn("Senior AI Researcher", conversion)
        self.assertIn("guardrail", conversion)
        self.assertIn("output_pydantic", conversion)
        self.assertIn("Process.hierarchical", conversion)
        self.assertIn("tasks.yaml description/expected_output/string guardrail", compat)

    def test_current_langgraph_schema_topology_is_extracted_and_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "langgraph-out"
            result = port(str(FIXTURES / "langgraph_schema_current"), str(out), validate=True, learn=False)
            conversion = (out / "conversion_map.json").read_text(encoding="utf-8")
            compat = (out / "framework_compatibility_report.md").read_text(encoding="utf-8")

        self.assertEqual(result.detection.framework, "langgraph")
        self.assertIn("LangGraph node: classify", conversion)
        self.assertIn("classify -> route", conversion)
        self.assertIn("Command/Send runtime behavior", compat)
        self.assertIn("requires manual review", conversion)

    def test_current_claude_cursor_schema_imports_and_mdc_metadata_are_extracted(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "claude-out"
            result = port(str(FIXTURES / "claude_cursor_schema_current"), str(out), validate=True, learn=False)
            conversion = (out / "conversion_map.json").read_text(encoding="utf-8")
            compat = (out / "framework_compatibility_report.md").read_text(encoding="utf-8")

        self.assertEqual(result.detection.framework, "claude-cursor")
        self.assertIn("Avoid unrelated refactors", conversion)
        self.assertIn("Cursor rule metadata", conversion)
        self.assertIn(".claude/CLAUDE.md", compat)
        self.assertIn("CLAUDE.md @imports", compat)


if __name__ == "__main__":
    unittest.main()
