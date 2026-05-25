from pathlib import Path
import tempfile
import unittest

from agentport.orchestrator import port


class GitAgentGenerationTests(unittest.TestCase):
    def test_port_generates_required_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "source"
            out = Path(tmp) / "out"
            root.mkdir()
            (root / "CLAUDE.md").write_text("You are a careful repo agent.", encoding="utf-8")
            result = port(str(root), str(out), validate=True, pr_ready=True, learn=False)
            self.assertTrue(result.validation)
            self.assertTrue(result.validation.ok)
            for rel in ("agent.yaml", "SOUL.md", "RULES.md", "DUTIES.md", "conversion_map.json", "PULL_REQUEST.md"):
                self.assertTrue((out / rel).exists(), rel)


if __name__ == "__main__":
    unittest.main()
