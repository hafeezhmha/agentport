from __future__ import annotations

from collections import defaultdict

from agentport.models import FrameworkDetection, SourceFile
from agentport.core.scanner.file_tree import read_text


def detect_framework(files: list[SourceFile]) -> FrameworkDetection:
    scores: dict[str, float] = defaultdict(float)
    evidence: dict[str, list[str]] = defaultdict(list)
    names = {f.rel_path.lower() for f in files}

    def mark(framework: str, score: float, reason: str) -> None:
        scores[framework] += score
        evidence[framework].append(reason)

    for file in files:
        rel = file.rel_path.lower()
        if rel.endswith(("agents.yaml", "tasks.yaml")):
            mark("crewai", 0.22, f"Found {file.rel_path}")
        if rel.endswith("crew.py") or "/crew.py" in rel:
            mark("crewai", 0.18, f"Found {file.rel_path}")
        if rel.endswith((".cursorrules", "claude.md")) or rel.startswith(".cursor/rules/"):
            mark("claude-cursor", 0.30, f"Found instruction file {file.rel_path}")
        if rel.endswith((".mdc", ".md")) and any(x in rel for x in ("cursor", "claude", "rules")):
            mark("claude-cursor", 0.15, f"Found rules-like markdown {file.rel_path}")
        if file.suffix == ".py":
            text = read_text(file.path, limit=25_000)
            lowered = text.lower()
            if "from crewai" in lowered or "import crewai" in lowered:
                mark("crewai", 0.32, f"Found CrewAI import in {file.rel_path}")
            if "langgraph" in lowered or "stategraph" in text:
                mark("langgraph", 0.34, f"Found LangGraph marker in {file.rel_path}")
            if "langchain" in lowered:
                mark("langchain", 0.18, f"Found LangChain marker in {file.rel_path}")
            if "openai.agents" in lowered or "from agents import agent" in lowered:
                mark("openai-agents-sdk", 0.20, f"Found OpenAI Agents SDK marker in {file.rel_path}")
        if file.rel_path in {"requirements.txt", "pyproject.toml", "Pipfile"}:
            text = read_text(file.path, limit=40_000).lower()
            for pkg, framework in (
                ("crewai", "crewai"),
                ("langgraph", "langgraph"),
                ("langchain", "langchain"),
                ("google-adk", "google-adk"),
                ("openai-agents", "openai-agents-sdk"),
            ):
                if pkg in text:
                    mark(framework, 0.18, f"Found dependency {pkg} in {file.rel_path}")

    if "agents.yaml" in names and "tasks.yaml" in names:
        mark("crewai", 0.12, "Found CrewAI agents.yaml and tasks.yaml pair")

    if not scores:
        return FrameworkDetection(
            framework="generic",
            confidence=0.35,
            evidence=["No strong framework markers found; using generic identity extraction."],
        )

    ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    framework, score = ordered[0]
    confidence = max(0.5, min(0.98, score))
    alternatives = [name for name, _ in ordered[1:4]]
    return FrameworkDetection(framework, confidence, evidence[framework], alternatives)
