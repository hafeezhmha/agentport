from pathlib import Path
import tempfile
import unittest

from agentport.core.scanner.file_tree import scan_files
from agentport.core.scanner.repository_extractor import extract_repository
from agentport.orchestrator import port


FIXTURES = Path(__file__).parent / "fixtures"


class LangChainMappingTests(unittest.TestCase):
    def test_extracts_legacy_agentexecutor_runtime(self):
        root = FIXTURES / "langchain_agentexecutor_legacy"
        extraction = extract_repository(scan_files(root))
        runtime = extraction.langchain_runtime

        self.assertEqual(runtime["agents"][0]["kind"], "initialize_agent")
        self.assertEqual(runtime["executors"][0]["kind"], "AgentExecutor")
        self.assertTrue(any(tool["kind"] == "Tool" for tool in runtime["tools"]))
        self.assertTrue(any("AgentExecutor runtime loop" in item for item in extraction.manual_review))

    def test_extracts_react_agent_prompts_tools_and_retrieval_markers(self):
        root = FIXTURES / "langchain_react_current"
        extraction = extract_repository(scan_files(root))
        runtime = extraction.langchain_runtime

        self.assertEqual(runtime["agents"][0]["kind"], "create_react_agent")
        self.assertEqual(runtime["executors"][0]["kind"], "AgentExecutor")
        self.assertTrue(any(prompt.get("template") == "You are a current LangChain ReAct agent. Use retrieved context carefully." for prompt in runtime["prompts"]))
        self.assertTrue(any(tool["name"] == "search_docs" for tool in runtime["tools"]))
        search_tool = next(tool for tool in extraction.tools if tool.name == "search_docs")
        self.assertEqual(search_tool.parameters["properties"]["query"]["type"], "string")
        self.assertEqual(search_tool.parameters["required"], ["query"])
        self.assertTrue(any(marker["kind"] == "retrieval_or_vectorstore" for marker in runtime["runtime_markers"]))
        self.assertTrue(any(fragment.kind == "langchain_chat_prompt" for fragment in extraction.identity_fragments))

    def test_conversion_map_includes_langchain_runtime(self):
        source = FIXTURES / "langchain_react_current"
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "ported"
            result = port(str(source), str(out), validate=True, learn=False)
            conversion = (out / "conversion_map.json").read_text(encoding="utf-8")
            tool_yaml = (out / "tools" / "search-docs.yaml").read_text(encoding="utf-8")

        self.assertEqual(result.detection.framework, "langchain")
        self.assertIn('"langchain_runtime"', conversion)
        self.assertIn('"create_react_agent"', conversion)
        self.assertIn('"search_docs"', conversion)
        self.assertIn('"retrieval_or_vectorstore"', conversion)
        self.assertIn('"query": {"type": "string"}', tool_yaml)
        self.assertIn('"required": ["query"]', tool_yaml)

    def test_extracts_structured_chat_agent_factory(self):
        root = FIXTURES / "langchain_structured_chat_current"
        extraction = extract_repository(scan_files(root))
        runtime = extraction.langchain_runtime

        self.assertEqual(runtime["agents"][0]["kind"], "create_structured_chat_agent")
        self.assertEqual(runtime["executors"][0]["kind"], "AgentExecutor")
        self.assertTrue(any(tool["name"] == "lookup_account" for tool in runtime["tools"]))
        lookup_tool = next(tool for tool in extraction.tools if tool.name == "lookup_account")
        self.assertEqual(lookup_tool.parameters["properties"]["account_id"]["type"], "string")
        self.assertEqual(lookup_tool.parameters["required"], ["account_id"])
        self.assertTrue(any("structured chat support agent" in fragment.text for fragment in extraction.identity_fragments))

    def test_extracts_openai_tools_agent_factory(self):
        root = FIXTURES / "langchain_openai_tools_current"
        extraction = extract_repository(scan_files(root))
        runtime = extraction.langchain_runtime

        self.assertEqual(runtime["agents"][0]["kind"], "create_openai_tools_agent")
        self.assertEqual(runtime["executors"][0]["kind"], "AgentExecutor")
        self.assertTrue(any(tool["name"] == "search_orders" for tool in runtime["tools"]))
        search_tool = next(tool for tool in extraction.tools if tool.name == "search_orders")
        self.assertEqual(search_tool.parameters["properties"]["query"]["type"], "string")
        self.assertEqual(search_tool.parameters["required"], ["query"])
        self.assertTrue(any("OpenAI tools agent" in fragment.text for fragment in extraction.identity_fragments))

    def test_extracts_explicit_args_schema_from_pydantic_model(self):
        root = FIXTURES / "langchain_args_schema_current"
        extraction = extract_repository(scan_files(root))

        lookup_tool = next(tool for tool in extraction.tools if tool.name == "lookup_order")
        properties = lookup_tool.parameters["properties"]
        self.assertEqual(properties["order_id"]["type"], "string")
        self.assertEqual(properties["order_id"]["description"], "Order identifier to look up.")
        self.assertEqual(properties["include_history"]["type"], "boolean")
        self.assertEqual(properties["include_history"]["description"], "Whether to include historical status changes.")
        self.assertEqual(properties["limit"]["type"], "integer")
        self.assertEqual(lookup_tool.parameters["required"], ["order_id"])
        self.assertTrue(any("MissingInput" in item for item in extraction.manual_review))

    def test_generated_tool_yaml_uses_explicit_args_schema(self):
        source = FIXTURES / "langchain_args_schema_current"
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "ported"
            result = port(str(source), str(out), validate=True, learn=False)
            tool_yaml = (out / "tools" / "lookup-order.yaml").read_text(encoding="utf-8")
            manual = (out / "TODO_MANUAL_REVIEW.md").read_text(encoding="utf-8")

        self.assertEqual(result.detection.framework, "langchain")
        self.assertTrue(result.validation.ok, result.validation.errors)
        self.assertIn('"order_id": {"type": "string", "description": "Order identifier to look up."}', tool_yaml)
        self.assertIn('"include_history": {"type": "boolean", "description": "Whether to include historical status changes."}', tool_yaml)
        self.assertIn('"required": ["order_id"]', tool_yaml)
        self.assertIn("MissingInput", manual)

    def test_extracts_zeroshot_agent_constructor(self):
        root = FIXTURES / "langchain_zeroshot_legacy"
        extraction = extract_repository(scan_files(root))
        runtime = extraction.langchain_runtime

        self.assertEqual(runtime["agents"][0]["kind"], "ZeroShotAgent")
        self.assertEqual(runtime["executors"][0]["kind"], "AgentExecutor")
        self.assertTrue(any(tool["kind"] == "Tool" for tool in runtime["tools"]))
        self.assertTrue(any("ZeroShotAgent constructor" in item for item in extraction.manual_review))


if __name__ == "__main__":
    unittest.main()
