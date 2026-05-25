from __future__ import annotations

from pathlib import Path

from agentport.models import CompatibilityProfile, DocsEvidence, FrameworkDetection

ALIASES = {
    "crewai": "crewai",
    "crew": "crewai",
    "langgraph": "langgraph",
    "langchain": "langchain",
    "deepagents": "deepagents",
    "deep-agents": "deepagents",
    "deep agents": "deepagents",
    "adk": "google adk",
    "google-adk": "google adk",
    "google adk": "google adk",
    "claude": "claude code / claude sdk",
    "claude-code": "claude code / claude sdk",
    "claude code": "claude code / claude sdk",
    "claude sdk": "claude code / claude sdk",
    "anthropic": "claude code / claude sdk",
    "cursor": "cursor",
    "openai": "openai agents sdk",
    "openai-agents": "openai agents sdk",
    "openai-agents-sdk": "openai agents sdk",
    "autogen": "microsoft autogen",
    "microsoft autogen": "microsoft autogen",
    "semantic-kernel": "semantic kernel",
    "semantic kernel": "semantic kernel",
    "haystack": "haystack",
    "llamaindex": "llamaindex",
    "llama-index": "llamaindex",
    "nemo": "nvidia nemo / aiq",
    "aiq": "nvidia nemo / aiq",
    "nvidia-aiq": "nvidia nemo / aiq",
    "nvidia nemo": "nvidia nemo / aiq",
    "hermes": "hermes / agent memory repos",
}


def default_registry_path(agentport_root: Path | None = None) -> Path:
    root = agentport_root or Path(__file__).resolve().parents[2]
    return root / "agents" / "agentport" / "knowledge" / "framework-docs" / "framework-links.md"


def load_docs_registry(path: Path | None = None) -> dict[str, list[dict[str, str]]]:
    registry_path = path or default_registry_path()
    text = registry_path.read_text(encoding="utf-8")
    registry: dict[str, list[dict[str, str]]] = {}
    current: str | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("## "):
            current = _canonical(line[3:])
            registry.setdefault(current, [])
            continue
        if not current or not line.startswith("- "):
            continue
        body = line[2:]
        if "http://" not in body and "https://" not in body:
            continue
        label, url = _split_link(body)
        registry[current].append({"label": label, "url": url})
    return registry


def docs_check(
    framework: str,
    profile: str | None = None,
    compatibility: CompatibilityProfile | None = None,
    detection: FrameworkDetection | None = None,
    registry_path: Path | None = None,
) -> DocsEvidence:
    canonical = _canonical(framework)
    registry = load_docs_registry(registry_path)
    links = registry.get(canonical, [])
    aliases = sorted(alias for alias, target in ALIASES.items() if target == canonical)
    reasons: list[str] = []

    if not links:
        reasons.append("No preloaded documentation links found for this framework.")
    if profile and any(marker in profile for marker in ("legacy", "unimplemented", "unclassified", "generic")):
        reasons.append(f"Profile '{profile}' should be verified against current or archived docs.")
    if compatibility:
        if compatibility.deprecated_patterns:
            reasons.append("Deprecated patterns were detected.")
        if compatibility.unknown_patterns:
            reasons.append("Unknown compatibility patterns were detected.")
        if not compatibility.version_hints:
            reasons.append("No dependency version hints were found.")
    if detection and detection.confidence < 0.70:
        reasons.append(f"Framework detection confidence is low ({detection.confidence:.2f}).")

    return DocsEvidence(
        framework=canonical,
        aliases=aliases,
        links=links,
        verification_recommended=bool(reasons),
        reasons=reasons,
    )


def _split_link(body: str) -> tuple[str, str]:
    parts = body.split("http", 1)
    label = parts[0].rstrip(": ").strip() or "Docs"
    url = "http" + parts[1].strip()
    return label, url


def _canonical(value: str) -> str:
    normalized = value.strip().lower().replace("_", "-")
    normalized = " ".join(normalized.replace("/", " / ").split())
    return ALIASES.get(normalized, normalized)
