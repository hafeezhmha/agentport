from pathlib import Path
import tempfile
import unittest

from agentport.core.scanner.file_tree import scan_files
from agentport.core.scanner.repository_extractor import extract_repository


FIXTURES = Path(__file__).parent / "fixtures"


class CrewAIMappingTests(unittest.TestCase):
    def test_extracts_agents_yaml_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "agents.yaml").write_text(
                "researcher:\n  role: Researcher\n  goal: Find evidence\n  backstory: Careful analyst\n",
                encoding="utf-8",
            )
            result = extract_repository(scan_files(root))
        texts = [fragment.text for fragment in result.identity_fragments]
        self.assertIn("Find evidence", texts)
        self.assertIn("Careful analyst", texts)
        self.assertTrue(result.hierarchy)

    def test_resolves_static_python_identity_references(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "crew.py").write_text(
                "\n".join(
                    [
                        "from crewai import Agent",
                        "",
                        'ROLE = "Reference Researcher"',
                        'GOAL = "Find static evidence"',
                        'BACKSTORY = f"{ROLE} with careful habits"',
                        'MODEL = "gpt-4o-mini"',
                        "",
                        "class ResearchCrew:",
                        '    agents_config = "config/agents.yaml"',
                        '    tasks_config = "config/tasks.yaml"',
                        "",
                        "agent = Agent(role=ROLE, goal=GOAL, backstory=BACKSTORY, llm=MODEL)",
                    ]
                ),
                encoding="utf-8",
            )
            result = extract_repository(scan_files(root))

        texts = [fragment.text for fragment in result.identity_fragments]
        self.assertIn("Reference Researcher", texts)
        self.assertIn("Find static evidence", texts)
        self.assertIn("Reference Researcher with careful habits", texts)
        self.assertIn("config/agents.yaml", texts)
        self.assertIn("gpt-4o-mini", [model.text for model in result.model_preferences])

    def test_crewai_yaml_hardening_extracts_tools_knowledge_and_context(self):
        result = extract_repository(scan_files(FIXTURES / "crewai_yaml_hardening"))

        texts = [fragment.text for fragment in result.identity_fragments]
        rule_texts = [rule.text for rule in result.rules]
        tool_names = {tool.name for tool in result.tools}
        manual = "\n".join(result.manual_review)
        fragments = {(fragment.kind, fragment.name, fragment.text) for fragment in result.identity_fragments}

        self.assertTrue(any("source-backed framework migration evidence" in text for text in texts))
        self.assertTrue(any("markdown table with field names" in text for text in rule_texts))
        self.assertIn("SerperDevTool", tool_names)
        self.assertIn("FileReadTool", tool_names)
        self.assertIn("knowledge_sources", manual)
        self.assertIn("context", manual)
        self.assertIn("config/agents.yaml:16: agent 'researcher' field 'knowledge_sources'", manual)
        self.assertIn("config/tasks.yaml:11: task 'research_task' field 'context'", manual)
        self.assertIn(("knowledge_source", "researcher", "agent 'researcher' knowledge source: docs/frameworks.md"), fragments)
        self.assertIn(("knowledge_source", "research_task", "task 'research_task' knowledge source: docs/crewai.md"), fragments)
        self.assertIn(("task_context", "research_task", "task 'research_task' context dependency: previous_task"), fragments)

    def test_crewai_decorated_functions_map_to_yaml_keys(self):
        result = extract_repository(scan_files(FIXTURES / "crewai_yaml_hardening"))

        mappings = [fragment.text for fragment in result.identity_fragments if fragment.kind == "crewai_config_mapping"]
        hierarchy = {(item.get("name"), item.get("source"), item.get("role")) for item in result.hierarchy}

        self.assertIn("researcher -> config/agents.yaml:researcher", mappings)
        self.assertIn("research_task -> config/tasks.yaml:research_task", mappings)
        self.assertIn(("researcher", "config/agents.yaml", "source-agent"), hierarchy)
        self.assertIn(("research_task", "config/tasks.yaml", "source-task"), hierarchy)
        self.assertNotIn(("defaults", "config/agents.yaml", "source-agent"), hierarchy)

    def test_crewai_runtime_options_and_output_schema_are_structured(self):
        result = extract_repository(scan_files(FIXTURES / "crewai_schema_current"))

        runtime = result.crewai_runtime
        markers = {(item.get("call"), item.get("kind")): item.get("value") for item in runtime["runtime_markers"]}
        output_schema = runtime["output_schemas"][0]
        output_fragments = [fragment.text for fragment in result.identity_fragments if fragment.kind == "output_schema"]

        self.assertEqual(markers[("Agent", "memory")], True)
        self.assertEqual(markers[("Crew", "process")], "Process.hierarchical")
        self.assertEqual(markers[("Crew", "manager_llm")], "gpt-4o")
        self.assertEqual(output_schema["name"], "ReportSchema")
        self.assertEqual(set(output_schema["schema"]["properties"]), {"title", "body"})
        self.assertTrue(any("fields: title, body" in fragment for fragment in output_fragments))
        self.assertTrue(any("CrewAI runtime option 'memory'" in item for item in result.manual_review))

    def test_crewai_agent_runtime_limit_options_are_structured(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "crew.py").write_text(
                "\n".join(
                    [
                        "from crewai import Agent",
                        "",
                        "agent = Agent(",
                        '    role="Researcher",',
                        '    goal="Find evidence",',
                        "    allow_delegation=False,",
                        "    max_iter=5,",
                        "    max_execution_time=120,",
                        "    max_rpm=30,",
                        "    respect_context_window=True,",
                        ")",
                    ]
                ),
                encoding="utf-8",
            )
            result = extract_repository(scan_files(root))

        markers = {item["kind"]: item["value"] for item in result.crewai_runtime["runtime_markers"]}
        self.assertEqual(markers["allow_delegation"], False)
        self.assertEqual(markers["max_iter"], 5)
        self.assertEqual(markers["max_execution_time"], 120)
        self.assertEqual(markers["max_rpm"], 30)
        self.assertEqual(markers["respect_context_window"], True)

    def test_crewai_decorated_config_mapping_supports_get_constants_and_aliases(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "crew.py").write_text(
                "\n".join(
                    [
                        "from crewai import Agent, Task",
                        "from crewai.project import CrewBase, agent, task",
                        "",
                        'AGENT_KEY = "researcher"',
                        "",
                        "@CrewBase",
                        "class ResearchCrew:",
                        '    agents_config = "config/agents.yaml"',
                        '    tasks_config = "config/tasks.yaml"',
                        '    task_key = "research_task"',
                        "",
                        "    @agent",
                        "    def researcher(self):",
                        "        cfg = self.agents_config.get(AGENT_KEY)",
                        "        return Agent(config=cfg)",
                        "",
                        "    @task",
                        "    def research_task(self):",
                        "        cfg = self.tasks_config[self.task_key]",
                        "        return Task(config=cfg)",
                    ]
                ),
                encoding="utf-8",
            )
            result = extract_repository(scan_files(root))

        mappings = {fragment.text for fragment in result.identity_fragments if fragment.kind == "crewai_config_mapping"}
        hierarchy = {(item.get("name"), item.get("source"), item.get("role")) for item in result.hierarchy}

        self.assertIn("researcher -> config/agents.yaml:researcher", mappings)
        self.assertIn("research_task -> config/tasks.yaml:research_task", mappings)
        self.assertIn(("researcher", "config/agents.yaml", "source-agent"), hierarchy)
        self.assertIn(("research_task", "config/tasks.yaml", "source-task"), hierarchy)


if __name__ == "__main__":
    unittest.main()
