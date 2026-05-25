from pathlib import Path
import tempfile
import unittest

from agentport.orchestrator import analyze, port


FIXTURES = Path(__file__).parent / "fixtures"


class CompatibilityProfileTests(unittest.TestCase):
    def test_crewai_modern_yaml_profile(self):
        result = analyze(str(FIXTURES / "crewai_schema_current"))
        compat = result["compatibility"]
        self.assertEqual(compat["profile"], "crewai-modern-yaml")
        self.assertTrue(any("crewai" in hint for hint in compat["version_hints"]) or compat["confidence"] >= 0.9)

    def test_crewai_legacy_code_only_profile_and_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out"
            port(str(FIXTURES / "crewai_legacy_code_only"), str(out), validate=True, learn=False)
            conversion = (out / "conversion_map.json").read_text(encoding="utf-8")
            report = (out / "framework_compatibility_report.md").read_text(encoding="utf-8")

        self.assertIn("crewai-legacy-code-only", conversion)
        self.assertIn("crewai==0.28.8", conversion)
        self.assertIn("Code-only CrewAI definitions", report)

    def test_langchain_agentexecutor_profile(self):
        result = analyze(str(FIXTURES / "langchain_agentexecutor_legacy"))
        self.assertEqual(result["framework"]["framework"], "langchain")
        compat = result["compatibility"]
        self.assertEqual(compat["framework"], "langchain")
        self.assertEqual(compat["profile"], "langchain-agentexecutor")
        self.assertIn("legacy", " ".join(compat["deprecated_patterns"]).lower())

    def test_langchain_zeroshot_legacy_profile(self):
        result = analyze(str(FIXTURES / "langchain_zeroshot_legacy"))
        self.assertEqual(result["framework"]["framework"], "langchain")
        compat = result["compatibility"]
        self.assertEqual(compat["framework"], "langchain")
        self.assertEqual(compat["profile"], "langchain-zeroshot-legacy")
        self.assertIn("zeroshotagent", " ".join(compat["evidence"]).lower())
        self.assertIn("legacy", " ".join(compat["deprecated_patterns"]).lower())

    def test_langchain_args_schema_profile(self):
        result = analyze(str(FIXTURES / "langchain_args_schema_current"))
        self.assertEqual(result["framework"]["framework"], "langchain")
        compat = result["compatibility"]
        self.assertEqual(compat["framework"], "langchain")
        self.assertEqual(compat["profile"], "langchain-tool-args-schema")
        self.assertIn("args_schema", " ".join(compat["evidence"]))

    def test_langgraph_legacy_profile(self):
        result = analyze(str(FIXTURES / "langgraph_legacy_no_start_end"))
        compat = result["compatibility"]
        self.assertEqual(compat["profile"], "langgraph-v0-or-legacy")
        self.assertTrue(compat["version_hints"])

    def test_cursor_legacy_profile(self):
        result = analyze(str(FIXTURES / "cursor_legacy_cursorrules"))
        compat = result["compatibility"]
        self.assertEqual(compat["profile"], "cursor-legacy-cursorrules")
        self.assertIn("legacy", " ".join(compat["deprecated_patterns"]).lower())

    def test_claude_memory_profile(self):
        result = analyze(str(FIXTURES / "claude_project_memory_only"))
        compat = result["compatibility"]
        self.assertEqual(compat["profile"], "claude-project-memory")

    def test_pyproject_optional_dependencies_provide_version_hints(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "crew.py").write_text("from crewai import Agent\n", encoding="utf-8")
            (root / "pyproject.toml").write_text(
                "\n".join(
                    [
                        "[project]",
                        'name = "optional-crewai"',
                        "dependencies = []",
                        "",
                        "[project.optional-dependencies]",
                        'agents = ["crewai>=0.70.0", "langchain==0.2.1"]',
                    ]
                ),
                encoding="utf-8",
            )

            compat = analyze(str(root))["compatibility"]

        self.assertIn("crewai>=0.70.0 from pyproject.toml", compat["version_hints"])
        self.assertIn("langchain==0.2.1 from pyproject.toml", compat["version_hints"])

    def test_pyproject_poetry_and_uv_groups_provide_version_hints(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "graph.py").write_text("from langgraph.graph import StateGraph\n", encoding="utf-8")
            (root / "pyproject.toml").write_text(
                "\n".join(
                    [
                        "[project]",
                        'name = "grouped-langgraph"',
                        "",
                        "[dependency-groups]",
                        'agents = ["langgraph>=0.2.5"]',
                        "",
                        "[tool.poetry.group.agent.dependencies]",
                        'langchain = "^0.3.0"',
                    ]
                ),
                encoding="utf-8",
            )

            compat = analyze(str(root))["compatibility"]

        self.assertIn("langgraph>=0.2.5 from pyproject.toml", compat["version_hints"])
        self.assertIn("langchain^0.3.0 from pyproject.toml", compat["version_hints"])

    def test_uv_lock_package_blocks_provide_version_hints(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "crew.py").write_text("from crewai import Agent\n", encoding="utf-8")
            (root / "uv.lock").write_text(
                "\n".join(
                    [
                        'version = 1',
                        "",
                        "[[package]]",
                        'name = "crewai"',
                        'version = "0.70.0"',
                        "",
                        "[[package]]",
                        'name = "langgraph"',
                        'version = "0.2.5"',
                    ]
                ),
                encoding="utf-8",
            )

            compat = analyze(str(root))["compatibility"]

        self.assertIn("crewai==0.70.0 from uv.lock", compat["version_hints"])
        self.assertIn("langgraph==0.2.5 from uv.lock", compat["version_hints"])

    def test_poetry_lock_package_blocks_provide_version_hints(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "agent.py").write_text("from langchain.agents import AgentExecutor\n", encoding="utf-8")
            (root / "poetry.lock").write_text(
                "\n".join(
                    [
                        "[[package]]",
                        'name = "langchain"',
                        'version = "0.3.0"',
                        "",
                        "[[package]]",
                        'name = "openai-agents"',
                        'version = "0.1.0"',
                    ]
                ),
                encoding="utf-8",
            )

            compat = analyze(str(root))["compatibility"]

        self.assertIn("langchain==0.3.0 from poetry.lock", compat["version_hints"])
        self.assertIn("openai-agents==0.1.0 from poetry.lock", compat["version_hints"])


if __name__ == "__main__":
    unittest.main()
