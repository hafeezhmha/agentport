from pathlib import Path
import tempfile
import unittest

from agentport.core.scanner.file_tree import scan_files
from agentport.core.scanner.framework_detector import detect_framework


class FrameworkDetectionTests(unittest.TestCase):
    def test_detects_crewai_from_yaml_and_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "agents.yaml").write_text("researcher:\n  role: Researcher\n", encoding="utf-8")
            (root / "crew.py").write_text("from crewai import Agent\n", encoding="utf-8")
            detection = detect_framework(scan_files(root))
        self.assertEqual(detection.framework, "crewai")
        self.assertGreaterEqual(detection.confidence, 0.5)

    def test_detects_claude_cursor_rules(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".cursor" / "rules").mkdir(parents=True)
            (root / ".cursor" / "rules" / "main.mdc").write_text("Be concise.", encoding="utf-8")
            detection = detect_framework(scan_files(root))
        self.assertEqual(detection.framework, "claude-cursor")


if __name__ == "__main__":
    unittest.main()
