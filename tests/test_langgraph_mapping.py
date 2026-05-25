from pathlib import Path
import tempfile
import unittest

from agentport.core.scanner.repository_extractor import extract_repository
from agentport.core.scanner.file_tree import scan_files
from agentport.core.scanner.framework_detector import detect_framework
from agentport.orchestrator import port


class LangGraphMappingTests(unittest.TestCase):
    def test_detects_langgraph_python_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "graph.py").write_text("from langgraph.graph import StateGraph\n", encoding="utf-8")
            detection = detect_framework(scan_files(root))
        self.assertEqual(detection.framework, "langgraph")

    def test_extracts_structured_langgraph_topology(self):
        root = Path(__file__).parent / "fixtures" / "langgraph_schema_current"
        extraction = extract_repository(scan_files(root))
        topology = extraction.graph_topology

        self.assertEqual({node["name"] for node in topology["nodes"]}, {"classify", "escalate", "draft"})
        self.assertIn({"source": "START", "target": "classify", "file": "graph.py", "line": 37}, topology["edges"])
        self.assertIn({"source": "draft", "target": "END", "file": "graph.py", "line": 39}, topology["edges"])
        self.assertEqual(topology["conditional_edges"][0]["source"], "classify")
        self.assertEqual(topology["conditional_edges"][0]["router"], "route")
        self.assertEqual(topology["conditional_edges"][0]["path_map"], {"urgent": "escalate", "normal": "draft"})
        self.assertTrue(any(schema.get("name") == "EmailState" for schema in topology["state_schemas"]))

    def test_conversion_map_includes_langgraph_topology(self):
        source = Path(__file__).parent / "fixtures" / "langgraph_schema_current"
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "ported"
            port(str(source), str(out), validate=False, pr_ready=False)
            conversion = (out / "conversion_map.json").read_text(encoding="utf-8")

        self.assertIn('"graph_topology"', conversion)
        self.assertIn('"conditional_edges"', conversion)
        self.assertIn('"EmailState"', conversion)

    def test_langgraph_topology_is_preserved_in_generated_workflow(self):
        source = Path(__file__).parent / "fixtures" / "langgraph_schema_current"
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "ported"
            result = port(str(source), str(out), validate=True, pr_ready=False, learn=False)
            workflow = (out / "workflows" / "ported-identity-review.yaml").read_text(encoding="utf-8")

        self.assertTrue(result.validation.ok, result.validation.errors)
        self.assertIn("Review LangGraph topology evidence", workflow)
        self.assertIn("Review LangGraph node 'classify' handled by 'classify' from graph.py:34", workflow)
        self.assertIn("Review LangGraph edge 'START -> classify' from graph.py:37", workflow)
        self.assertIn("Review LangGraph conditional edge from 'classify' via 'route' from graph.py:38", workflow)
        self.assertIn("urgent -> escalate", workflow)
        self.assertIn("Review LangGraph state schema 'EmailState' fields: message, classification", workflow)
        self.assertIn("compiled runtime behavior remains outside the identity-layer port", workflow)

    def test_generic_workflow_is_unchanged_without_langgraph_topology(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source"
            out = Path(tmp) / "ported"
            source.mkdir()
            (source / "CLAUDE.md").write_text("You are a careful repo agent.", encoding="utf-8")
            result = port(str(source), str(out), validate=True, pr_ready=False, learn=False)
            workflow = (out / "workflows" / "ported-identity-review.yaml").read_text(encoding="utf-8")

        self.assertTrue(result.validation.ok, result.validation.errors)
        self.assertIn("If graph_topology is present, compare nodes and edges", workflow)
        self.assertNotIn("Review LangGraph topology evidence", workflow)


if __name__ == "__main__":
    unittest.main()
