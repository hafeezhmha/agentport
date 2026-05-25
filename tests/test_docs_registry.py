from pathlib import Path
import tempfile
import unittest

from agentport.core.docs_registry import docs_check, load_docs_registry
from agentport.orchestrator import analyze, port


FIXTURES = Path(__file__).parent / "fixtures"


class DocsRegistryTests(unittest.TestCase):
    def test_registry_loads_expected_framework_links(self):
        registry = load_docs_registry()
        self.assertIn("crewai", registry)
        self.assertIn("langgraph", registry)
        self.assertIn("google adk", registry)
        self.assertIn("claude code / claude sdk", registry)
        self.assertTrue(any("docs.crewai.com" in link["url"] for link in registry["crewai"]))

    def test_aliases_resolve_to_docs_evidence(self):
        adk = docs_check("adk")
        claude = docs_check("anthropic")
        deepagents = docs_check("deep-agents")
        self.assertEqual(adk.framework, "google adk")
        self.assertEqual(claude.framework, "claude code / claude sdk")
        self.assertEqual(deepagents.framework, "deepagents")
        self.assertTrue(adk.links)
        self.assertTrue(claude.links)

    def test_analyze_source_includes_docs_evidence(self):
        result = analyze(str(FIXTURES / "crewai_legacy_code_only"))
        docs = result["docs_evidence"]
        self.assertEqual(docs["framework"], "crewai")
        self.assertTrue(docs["verification_recommended"])
        self.assertTrue(docs["links"])

    def test_generated_report_includes_docs_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out"
            port(str(FIXTURES / "crewai_legacy_code_only"), str(out), validate=True, pr_ready=True, learn=False)
            report = (out / "framework_compatibility_report.md").read_text(encoding="utf-8")
            conversion = (out / "conversion_map.json").read_text(encoding="utf-8")
            pr_body = (out / "PULL_REQUEST.md").read_text(encoding="utf-8")

        self.assertIn("## Documentation Evidence", report)
        self.assertIn("https://docs.crewai.com/", report)
        self.assertIn('"docs_evidence"', conversion)
        self.assertIn("Docs verification recommended", pr_body)


if __name__ == "__main__":
    unittest.main()
