from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from agentport.orchestrator import port
from agentport.core.scanner.yaml_extractor import load_yamlish


FIXTURES = Path(__file__).parent / "fixtures"


def markdown_section(text: str, heading: str) -> str:
    marker = f"## {heading}"
    start = text.index(marker)
    next_heading = text.find("\n## ", start + len(marker))
    return text[start:] if next_heading == -1 else text[start:next_heading]


class GoldenOutputTests(unittest.TestCase):
    def test_crewai_conversion_map_has_stable_structured_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out"
            port(str(FIXTURES / "crewai_schema_current"), str(out), validate=True, pr_ready=True, learn=False)
            conversion = json.loads((out / "conversion_map.json").read_text(encoding="utf-8"))

        self.assertEqual(conversion["framework"]["framework"], "crewai")
        self.assertEqual(conversion["compatibility_profile"]["profile"], "crewai-modern-yaml")
        self.assertIn("identity layer", conversion["boundary"])
        self.assertGreaterEqual(len(conversion["identity_fragments"]), 4)
        self.assertTrue(any(item["kind"] == "goal" for item in conversion["identity_fragments"]))
        self.assertTrue(any(item["kind"] == "expected_output" for item in conversion["rules"]))
        self.assertTrue(any("output_pydantic" in item for item in conversion["manual_review"]))
        self.assertEqual(conversion["framework_compatibility"]["profile"], "crewai-modern-yaml")

    def test_compatibility_report_sections_are_normalized(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out"
            port(str(FIXTURES / "langgraph_schema_current"), str(out), validate=True, learn=False)
            report = (out / "framework_compatibility_report.md").read_text(encoding="utf-8")

        profile = markdown_section(report, "Profile Evidence")
        manual = markdown_section(report, "Manual Review Boundary")
        coverage = markdown_section(report, "Current Migration Coverage")

        self.assertIn("LangGraph StateGraph", profile)
        self.assertIn("conditional routing semantics", manual)
        self.assertIn("Identity fragments:", coverage)

    def test_crewai_yaml_context_is_preserved_in_conversion_and_workflow(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out"
            port(str(FIXTURES / "crewai_yaml_hardening"), str(out), validate=True, learn=False)
            conversion = json.loads((out / "conversion_map.json").read_text(encoding="utf-8"))
            workflow = (out / "workflows" / "ported-identity-review.yaml").read_text(encoding="utf-8")

        fragments = conversion["identity_fragments"]
        self.assertTrue(any(item["kind"] == "knowledge_source" and "docs/frameworks.md" in item["text"] for item in fragments))
        self.assertTrue(any(item["kind"] == "task_context" and "previous_task" in item["text"] for item in fragments))
        self.assertIn("Review CrewAI task context evidence from config/tasks.yaml", workflow)

    def test_crewai_agent_yaml_has_stable_generated_structure(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out"
            port(str(FIXTURES / "crewai_yaml_hardening"), str(out), validate=True, learn=False)
            agent = load_yamlish(out / "agent.yaml")

        self.assertEqual(agent["spec_version"], "0.1.0")
        self.assertEqual(agent["name"], "crewai-yaml-hardening-gitagent")
        self.assertEqual(agent["model"]["preferred"], "gpt-4o-mini")
        self.assertIn("serperdevtool", agent["tools"])
        self.assertIn("filereadtool", agent["tools"])
        self.assertIn("ported-identity", agent["skills"])

    def test_crewai_manual_review_has_stable_line_aware_sections(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out"
            port(str(FIXTURES / "crewai_yaml_hardening"), str(out), validate=True, learn=False)
            manual = (out / "TODO_MANUAL_REVIEW.md").read_text(encoding="utf-8")

        self.assertIn("This migration ports the agent identity layer", manual)
        self.assertIn("config/agents.yaml:16: agent 'researcher' field 'knowledge_sources'", manual)
        self.assertIn("config/tasks.yaml:11: task 'research_task' field 'context'", manual)
        self.assertIn("src/crew.py:19: CrewAI crew orchestration function 'crew'", manual)


if __name__ == "__main__":
    unittest.main()
